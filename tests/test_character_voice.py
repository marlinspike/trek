"""The optional character voice model: which requests it answers, the fallback, settings and the CLI."""

from __future__ import annotations

import pytest

from begin.llm.providers.base import LLMError, Message
from begin.llm.routing import (CharacterRoute, RoutedProvider, character_from_settings, route_from_settings,
                               with_character)
from begin.llm.service import LLMService
from begin.llm.usage import caller


class Fake:
    def __init__(self, name: str, fail: bool = False) -> None:
        self.name = name
        self.fail = fail
        self.asked: list[str] = []

    def complete(self, system: str, messages: list[Message]) -> str:
        self.asked.append(system)
        if self.fail:
            raise LLMError("not running")
        return self.name


FACTIONS = {"7": "klingon", "8": "romulan"}


def ask(p: RoutedProvider, tag: str, system: str = "sys") -> str:
    token = caller.set(tag)
    try:
        return p.complete(system, [{"role": "user", "content": "hi"}])
    finally:
        caller.reset(token)


def routed(route: CharacterRoute, fail: bool = False) -> tuple[RoutedProvider, Fake, Fake]:
    main, char = Fake("main"), Fake("character", fail)
    return RoutedProvider(main, char, route, FACTIONS.get), main, char


def test_default_route_takes_enemy_captains_only() -> None:
    p, _, _ = routed(CharacterRoute())
    assert ask(p, "\0hail:7") == "character"
    assert ask(p, "\0hailvoice:8") == "character"
    for tag in ("worf", "\0line:worf", "log:spock", "console", "orders", "\0address", "direct"):
        assert ask(p, tag) == "main", tag


def test_factions_and_officers_narrow_the_route() -> None:
    p, _, _ = routed(route_from_settings({"for": ["captains", "officers", "chatter"], "factions": ["klingon"],
                                          "officers": ["worf"]}))
    assert ask(p, "\0hail:7") == "character"
    assert ask(p, "\0hail:8") == "main"           # a Romulan: not on the list
    assert ask(p, "\0hail:99") == "main"          # a ship that's gone
    assert ask(p, "worf") == "character"
    assert ask(p, "\0line:worf") == "character"
    assert ask(p, "spock") == "main"
    assert ask(p, "console") == "main"            # reading orders never leaves the main model


def test_notes_are_added_for_the_character_only() -> None:
    p, main, char = routed(route_from_settings({"notes": {"*": "Stay in character.", "klingon": "Speak Klingon."}}))
    ask(p, "\0hail:7", "base")
    ask(p, "\0hail:8", "base")
    assert char.asked[0] == "base\n\nStay in character. Speak Klingon."
    assert char.asked[1] == "base\n\nStay in character."
    ask(p, "worf", "base")
    assert main.asked == ["base"]


def test_a_failing_character_model_falls_back_to_the_main_one() -> None:
    p, main, _ = routed(CharacterRoute(), fail=True)
    assert ask(p, "\0hail:7") == "main"
    assert p.fallbacks == 1 and main.asked == ["sys"]


def test_service_tags_reach_the_router() -> None:
    p, _, _ = routed(CharacterRoute())
    svc = LLMService(p, workers=1)
    try:
        svc.submit("\0hail:7", "s", [])
        svc.submit("worf", "s", [])
        got: list = []
        import time

        for _ in range(200):
            got += svc.poll()
            if len(got) == 2:
                break
            time.sleep(0.01)
        assert {r.tag: r.text for r in got} == {"\0hail:7": "character", "worf": "main"}
    finally:
        svc.close()


def test_settings() -> None:
    assert character_from_settings({"provider": "ollama", "model": "a"}) is None
    llm = {"provider": "ollama", "model": "a", "log_tokens": True,
           "character": {"provider": "ollama", "model": "b", "think": "off", "for": "captains"}}
    cfg, route = character_from_settings(llm)  # type: ignore[misc]
    assert (cfg.model, cfg.think, cfg.log_tokens) == ("b", False, True)
    assert route.situations == {"captains"}
    assert character_from_settings({**llm, "character": {**llm["character"], "enabled": False}}) is None  # type: ignore[dict-item]
    with pytest.raises(LLMError):
        route_from_settings({"for": ["everything"]})


def test_with_character_reports_a_bad_setup_and_keeps_the_main_model() -> None:
    main = Fake("main")
    r = with_character(main, {"character": {"provider": "nonsense", "model": "x"}})
    assert r.provider is main and r.problem and "left out" in (r.note() or "")
    r = with_character(main, {"character": {"provider": "ollama", "model": "x"}})
    assert isinstance(r.provider, RoutedProvider) and "ollama (x)" in (r.note() or "")
    assert with_character(main, {}).provider is main


def test_cli_configures_and_removes_the_character_model(tmp_path, monkeypatch) -> None:
    from begin import settings as settings_mod
    from begin.tools.llm import configure

    monkeypatch.setattr(settings_mod, "settings_dir", lambda: tmp_path)
    s = configure(["provider=ollama", "model=a", "character.model=b", "character.provider=ollama",
                   "character.for=captains,taunts", "character.factions=klingon",
                   "character.notes.klingon=Use a few words of Klingon."])
    ch = s.llm["character"]
    assert ch == {"model": "b", "provider": "ollama", "for": ["captains", "taunts"], "factions": ["klingon"],
                  "notes": {"klingon": "Use a few words of Klingon."}}
    with pytest.raises(LLMError):
        configure(["character.colour=red"], s)
    s = configure(["character.only=worf,seven"], s)
    assert s.llm["character"]["only"] == ["worf", "seven"]
    s = configure(["character=off"], s)
    assert "character" not in s.llm


def test_battle_session_routes_hails_by_faction(tmp_path) -> None:
    from begin.battle import build_battle
    from begin.content import default_content
    from begin.presets import load_presets
    from begin.session.battle import BattleSession

    preset = next(p for p in load_presets() if p.id == "border-incident")
    battle = build_battle(default_content(), preset.setup())
    llm = {"provider": "ollama", "model": "a", "character": {"provider": "ollama", "model": "b"}}
    session = BattleSession(battle, hidden={}, llm=llm, career={}, config=tmp_path)
    heard: list[object] = []
    session.subscribe(heard.append)
    try:
        klingon = next(s for s in battle.world.ships.values() if s.faction == "klingon")
        assert session._faction_of(str(klingon.id)) == "klingon"
        prov = session.comms.llm.provider  # type: ignore[union-attr]
        assert isinstance(prov, RoutedProvider)
        assert prov.route.subject(f"\0hail:{klingon.id}", prov._faction) == "klingon"
        assert any("Character voices through ollama (b)" in getattr(n, "text", "") for n in heard)
    finally:
        session.close()


def test_the_character_voices_page_toggles_and_saves(tmp_path, monkeypatch) -> None:
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    from begin import settings as settings_mod
    from begin.content import default_content
    from begin.settings import Settings
    from begin.ui.menu_scene import MenuScene

    monkeypatch.setattr(settings_mod, "settings_dir", lambda: tmp_path)
    pygame.init()
    surf = pygame.display.set_mode((1400, 860))
    st = Settings(llm={"provider": "ollama", "model": "a", "character": {"provider": "ollama", "model": "b"}})
    menu = MenuScene(default_content(), st, lambda setup: None, lambda: None)
    menu.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_v, mod=0, unicode="v"))
    assert menu.page == "settings" and menu.hub.section == "voices"
    menu.draw(surf)
    toggle = next(h for h in menu.ui.hotspots if h.tooltip.startswith("Off keeps"))
    toggle.action()               # On -> Off: saved under llm.character, the model's settings kept
    saved = Settings.load().llm["character"]
    assert saved["enabled"] is False and saved["model"] == "b"
    klingon = next(h for h in menu.ui.hotspots if h.tooltip.startswith("None picked"))
    menu.draw(surf)               # Off: the race buttons stand idle
    assert not any(h.tooltip.startswith("None picked") for h in menu.ui.hotspots)
    del klingon
    next(h for h in menu.ui.hotspots if h.tooltip.startswith("Off keeps")).action()   # back on
    menu.draw(surf)               # one button per officer for "only this model"
    pin = [h for h in menu.ui.hotspots if h.tooltip.startswith("Everything this officer says")]
    assert len(pin) == 4
    pin[1].action()
    assert Settings.load().llm["character"]["only"] == ["worf"]
    menu.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
    assert menu.page == "main"


def test_pinned_characters_use_only_the_character_model() -> None:
    route = route_from_settings({"for": ["captains"], "only": ["worf", "romulan"]})
    p, main, char = routed(route)
    for tag in ("worf", "\0line:worf", "log:worf", "\0hailvoice:8"):     # pinned, whatever "for" says
        assert ask(p, tag) == "character", tag
    assert ask(p, "spock") == "main"
    assert ask(p, "\0address") == "main" and ask(p, "console") == "main"   # judgements never move
    p, main, _ = routed(route, fail=True)
    with pytest.raises(LLMError):
        ask(p, "worf")                       # no stand-in: the officer answers offline instead
    assert main.asked == [] and p.fallbacks == 0
    assert ask(p, "\0hail:7") == "main"      # not pinned: the main model still stands in
