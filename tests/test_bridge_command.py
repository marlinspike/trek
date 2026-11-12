"""Bridge-style command: readbacks, subtitles, focus, the wheel, preview, completion, pointing, proposals,
alerts, recording, styles, trust, learned phrasing and voice (headless)."""

from __future__ import annotations

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from begin.battle import build_battle  # noqa: E402
from begin.console.complete import Completer  # noqa: E402
from begin.console.pointing import resolve_pointing  # noqa: E402
from begin.console.readback import mounts, readback  # noqa: E402
from begin.crew.career import Career, level  # noqa: E402
from begin.crew.proposals import Proposal, Proposer, candidates  # noqa: E402
from begin.presets import load_presets  # noqa: E402
from begin.sim.commands import FirePhasers, FireTorpedoes, Pursue, SelectTarget, SetHelm, SetShields  # noqa: E402
from begin.session.command import order_name, tidy  # noqa: E402
from begin.ui.battle_scene import BattleScene  # noqa: E402
from begin.session.prefs import BridgePrefs  # noqa: E402
from begin.ui.subtitles import Subtitles  # noqa: E402
from begin.ui.wheel import CommandWheel, load_wheels  # noqa: E402
from begin.voice.engines import WhisperServer, clean, multipart  # noqa: E402
from begin.voice.recorder import to_wav  # noqa: E402
from begin.voice.settings import VoiceSettings  # noqa: E402


@pytest.fixture()
def duel(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1600, 900))
    preset = next(p for p in load_presets() if p.id == "dreadnought-duel")
    b = build_battle(content, preset.setup())
    store: dict[str, object] = {}
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={}, bridge=store, career={}, voice={})
    sc.overlay = None
    return sc, surf


def _texts(sc: BattleScene) -> list[str]:
    return [ln.text for ln in sc.log]


def _enemy(sc: BattleScene) -> int:
    return min(sc.obs.contacts())


# ------------------------------------------------------------ readbacks


def test_readbacks_say_exactly_what_will_happen() -> None:
    name = {7: "Hydra"}.get
    assert readback(SetHelm(ship_id=1, course=90, warp=6), name) == "Course 090, warp 6."
    assert readback(SetHelm(ship_id=1, warp=0.0), name) == "All stop."
    assert readback(FirePhasers(ship_id=1, banks=(0, 2), target=7, subsystem="shields"), name) == \
        "Firing phasers 1 and 3 at the Hydra, aiming for her shields."
    assert readback(FireTorpedoes(ship_id=1, tubes=None, target=7, fan=10), name) == \
        "Firing all tubes at the Hydra, fanned 10°."
    assert readback(Pursue(ship_id=1, target=7, warp=5, elude=True), name) == "Breaking away from the Hydra at warp 5."
    assert readback(SelectTarget(ship_id=1, target=7, lock_weapons=True), name) == "Targeting the Hydra; weapons locked."
    assert readback(SetShields(ship_id=1, sectors=None, up=False), name) == "Lowering all shields."
    assert mounts((4,), "tube", "tubes") == "tube 5"


def test_the_officer_reads_an_order_back_in_the_bridge_column(duel) -> None:  # type: ignore[no-untyped-def]
    sc, surf = duel
    sc.run_console("helm 90 warp 6")
    back = [ln for ln in sc.log if "Course 090, warp 6." in ln.text]
    assert back and back[-1].channel == "bridge"
    assert any(ln.text == "> helm 90 warp 6" and ln.channel == "bridge" for ln in sc.log)
    sc.update(0.05)
    said = [x.text for x in ([sc.subs.current] if sc.subs.current else []) + sc.subs.waiting]
    assert any("Course 090" in t for t in said)
    sc.draw(surf)


def test_classic_bridge_keeps_acknowledged(duel) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel
    sc.run_console("hud bridge classic")
    assert sc.bridge_store["mode"] == "classic" and sc.bridge_store["wheel"] is False
    sc.run_console("helm 45")
    assert any(t.endswith(": acknowledged") for t in _texts(sc))
    sc.update(0.05)
    assert sc.subs.current is None


def test_bridge_prefs_round_trip() -> None:
    p = BridgePrefs.from_dict({"mode": "quiet", "focus": "pause", "wheel": "nonsense"})
    assert p.mode == "quiet" and p.focus == "pause" and p.wheel is True and p.subtitles == "urgent"
    assert BridgePrefs.from_dict(p.to_dict()) == p


def test_subtitles_one_voice_at_a_time_urgent_first() -> None:
    from begin.ui import theme

    s = Subtitles()
    for i in range(6):
        s.say("Spock", f"Remark {i}", theme.CREW)
    s.say("Worf", "Torpedoes!", theme.CAUTION, urgent=True)
    s.update(0.01)
    assert s.current is not None and s.current.text == "Torpedoes!"
    assert len(s.waiting) <= 3


# ------------------------------------------------------------ tactical focus


def test_focus_eases_to_a_quarter_while_typing_and_lapses(duel) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel
    sc.paused = False
    sc.speed = 2.0
    sc.console_focus = True
    sc.focus_keystroke()
    for _ in range(30):
        sc.update(1 / 30)
    assert sc.effective_speed() == pytest.approx(0.25)
    for _ in range(int(9 * 30)):
        sc.update(1 / 30)
    assert sc.effective_speed() == pytest.approx(2.0)       # eight idle seconds: the battle runs again
    sc.console_focus = False
    sc.run_console("hud focus pause")
    sc.console_focus = True
    sc.focus_keystroke()
    for _ in range(30):
        sc.update(1 / 30)
    assert sc.effective_speed() == pytest.approx(0.0)


# ------------------------------------------------------------ pointing, completion, preview


def test_pointing_words_become_the_ship_under_the_mouse() -> None:
    assert resolve_pointing("fire all phasers at her", "Hydra") == "fire all phasers at Hydra"
    assert resolve_pointing("pursue him warp 6", "#4") == "pursue #4 warp 6"
    assert resolve_pointing("scan that one", "Hydra") == "scan Hydra"
    assert resolve_pointing("raise her shields", "Hydra") == "raise her shields"
    assert resolve_pointing("fire at her", None) == "fire at her"


def test_tab_finishes_words_and_steps_through_choices() -> None:
    c = Completer()
    assert c.complete("fire all torpedoes at hy", ["Hydra", "Wraith"], [], []) == "fire all torpedoes at Hydra "
    assert c.complete("wo", [], ["Worf", "Spock"], []) == "Worf, "
    line = c.complete("sc", [], [], [])
    assert line == "sc" and "scan" in c.options          # several: shown, nothing chosen yet
    first = c.complete(line, [], [], [])
    assert first == c.options[0] + " "
    assert c.complete(first, [], [], []) == c.options[1] + " "


def test_preview_says_what_enter_would_do(duel) -> None:  # type: ignore[no-untyped-def]
    sc, surf = duel
    sc.console_focus = True
    sc.console = "helm 90 warp 3"
    assert sc.preview_text() == "Course 090, warp 3."
    sc.draw(surf)
    sc.console = "blorp"
    assert sc.preview_text() is None


# ------------------------------------------------------------ the command wheel


def test_the_wheel_has_eight_slices_and_runs_console_lines(duel) -> None:  # type: ignore[no-untyped-def]
    sc, surf = duel
    wheels = load_wheels()
    assert [s.label for s in wheels["enemy"]] == ["Phasers", "Torpedoes", "Disable", "Close to", "Hail", "Board",
                                                 "Elude", "Target"]
    sid = _enemy(sc)
    assert sc.open_wheel(sid, (500, 400))
    sc.draw(surf)
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_4, mod=0, unicode="4"))   # Close to
    assert sc.wheel is None
    assert f"> pursue {sc.ship_name(sid)}" in _texts(sc)
    p = sc.player
    assert p is not None and p.helm_target == sid


def test_a_ring_slice_opens_its_second_ring(duel) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel
    sid = _enemy(sc)
    sc.open_wheel(sid, (500, 400))
    w = sc.wheel
    assert isinstance(w, CommandWheel)
    assert w.key(2) == "stay" and w.sub == 2            # Disable: shields, weapons, engines, warp core
    pick = w.key(0)
    assert pick is not None and not isinstance(pick, str) and pick.line == "disable shields {ship}"


def test_right_click_steers_in_empty_space_and_opens_the_wheel_on_a_ship(duel) -> None:  # type: ignore[no-untyped-def]
    sc, surf = duel
    sc.draw(surf)
    p = sc.player
    assert p is not None
    x, y = sc.cam.to_screen(p.x + 4000, p.y)
    sc._right_click((int(x), int(y)))
    assert sc.wheel is None and round(p.desired_course) == 90
    sc.run_console("hud wheel off")
    sid = _enemy(sc)
    assert not sc.open_wheel(sid)


# ------------------------------------------------------------ proposals


def test_an_officer_proposes_a_target_and_y_makes_it_so(duel) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel
    sc.session.world.run(3.0)
    sc.obs = sc.session.world.observe(sc.session.side)
    p = sc.player
    assert p is not None and p.target is None
    props = candidates(sc.obs, p, sc.session.battle.crew.officers)
    tgt = [x for x in props if x.station == "tactical"]
    assert tgt and tgt[0].line.startswith("target ")
    sc.paused = False
    sc.session._propose_t = 0.0
    sc.session._proposals_tick(0.1)
    assert isinstance(sc.proposal, Proposal)
    line = sc.proposal.line
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_y, mod=0, unicode="y"))
    assert sc.proposal is None and f"> {line}" in _texts(sc)
    assert sc.session.career.points(tgt[0].officer) == 2


def test_proposals_are_rare_and_a_belayed_one_stays_quiet(duel) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel
    sc.session.world.run(3.0)
    obs = sc.session.world.observe(sc.session.side)
    p = sc.player
    officers = sc.session.battle.crew.officers
    pr = Proposer()
    first = pr.next(obs, p, officers, 10.0, "rarely", False)
    assert first is not None
    assert pr.next(obs, p, officers, 15.0, "rarely", False) is None      # too soon after the last
    pr.belay(first, 15.0)
    later = pr.next(obs, p, officers, 200.0, "rarely", False)
    assert later is None or later.line != first.line or 200.0 - 15.0 >= 120.0
    assert pr.next(obs, p, officers, 10.0, "off", False) is None
    assert Proposer().next(obs, p, officers, 10.0, "rarely", True) is None   # typing: only urgent ones


# ------------------------------------------------------------ alerts, recording, styles, trust


def test_alert_red_raises_shields_and_shows_the_condition(duel) -> None:  # type: ignore[no-untyped-def]
    sc, surf = duel
    sc.run_console("lower shields all")
    sc.run_console("alert red")
    p = sc.player
    assert sc.condition == "red" and p is not None and all(s.up for s in p.shields)
    sc.draw(surf)


def test_recording_saves_a_named_order(duel) -> None:  # type: ignore[no-untyped-def]
    sc, surf = duel
    sc.run_console("record strike one")
    assert sc.recording is not None and sc.recording.name == "strike-one"
    sc.run_console("helm 90 warp 4")
    sc.run_console("status")
    sc.run_console("raise shields all")
    sc.run_console("record stop")
    order = sc.session.orders.find("strike-one")
    assert order is not None and [s.text for s in order.steps] == ["helm 90 warp 4", "raise shields all"]
    sc.run_console("helm 10")
    sc.run_console("record last 1 as again")
    assert sc.session.orders.find("again") is not None
    sc.side_tabs.active = len(sc.side_tabs.tabs) - 1
    sc.draw(surf)


def test_tidy_drops_displays_and_keeps_pauses() -> None:
    steps = [(0.0, "helm 90"), (0.5, "helm 90"), (1.0, "status"), (5.0, "fire all phasers")]
    assert tidy(steps) == ["helm 90", "wait 5", "fire all phasers"]
    assert order_name("Strike One!", set()) == "strike-one"
    assert order_name("", {"alpha-1"}) == "bravo-1"


def test_a_style_is_promised_before_the_battle_and_broken_by_delegating(duel) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel
    sc.run_console("style chair")
    assert sc.style == "chair" and sc.style_broken is None
    sc.run_console("delegate helm")
    assert sc.style_broken is not None
    sc.session.world.run(5.0)
    sc.run_console("style iron")
    assert sc.style == "chair"                  # too late to change


def test_trust_levels_and_perks() -> None:
    store: dict[str, object] = {}
    c = Career(store)
    assert c.level("worf") == "Green" and level(30) == "Trusted"
    for _ in range(5):
        c.proposal("worf", accepted=True)
    assert c.level("worf") == "Steady" and c.take_risen() == [("worf", "Steady")]
    assert c.proposal_bonus("worf") > 0 and not c.acts_alone("worf")
    c.battle_won(["worf", "spock"], ["worf"], "worf")
    assert store["trust"]["worf"] == 17.0        # type: ignore[index]
    c.ribbon("iron")
    assert Career(store).ribbons == {"iron": 1}


def test_winning_keeping_a_style_earns_its_ribbon(duel) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel
    sc.run_console("style chair")
    sc.session.world.outcome.over = True
    sc.session.world.outcome.winner = sc.session.side
    sc.session._crew_outcome()
    assert sc.session.career.ribbons.get("chair") == 1 and sc.session.ribbon_won


# ------------------------------------------------------------ learned phrasing


def test_remembered_phrasing_runs_without_the_model(duel) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel
    sc.session.remember_phrase("Make a hard turn to port", ["helm 270"])
    sc.run_console("make a hard turn to port")
    p = sc.player
    assert p is not None and round(p.desired_course) == 270
    assert json.loads((__import__("begin.paths").paths.config_dir() / "phrasebook.json").read_text())


# ------------------------------------------------------------ voice


class _Whisper(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        n = int(self.headers["Content-Length"])
        body = self.rfile.read(n)
        ok = b'name="file"' in body and b"RIFF" in body
        out = json.dumps({"text": " Fire all phasers." if ok else ""}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a: object) -> None:
        pass


def test_whisper_server_engine_posts_the_recording() -> None:
    srv = HTTPServer(("127.0.0.1", 0), _Whisper)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    try:
        eng = WhisperServer(f"http://127.0.0.1:{srv.server_port}")
        assert eng.ready() is None
        assert eng.transcribe(to_wav(b"\0\0" * 8000), ["Hydra"]) == "Fire all phasers"
    finally:
        srv.shutdown()


def test_voice_settings_and_helpers() -> None:
    v = VoiceSettings.from_dict({"engine": "cloud", "key": "f13", "nonsense": 1, "model": 3})
    assert v.engine == "cloud" and v.key == "f13" and v.model == "base.en"
    assert VoiceSettings.from_dict({"engine": "telepathy"}).engine in ("mac", "whisper-server")
    body, ctype = multipart({"a": "1"}, b"RIFFxx")
    assert ctype.startswith("multipart/form-data; boundary=") and b'name="a"' in body and b"RIFFxx" in body
    assert clean(" Raise shields. [BLANK_AUDIO]") == "Raise shields"


def test_spoken_orders_run_and_misheard_ones_wait(duel) -> None:  # type: ignore[no-untyped-def]
    sc, surf = duel
    sc.spoken("helm 180 warp 2")
    p = sc.player
    assert p is not None and round(p.desired_course) == 180
    sc.spoken("blorp the flux")
    assert sc.console == "blorp the flux" and sc.console_focus
    sc.run_console("voice engine server")
    assert sc.voice_store["engine"] == "whisper-server"
    sc.run_console("voice")
    assert sc.overlay == "voice"
    sc.draw(surf)


def test_push_to_talk_records_and_hears(duel, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    sc, _ = duel

    class FakeRecorder:
        level = 0.5
        error = None

        def start(self) -> bool:
            return True

        def stop(self) -> bytes:
            return to_wav(b"\0\0" * 8000)

    class FakeEngine:
        def transcribe(self, wav: bytes, hints: list[str]) -> str:
            return "helm 45"

    monkeypatch.setattr("begin.ui.battle.voice.make_engine", lambda v: FakeEngine())
    sc.recorder = FakeRecorder()  # type: ignore[assignment]
    key = sc.ptt_key()
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=key, mod=0, unicode=""))
    assert sc.voice_state == "listening"
    sc.handle(pygame.event.Event(pygame.KEYUP, key=key, mod=0))
    for _ in range(100):
        sc.update(0.01)
        if sc.voice_state == "idle":
            break
    p = sc.player
    assert p is not None and round(p.desired_course) == 45
    assert any('heard: "helm 45"' in t for t in _texts(sc))
