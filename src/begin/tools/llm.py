"""Command-line helpers for the officers' language model.

    begin --llm provider=ollama model=lfm3 think=off    save these in settings.json
    begin --llm provider=off                           officers answer offline again
    begin --llm-test                                   ask Spock one question and print the answer
    begin --llm log_prompts=on log_tokens=on           the debug logs, in config/logs/
    begin --llm-usage                                  print the token totals

Keys accepted by --llm: provider, model, base_url, think, effort, timeout, max_tokens, console,
log_prompts, log_tokens (console = on | off | always: plain-English orders at the console;
log_prompts / log_tokens = on | off: see `llm/usage.py`).
API keys are never written; they come from the environment.
"""

from __future__ import annotations

import time

from ..settings import Settings
from ..llm.providers.base import LLMError, config_from_settings, make_provider, parse_switch, parse_think

KEYS = ("provider", "model", "base_url", "think", "effort", "timeout", "max_tokens", "console", "log_prompts",
        "log_tokens")


def configure(pairs: list[str], settings: Settings | None = None) -> Settings:
    """Merge key=value pairs into the saved "llm" settings; an empty value removes the key."""
    s = settings or Settings.load()
    llm = dict(s.llm)
    for pair in pairs:
        key, sep, value = pair.partition("=")
        key = key.strip().lower().replace("-", "_")
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
        llm = {"provider": "off", **{k: llm[k] for k in ("log_prompts", "log_tokens") if k in llm}}
    config_from_settings(llm, env={})  # validate before saving
    s.llm = llm
    s.save()
    print(f"Saved to {Settings.path()}: \"llm\": {llm}")
    return s


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
    think = {None: "model default", True: "on", False: "off"}.get(cfg.think, str(cfg.think))  # type: ignore[call-overload]
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


__all__ = ["KEYS", "configure", "test", "usage"]
