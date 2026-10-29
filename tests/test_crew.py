"""Bridge officers: delegation, conversation, rapport, the hidden setting and the LLM plumbing."""

from __future__ import annotations

import json
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
    assert cfg == LLMConfig("ollama", "other", timeout=120.0)
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
    b = _battle(content)
    for ship in b.world.ships.values():
        if ship.side != b.world.ships[b.player_ship_id].side:
            ship.name = "Derango"  # a fixed enemy name for the tests that talk about it
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
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
    before = sc.bridge.relationships.get("worf").rapport
    sc.run_console("worf, you are useless")
    assert sc.bridge.relationships.get("worf").rapport < before
    sc.run_console("seven, you are useless")
    assert sc.bridge.relationships.get("seven").rapport == 1.0
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


def test_llm_answer_to_a_question_only_suggests(scene) -> None:  # type: ignore[no-untyped-def]
    sc, _ = scene
    fake = _Fake('{"say": "Close and fire.", "commands": ["target derango[weapons]", "fire all phasers [spread 45]"]}')
    sc.bridge.llm = LLMService(fake)
    fired = sc.player.stats.phaser_shots
    sc.run_console("spock, what do you recommend?")
    end = time.time() + 5
    while sc.bridge.llm.busy("spock") and time.time() < end:
        sc.update(0.0)
        time.sleep(0.01)
    sc.update(0.0)
    texts = [line.text for line in sc.log]
    assert any("› target derango weapons" in t for t in texts)
    assert sc.player.stats.phaser_shots == fired and sc.player.target is None
    sc.run_console("target derango weapons")
    assert sc.bridge.relationships.get("spock").advice_taken == 1
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


def test_ollama_think_switch(monkeypatch: pytest.MonkeyPatch) -> None:
    from begin.llm.providers import ollama
    from begin.llm.providers.base import parse_think

    assert parse_think("nothink") is False and parse_think("think") is True and parse_think(None) is None
    assert parse_think("High") == "high" and parse_think(False) is False and parse_think("default") is None
    cfg = config_from_settings({"provider": "ollama", "model": "lfm3", "think": False}, env={})
    assert cfg is not None and cfg.think is False
    cfg = config_from_settings({"provider": "ollama", "model": "lfm3", "think": False}, env={"BEGIN_LLM_THINK": "think"})
    assert cfg is not None and cfg.think is True
    bodies: list[dict[str, object]] = []

    def fake_post(url, body, headers, timeout):  # type: ignore[no-untyped-def]
        bodies.append(body)
        return {"message": {"thinking": "hmm", "content": "<think>inline</think> Aye, Captain."}}

    monkeypatch.setattr(ollama, "post_json", fake_post)
    assert make_provider(LLMConfig("ollama", "lfm3", think=False), env={}).complete("s", []) == "Aye, Captain."
    assert bodies[-1]["think"] is False
    make_provider(LLMConfig("ollama", "lfm3"), env={}).complete("s", [])
    assert "think" not in bodies[-1]  # unset: the model's own default

    def refuse(url, body, headers, timeout):  # type: ignore[no-untyped-def]
        raise LLMError('400 from the provider: {"error":"\\"lfm3\\" does not support thinking"}')

    monkeypatch.setattr(ollama, "post_json", refuse)
    with pytest.raises(LLMError, match="think\": false"):
        make_provider(LLMConfig("ollama", "lfm3", think=True), env={}).complete("s", [])


def test_llm_cli_configures_settings(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    from begin.llm.cli import configure
    from begin.ui.settings import Settings

    monkeypatch.setenv("BEGIN_HOME", str(tmp_path))
    configure(["provider=ollama", "model=lfm3", "think=nothink"])
    assert Settings.load().llm == {"provider": "ollama", "model": "lfm3", "think": False}
    configure(["think=think", "timeout=200"])
    assert Settings.load().llm["think"] is True and Settings.load().llm["timeout"] == 200.0
    configure(["think="])
    assert "think" not in Settings.load().llm
    with pytest.raises(LLMError):
        configure(["colour=blue"])
    configure(["provider=off"])
    assert Settings.load().llm == {"provider": "off"}


def test_llm_commands_are_cleaned_and_questions_only_suggest() -> None:
    from begin.crew.conversation import clean_command, is_question

    assert clean_command("target derango[weapons]") == "target derango weapons"
    assert clean_command("fire all phasers [spread 45]") == "fire all phasers spread 45"
    say, cmds = parse_reply('{"say": "Aye.", "commands": ["helm <90> warp 6", " "]}')
    assert cmds == ["helm 90 warp 6"]
    assert is_question("what do you recommend?") and is_question("should we close in")
    assert not is_question("fire all torpedoes") and not is_question("take tactical")


def test_old_home_folder_is_copied_into_config(tmp_path) -> None:  # type: ignore[no-untyped-def]
    from begin.paths import migrate_legacy, project_root

    old, new = tmp_path / "home", tmp_path / "config"
    (old / "help").mkdir(parents=True)
    (old / "settings.json").write_text('{"llm": {"provider": "ollama", "model": "lfm3"}}')
    (old / "begin2.key").write_text("F2 fire all torpedoes\n")
    (old / "help" / "mine.md").write_text("---\ntitle: Mine\n---\nHello")
    assert sorted(migrate_legacy(old, new)) == ["begin2.key", "help/mine.md", "settings.json"]
    assert "lfm3" in (new / "settings.json").read_text() and (old / "settings.json").exists()
    assert migrate_legacy(old, new) == []  # once only
    other = tmp_path / "config2"
    other.mkdir()
    (old / "settings.json").write_text('{"hidden": {"rapport": {"spock": {}}}, "llm": {"model": "x"}, "speed": 2}')
    assert "settings.json" in migrate_legacy(old, other)
    merged = json.loads((other / "settings.json").read_text())
    assert merged["llm"] == {"provider": "off", "model": "x"}  # the project's own values win
    root = project_root()
    assert root is not None and (root / "config" / "README.md").is_file()


def test_science_officer_gives_last_fix_on_lost_contact(content) -> None:  # type: ignore[no-untyped-def]
    from begin.crew.conversation import Bridge
    from begin.help.coach import HelpContext
    from begin.presets import load_presets

    b = build_battle(content, load_presets()[0].setup())
    assert b.crew is not None and b.player_ship_id is not None
    bridge = Bridge(b.crew, {})
    w = b.world
    me = w.ships[b.player_ship_id]
    enemy = next(s for s in w.ships.values() if s.side != me.side)
    w.run(1)
    w.take_events()
    enemy.x, enemy.y = me.x, me.y + me.sensor_range() * 2   # far beyond the haze band
    w.run(0.2)
    events = w.take_events()
    ctx = HelpContext(content, w.observe(me.side), me)
    said = [u.text for u in bridge.react(events, ctx)]
    assert any(enemy.name in t and "bearing" in t for t in said), said


def test_seven_rapport_floor_holds(content) -> None:  # type: ignore[no-untyped-def]
    from begin.crew.conversation import Bridge
    from begin.presets import load_presets

    b = build_battle(content, load_presets()[0].setup())
    assert b.crew is not None
    rel = bridge.relationships.get("seven")
    assert rel.rapport == 1.0 and rel.mood == "devoted"
    rel.nudge(-0.5)
    assert rel.rapport == 1.0
    assert bridge.relationships.get("spock").floor == -1.0


def test_spock_and_seven_design_a_tachyon_detector(scene) -> None:  # type: ignore[no-untyped-def]
    import math

    from begin.console.parser import ParseContext, parse
    from begin.sim.commands import FireSpecialRound

    sc, surf = scene
    sc.run_console("spock, I think there's a cloaked ship out there")
    assert "tachyon" in sc.player.projects
    assert _said(sc, "Spock") and any("Twenty seconds" in t for t in _said(sc, "Seven of Nine"))
    sc.run_console("seven, find the cloaked ship")   # already under way: she says so instead of starting again
    assert any("already being designed" in t for t in _said(sc, "Seven of Nine"))
    for _ in range(25 * sc.world.rules.ticks_per_cycle):
        sc.world.step()
        sc._drain_events()
    tube = next(t for t in sc.player.tubes if t.loaded and t.loaded.ordnance == "tachyon")
    assert any(f"ready in tube {tube.index + 1}" in t for t in _said(sc, "Seven of Nine"))
    cmd = parse("tachyon 90 8000", ParseContext(sc.player_id, sc.world.observe(sc.side))).commands[0]
    assert isinstance(cmd, FireSpecialRound) and math.isclose(cmd.x, sc.player.x + 8000, abs_tol=1)
    sc.run_console("worf, tachyon 90 8000")
    assert tube.loaded is None or tube.loaded.ordnance != "tachyon"
    sc.draw(surf)


def test_an_officer_takes_the_bridge_and_hands_it_back(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    sc.run_console("delegate engineering")
    sc.run_console("seven, take the bridge")
    assert sc.player.conn == "seven" and sc.player.delegated == set(STATION_COMMANDS)
    assert any("bridge" in t.lower() or "command" in t.lower() for t in _said(sc, "Seven of Nine"))
    sc.player.target = None
    for _ in range(10 * sc.world.rules.ticks_per_cycle):
        sc.world.step()
        sc._drain_events()
    assert sc.player.target is not None          # she picked one herself
    sc.draw(surf)                                 # with the conn banner
    sc.run_console("helm 45 warp 2")              # the captain steps in; she leaves it alone for a while
    for _ in range(2 * sc.world.rules.ticks_per_cycle):
        sc.world.step()
    assert sc.player.desired_course == 45
    sc.run_console("I have the bridge")
    assert sc.player.conn == "" and sc.player.delegated == {"engineering"}   # back to how it was
    sc.run_console("conn worf")
    assert sc.player.conn == "worf" and _said(sc, "Worf")
    sc.run_console("spock, you have the conn")
    assert sc.player.conn == "spock"
    sc.run_console("conn captain")
    assert sc.player.conn == ""
    sc.run_console("worf, take tactical")
    sc.run_console("worf, I relieve you")         # with nobody in command, this is about his station
    assert "tactical" not in sc.player.delegated


def test_spock_in_command_hunts_cloaked_ships(content) -> None:  # type: ignore[no-untyped-def]
    from begin.core.rng import Rng
    from begin.crew.officers import Crew, default_crew
    from begin.sim.commands import FireSpecialRound, StartProject, TakeConn
    from begin.sim.world import World

    w = World(content, seed=3)
    hc = w.add_ship("federation.hc", 0, 0, 0)
    bp = w.add_ship("romulan.bp", 1, 0, 9000, course=180)
    w.run(1)
    bp.cloaked = True
    w.run(0.5)
    assert w.observe(0).contact(bp.id).cloaked_hint
    crew = Crew(hc.id, 0, content, default_crew(load_officers()), Rng(1))
    w.execute(TakeConn(ship_id=hc.id, officer="spock"))
    cmds = crew.think(w.observe(0))
    assert any(isinstance(c, StartProject) and c.project == "tachyon" for c in cmds)
    for c in cmds:
        w.execute(c)
    w.run(22)
    cmds = crew.think(w.observe(0))
    assert any(isinstance(c, FireSpecialRound) for c in cmds)


def test_officers_can_be_addressed_without_a_comma(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    b = sc.bridge
    for text, who, rest in [("seven take the bridge", "seven", "take the bridge"), ("Sev status", "seven", "status"),
                            ("SPOCK you have the conn", "spock", "you have the conn"),
                            ("seven of nine report", "seven", "report"), ("worf, fire", "worf", "fire"),
                            ("scotty raise all", "scotty", "raise all")]:
        hit = b.addressed(text)
        assert hit is not None and hit[0].id == who and hit[1] == rest, text
    for command in ("scan derango", "sc derango", "status", "fire all torpedoes", "seven"[:2] + " 90"):
        assert b.addressed(command) is None, command
    sc.run_console("seven take the bridge")
    assert sc.player.conn == "seven"
    sc.run_console("i have the bridge")
    assert sc.player.conn == ""


def test_seven_sets_up_and_fires_the_deflector_pulse(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    sc.run_console("seven use the deflector to find them")
    assert "deflector" in sc.player.projects and _said(sc, "Spock")
    for _ in range(15 * sc.world.rules.ticks_per_cycle):
        sc.world.step()
        sc._drain_events()
    assert sc.player.deflector_ready
    assert any("deflector is ready" in t for t in _said(sc, "Seven of Nine"))
    sc.run_console("seven, pulse")
    assert sc.player.deflector_cooldown > 0
    sc.draw(surf)


def test_seven_in_command_pulses_at_a_cloaked_ship_ahead(content) -> None:  # type: ignore[no-untyped-def]
    from begin.core.rng import Rng
    from begin.crew.officers import Crew, default_crew
    from begin.sim.commands import DeflectorPulse, TakeConn
    from begin.sim.world import World

    w = World(content, seed=3)
    hc = w.add_ship("federation.hc", 0, 0, 0)
    bp = w.add_ship("romulan.bp", 1, 0, 9000, course=180)
    hc.deflector_ready = True
    w.run(1)
    bp.cloaked = True
    w.run(0.5)
    crew = Crew(hc.id, 0, content, default_crew(load_officers()), Rng(1))
    w.execute(TakeConn(ship_id=hc.id, officer="seven"))
    assert any(isinstance(c, DeflectorPulse) for c in crew.think(w.observe(0)))
