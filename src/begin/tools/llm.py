"""Command-line helpers for the officers' language model.

    begin --llm provider=ollama model=lfm3 think=off    save these in settings.json
    begin --llm provider=off                           officers answer offline again
    begin --llm-test                                   ask Spock one question and print the answer
    begin --llm log_prompts=on log_tokens=on           the debug logs, in config/logs/
    begin --llm-usage                                  print the token totals
    begin --llm character.model=<name> character.for=captains,taunts character.factions=klingon
                                                       a second model for character voices (see llm/routing.py)
    begin --llm character=off                          no second model: the main one speaks for everyone
    begin --llm-voice-test klingon                     a Klingon captain answers a hail, through the model that would

Keys accepted by --llm: provider, model, base_url, think, effort, timeout, max_tokens, console,
log_prompts, log_tokens (console = on | off | always: plain-English orders at the console;
log_prompts / log_tokens = on | off: see `llm/usage.py`).
character.<key>: the character voice model, with the same keys (provider, model, base_url, think, effort, timeout,
max_tokens) plus enabled (on | off), for, factions and officers (comma-separated lists) and notes.<faction or
officer id> (a line added to that character's prompt). character=off removes it.
API keys are never written; they come from the environment.
"""

from __future__ import annotations

import time

from ..settings import Settings
from ..llm.providers.base import LLMError, config_from_settings, make_provider, parse_switch, parse_think
from ..llm.routing import CHARACTER_KEY, character_from_settings

KEYS = ("provider", "model", "base_url", "think", "effort", "timeout", "max_tokens", "console", "log_prompts",
        "log_tokens")


def configure(pairs: list[str], settings: Settings | None = None) -> Settings:
    """Merge key=value pairs into the saved "llm" settings; an empty value removes the key."""
    s = settings or Settings.load()
    llm = dict(s.llm)
    for pair in pairs:
        key, sep, value = pair.partition("=")
        key = key.strip().lower().replace("-", "_")
        if sep and (key == CHARACTER_KEY or key.startswith(CHARACTER_KEY + ".")):
            _configure_character(llm, key[len(CHARACTER_KEY) + 1:], value.strip())
            continue
        if not sep or key not in KEYS:
            raise LLMError(f"Expected key=value with key one of {', '.join(KEYS)}; got '{pair}'.")
        value = value.strip()
        if not value:
            llm.pop(key, None)
        elif key == "think":
            llm[key] = parse_think(value)
        elif key == "timeout":
            llm[key] = float(value)
        elif key == "console":
            from ..console.translator import normalize_mode

            llm[key] = normalize_mode(value)
        elif key in ("log_prompts", "log_tokens"):
            llm[key] = parse_switch(value)
        elif key == "max_tokens":
            llm[key] = int(value)
        else:
            llm[key] = value
    if str(llm.get("provider", "")).lower() == "off":
        llm = {"provider": "off", **{k: llm[k] for k in ("log_prompts", "log_tokens", CHARACTER_KEY) if k in llm}}
    config_from_settings(llm, env={})  # validate before saving
    character_from_settings(llm)
    s.llm = llm
    s.save()
    print(f"Saved to {Settings.path()}: \"llm\": {llm}")
    return s


CHARACTER_KEYS = ("provider", "model", "base_url", "think", "effort", "timeout", "max_tokens", "enabled", "for",
                  "factions", "officers")


def _configure_character(llm: dict[str, object], key: str, value: str) -> None:
    """One `character.<key>=value` pair, into llm["character"]; `character=off` (or empty) removes it all."""
    if not key:
        if value.lower() in ("", "off", "none", "false"):
            llm.pop(CHARACTER_KEY, None)
            return
        raise LLMError("Use character=off to remove the character model, or character.<key>=value to set it up.")
    raw = llm.get(CHARACTER_KEY)
    ch: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
    if key.startswith("notes."):
        who = key[len("notes."):].strip()
        notes = dict(ch.get("notes") or {})  # type: ignore[call-overload]
        if value:
            notes[who] = value
        else:
            notes.pop(who, None)
        ch["notes"] = notes
    elif key not in CHARACTER_KEYS:
        raise LLMError(f"character.<key> takes one of {', '.join(CHARACTER_KEYS)} or notes.<who>; got '{key}'.")
    elif not value:
        ch.pop(key, None)
    elif key in ("for", "factions", "officers"):
        ch[key] = [v.strip().lower() for v in value.split(",") if v.strip()]
    elif key == "think":
        ch[key] = parse_think(value)
    elif key == "enabled":
        ch[key] = parse_switch(value)
    elif key == "timeout":
        ch[key] = float(value)
    elif key == "max_tokens":
        ch[key] = int(value)
    else:
        ch[key] = value
    llm[CHARACTER_KEY] = ch


def voice_test(faction: str = "klingon", words: str = "This is the Enterprise. Stand down and you will not be harmed.") -> int:
    """Hail an enemy captain of this faction, as the game would, and print the answer and which model gave it."""
    from ..battle import build_battle
    from ..content import default_content
    from ..crew.hails import HAIL_TAG, Comms
    from ..llm.routing import RoutedProvider, with_character
    from ..llm.usage import caller
    from ..presets import load_presets

    s = Settings.load()
    cfg = config_from_settings(s.llm)
    if cfg is None:
        print("No LLM provider is set. Try: begin --llm provider=ollama model=<name>")
        return 1
    content = default_content()
    faction = faction.strip().lower()
    for preset in load_presets():
        battle = build_battle(content, preset.setup())
        enemy = next((sh for sh in battle.world.ships.values() if sh.faction == faction and sh.side != 0), None)
        if enemy is not None:
            break
    else:
        print(f"No preset battle has a {faction} ship to hail. Try klingon, romulan or orion.")
        return 1
    world = battle.world
    assert battle.player_ship_id is not None
    player = world.ships[battle.player_ship_id]
    routed = with_character(make_provider(cfg), s.llm, lambda sid: world.ships[int(sid)].faction)
    if routed.problem:
        print(f"The character model is left out: {routed.problem}")
    tag = f"{HAIL_TAG}{enemy.id}"
    rp = routed.provider
    who = (f"character model {routed.cfg.provider} ({routed.cfg.model})"
           if isinstance(rp, RoutedProvider) and routed.cfg is not None and rp.route.subject(tag, rp._faction)
           else f"main model {cfg.provider} ({cfg.model})")
    print(f"Hailing the {enemy.name} ({faction}); the {who} answers.")
    t0 = time.perf_counter()
    caller.set(tag)
    try:
        text = rp.complete(Comms(world, player.side).system_prompt(player, enemy), [{"role": "user", "content": words}])
    except LLMError as e:
        if isinstance(rp, RoutedProvider) and rp.fallbacks:
            print("The character model failed, and so did the main model.")
        print(f"Failed after {time.perf_counter() - t0:.1f}s: {e}")
        return 1
    if isinstance(rp, RoutedProvider) and rp.fallbacks:
        print("The character model failed; the main model answered instead.")
    print(f"Answered in {time.perf_counter() - t0:.1f}s.\n\n{text}")
    return 0


def test(question: str = "Spock, what do you recommend?") -> int:
    """Send one real question through the configured provider, as the game would, and print the reply."""
    from ..battle import build_battle
    from ..content import default_content
    from ..crew.conversation import Bridge
    from ..llm.reply import parse_reply
    from ..help.coach import HelpContext
    from ..presets import load_presets

    s = Settings.load()
    cfg = config_from_settings(s.llm)
    if cfg is None:
        print("No LLM provider is set; officers answer offline. Try: begin --llm provider=ollama model=<name>")
        return 1
    think = "model default" if cfg.think is None else "on" if cfg.think is True else "off" if cfg.think is False else str(cfg.think)
    print(f"Provider {cfg.provider}, model {cfg.model}, thinking {think}"
          + (f", endpoint {cfg.base_url}" if cfg.base_url else ""))
    content = default_content()
    battle = build_battle(content, load_presets()[0].setup())
    assert battle.crew is not None
    bridge = Bridge(battle.crew, dict(s.hidden))
    officer = battle.crew.find("spock")
    assert officer is not None
    world = battle.world
    ship = world.ships[battle.player_ship_id] if battle.player_ship_id is not None else None
    ctx = HelpContext(content, world.observe(ship.side if ship else 0), ship)
    provider = make_provider(cfg)
    t0 = time.perf_counter()
    try:
        from ..llm.usage import caller

        caller.set("llm-test")
        text = provider.complete(bridge.system_prompt(officer, ctx), [{"role": "user", "content": question}])
    except LLMError as e:
        print(f"Failed after {time.perf_counter() - t0:.1f}s: {e}")
        return 1
    say, commands = parse_reply(text)
    print(f"Answered in {time.perf_counter() - t0:.1f}s.\n\nRaw reply:\n{text}\n\n{officer.title}: {say}")
    if commands:
        print("Commands: " + "; ".join(commands))
    logs = [name for name, on in (("prompts", cfg.log_prompts), ("tokens", cfg.log_tokens)) if on]
    if logs:
        from ..llm.usage import log_dir

        print(f"Logged ({' and '.join(logs)}) in {log_dir()}")
    return 0


def usage() -> int:
    """Print the token log's totals and its most recent games."""
    from ..llm.usage import summary

    print(summary())
    return 0


__all__ = ["CHARACTER_KEYS", "KEYS", "configure", "test", "usage", "voice_test"]
