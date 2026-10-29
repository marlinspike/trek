"""Bridge officers: delegation, conversation, rapport, the hidden setting and the LLM plumbing."""

from __future__ import annotations

import os
import time

import pytest

from begin.battle import build_battle
from begin.crew.characters import (
    Relationship, Relationships, load_officers,
)
from begin.crew.conversation import parse_reply, situation
from begin.crew.officers import STATION_COMMANDS, station_of
from begin.help.coach import HelpContext
from begin.llm.providers.base import LLMConfig, LLMError, config_from_settings, make_provider
from begin.llm.service import LLMService
from begin.presets import load_presets
from begin.sim.commands import Authority, DelegateStation, SelectTarget, SetHelm


def _battle(content, preset: int = 0):  # type: ignore[no-untyped-def]
    return build_battle(content, load_presets()[preset].setup())


def test_officer_roster() -> None:
    officers = load_officers()
    assert {o.station for o in officers.values()} == {"helm", "tactical", "engineering", "science"}
    for o in officers.values():
        assert o.persona and o.lines.get("ack") and o.lines.get("unknown")


def test_station_commands_do_not_overlap() -> None:
    seen: set[type] = set()
    for kinds in STATION_COMMANDS.values():
        assert not (set(kinds) & seen)
        seen |= set(kinds)


def test_delegated_officers_only_work_their_own_stations(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    w, pid = b.world, b.player_ship_id
    assert b.crew is not None and pid is not None
    assert w.execute(DelegateStation(ship_id=pid, station="tactical")) is None
    assert w.execute(DelegateStation(ship_id=pid, station="science")) is None
    for _ in range(600):
        w.step()
    officer_cmds = [lc.command for lc in w.command_log
                    if lc.command.ship_id == pid and lc.command.issuer == Authority.OFFICER]
    assert officer_cmds, "officers should act"
    assert {station_of(c) for c in officer_cmds} <= {"tactical", "science"}
    assert w.ships[pid].target is not None  # Worf chose a target


def test_captain_orders_hold_against_the_helm_officer(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    w, pid = b.world, b.player_ship_id
    w.execute(DelegateStation(ship_id=pid, station="helm"))
    w.execute(SetHelm(ship_id=pid, course=33.0, warp=2.0))
    for _ in range(int(w.rules.captain_hold_cycles * w.rules.ticks_per_cycle) - 2):
        w.step()
    assert w.ships[pid].desired_course == 33.0


def test_officers_keep_the_captains_target(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content, 5)  # fleet action: several enemies
    w, pid = b.world, b.player_ship_id
    obs = w.observe(w.ships[pid].side)
    enemies = [c.id for c in obs.hostile_contacts()]
    assert enemies
    choice = enemies[-1]
    w.execute(SelectTarget(ship_id=pid, target=choice))
    w.execute(DelegateStation(ship_id=pid, station="tactical"))
    for _ in range(200):
        w.step()
    if w.ships[choice].alive and w.ships[pid].alive:
        assert w.ships[pid].target == choice


def test_delegation_is_deterministic(content) -> None:  # type: ignore[no-untyped-def]
    def run() -> list[tuple[int, str, bool]]:
        b = _battle(content)
        b.world.execute(DelegateStation(ship_id=b.player_ship_id, station="tactical"))
        b.world.execute(DelegateStation(ship_id=b.player_ship_id, station="helm"))
        for _ in range(400):
            b.world.step()
        return [(lc.tick, lc.command.name, lc.accepted) for lc in b.world.command_log]

    assert run() == run()


def test_rapport_round_trip_and_moods() -> None:
    rel = Relationships()
    rel.get("worf").nudge(0.5)
    rel.get("seven").nudge(-0.9)
    hidden: dict[str, object] = {}
    rel.to_settings(hidden)
    back = Relationships.from_settings(hidden)
    assert back.get("worf").mood == "warm" and back.get("seven").mood == "resentful"
    assert back.get("worf").negotiation_modifier() > 0 > back.get("seven").negotiation_modifier()

def test_parse_reply() -> None:
    assert parse_reply('Sure. {"say": "Firing.", "commands": ["fire all torpedoes"]}') == ("Firing.", ["fire all torpedoes"])
    assert parse_reply('{"say": "Aye", "commands": "raise all"}') == ("Aye", ["raise all"])
    assert parse_reply("Just words.") == ("Just words.", [])


def test_situation_summary_only_uses_our_knowledge(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    w = b.world
    ship = w.ships[b.player_ship_id]
    text = situation(HelpContext(content, w.observe(ship.side), ship))
    assert ship.name in text and "Hull" in text
    for s in w.ships.values():
        if s.side != ship.side and not w.is_visible(ship.side, s.id):
            assert s.name not in text


# ------------------------------------------------------------------ LLM plumbing

class _Fake:
    name = "fake"

    def __init__(self, reply: str | Exception) -> None:
        self.reply = reply
        self.seen: list[tuple[str, list[dict[str, str]]]] = []

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        self.seen.append((system, messages))
        if isinstance(self.reply, Exception):
            raise self.reply
        return self.reply


def _drain(svc: LLMService, timeout: float = 5.0):  # type: ignore[no-untyped-def]
    end = time.time() + timeout
    while time.time() < end:
        got = svc.poll()
        if got:
            return got
        time.sleep(0.01)
    raise AssertionError("no reply")


def test_service_runs_in_the_background() -> None:
    svc = LLMService(_Fake("hello"))
    svc.submit("spock", "sys", [{"role": "user", "content": "hi"}])
    assert svc.busy("spock")
    (r,) = _drain(svc)
    assert r.tag == "spock" and r.text == "hello" and not svc.busy("spock")
    svc2 = LLMService(_Fake(LLMError("down")))
    svc2.submit("worf", "sys", [])
    (r2,) = _drain(svc2)
    assert r2.text is None and r2.error == "down"
    svc.close()
    svc2.close()


def test_provider_configuration() -> None:
    assert config_from_settings({}, env={}) is None
    with pytest.raises(LLMError):
        config_from_settings({"provider": "anthropic"}, env={})  # no model
    with pytest.raises(LLMError):
        config_from_settings({"provider": "nonsense", "model": "m"}, env={})
    cfg = config_from_settings({"provider": "ollama", "model": "m"}, env={"BEGIN_LLM_MODEL": "other"})
    assert cfg == LLMConfig("ollama", "other")
    assert config_from_settings({"provider": "openai", "model": "m"}, env={"BEGIN_LLM_PROVIDER": "off"}) is None
    with pytest.raises(LLMError):
        make_provider(LLMConfig("openai", "m"), env={})  # no key


def test_http_providers_build_requests(monkeypatch: pytest.MonkeyPatch) -> None:
    from begin.llm.providers import ollama, openai_compat

    calls: list[tuple[str, dict[str, object], dict[str, str]]] = []

    def fake_post(url, body, headers, timeout):  # type: ignore[no-untyped-def]
        calls.append((url, body, headers))
        if "chat/completions" in url:
            return {"choices": [{"message": {"content": "aye"}}]}
        return {"message": {"content": "aye"}}

    monkeypatch.setattr(openai_compat, "post_json", fake_post)
    monkeypatch.setattr(ollama, "post_json", fake_post)
    p = make_provider(LLMConfig("openrouter", "some/model"), env={"OPENROUTER_API_KEY": "k"})
    assert p.complete("sys", [{"role": "user", "content": "hi"}]) == "aye"
    url, body, headers = calls[-1]
    assert url == "https://openrouter.ai/api/v1/chat/completions" and headers["Authorization"] == "Bearer k"
    assert body["messages"][0] == {"role": "system", "content": "sys"}  # type: ignore[index]
    p2 = make_provider(LLMConfig("ollama", "llama", base_url="http://box:11434/"), env={})
    assert p2.complete("sys", []) == "aye"
    assert calls[-1][0] == "http://box:11434/api/chat" and calls[-1][1]["stream"] is False


def test_anthropic_provider_needs_the_sdk(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def no_sdk(name, globals=None, locals=None, fromlist=(), level=0):  # type: ignore[no-untyped-def]
        if name == "anthropic" and level == 0:
            raise ImportError
        return real(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", no_sdk)
    with pytest.raises(LLMError, match="pip install anthropic"):
        make_provider(LLMConfig("anthropic", "m"))


# ------------------------------------------------------------------ in the battle scene

pygame = pytest.importorskip("pygame")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    sc = BattleScene(_battle(content), surf.get_size(), lambda: None, hidden={}, llm={})
    return sc, surf


def _said(sc, who: str) -> list[str]:  # type: ignore[no-untyped-def]
    return [ln.text for ln in sc.log if ln.text.startswith(who + ":")]


def test_talking_to_officers_offline(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    sc.run_console("worf, status")
    assert any("phaser" in t.lower() for t in _said(sc, "Worf"))
    sc.run_console("spock, what do you recommend?")
    assert _said(sc, "Spock")
    sc.run_console("scotty, take engineering")
    assert "engineering" in sc.player.delegated
    sc.run_console("scotty, stand down")
    assert "engineering" not in sc.player.delegated
    sc.run_console("worf, helm 90 warp 3")
    assert any("not my station" in t for t in _said(sc, "Worf"))
    sc.run_console("worf, raise all")
    assert any("not my station" in t for t in _said(sc, "Worf"))
    sc.run_console("scotty, raise all")
    assert all(sh.up for sh in sc.player.shields)
    before = sc.bridge.relationships.get("seven").rapport
    sc.run_console("seven, you are useless")
    assert sc.bridge.relationships.get("seven").rapport < before
    sc.run_console("ask seven of nine status")
    assert any("contacts" in t for t in _said(sc, "Seven of Nine"))
    sc.run_console("crew")
    assert sc.printout and sc.printout[0] == "BRIDGE CREW:"
    sc.draw(surf)


def test_llm_answers_carry_out_orders_for_the_right_station(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    fake = _Fake('{"say": "Shields up, and I will try the helm.", "commands": ["raise all", "helm 90 warp 2"]}')
    sc.bridge.llm = LLMService(fake)
    sc.run_console("scotty, shields up and turn us around")
    assert sc.bridge.llm.busy("scotty")
    end = time.time() + 5
    while sc.bridge.llm.busy("scotty") and time.time() < end:
        sc.update(0.0)
        time.sleep(0.01)
    sc.update(0.0)
    said = _said(sc, "Scott")
    assert any("Shields up" in t for t in said)
    assert all(sh.up for sh in sc.player.shields)
    assert any("not my station" in t for t in said)       # helm is Spock's
    system, messages = fake.seen[0]
    assert "Montgomery Scott" in system and messages[-1]["content"].startswith("shields up")
    sc.close()


def test_delegation_from_the_console_and_panel(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    sc.run_console("delegate all")
    assert sc.player.delegated == {"helm", "tactical", "engineering", "science"}
    sc.run_console("assume tactical")
    assert "tactical" not in sc.player.delegated
    sc.paused = False
    for _ in range(120):
        sc.update(1 / 30)
    sc.draw(surf)
