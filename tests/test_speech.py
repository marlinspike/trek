"""The officers' spoken voices (2026-11-14): on by default, cast per officer, one voice at a time, and set from
Settings, the battle's Bridge voices page or `speak`. No real speech engine is ever started here."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass, field

import pytest

from begin.speech import CAST, OFFICERS, RACES, Speaker, SpeechSettings, VoiceInfo, cast_voice, choices, part_for, speakable
from begin.speech.engines import Espeak, MacSay, Spoken, parse_say_voices, sapi_rate, sapi_ssml
from begin.speech.casting import cast_all

MAC = [VoiceInfo(n, lang) for n, lang in (
    ("Albert", "en_US"), ("Daniel", "en_GB"), ("Fred", "en_US"), ("Karen", "en_AU"), ("Moira", "en_IE"),
    ("Ralph", "en_US"), ("Samantha", "en_US"), ("Reed (English (US))", "en_US"), ("Zarvox", "en_US"),
    ("Yuri", "ru_RU"), ("Milena", "ru_RU"), ("Thomas", "fr_FR"))]


@dataclass
class FakeEngine:
    kind: str = "mac"
    title: str = "Fake voices"
    took: float = 0.0
    spoken: list[Spoken] = field(default_factory=list)
    stops: int = 0
    _cut: threading.Event = field(default_factory=threading.Event)

    def problem(self) -> str | None:
        return None

    def voices(self) -> list[VoiceInfo]:
        return MAC

    def speak(self, line: Spoken) -> None:
        self.spoken.append(line)
        self._cut.clear()
        self._cut.wait(self.took)

    def stop(self) -> None:
        self.stops += 1
        self._cut.set()

    def close(self) -> None:
        self.stop()


def _wait(cond, seconds: float = 2.0) -> bool:  # type: ignore[no-untyped-def]
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return cond()


# ------------------------------------------------------------------ settings and casting

def test_voices_are_on_by_default_and_the_settings_say_what_is_spoken() -> None:
    s = SpeechSettings()
    assert s.enabled and s.speak == "all" and s.captains
    assert all(s.wants(k, False) for k in ("readback", "proposal", "report", "hail"))
    s.speak = "orders"
    assert s.wants("readback", False) and s.wants("proposal", False) and not s.wants("report", False)
    assert s.wants("report", True)                                       # warnings always
    s.speak = "urgent"
    assert not s.wants("readback", False) and s.wants("report", True)
    s.speak, s.captains = "all", False
    assert not s.wants("hail", False)
    s.enabled = False
    assert not s.wants("report", True)
    back = SpeechSettings.from_dict({"volume": 3, "rate": 9, "speak": "shout", "engine": "x", "cast": {"worf": "Fred"}})
    assert back.volume == 1.0 and back.rate == 1.4 and back.speak == "all" and back.engine == "auto"
    assert back.cast == {"worf": "Fred"}


def test_each_officer_is_cast_to_suit_the_part_from_what_the_computer_has() -> None:
    assert cast_voice("worf", "mac", MAC) == "Ralph"                       # deep
    assert cast_voice("doctor", "mac", MAC) == "Daniel"                    # brisk and British
    assert cast_voice("chekov", "mac", MAC) == "Yuri"                      # a Russian voice, when there is one
    assert cast_voice("computer", "mac", MAC) == "Samantha"
    assert cast_voice("spock", "mac", MAC) == "Reed (English (US))"
    seven = cast_voice("seven", "mac", MAC)
    assert seven in ("Samantha", "Karen", "Moira")                         # a woman's voice stands in
    assert cast_voice("worf", "mac", MAC, chosen="Fred") == "Fred"         # the player's choice wins
    assert cast_voice("worf", "mac", MAC, chosen="Gone") == "Ralph"        # ... while the computer still has it
    assert cast_voice("worf", "espeak", []) == CAST["worf"].espeak
    win = [VoiceInfo("Microsoft David Desktop", "en-US", False), VoiceInfo("Microsoft Zira Desktop", "en-US", True)]
    assert cast_voice("seven", "windows", win) == "Microsoft Zira Desktop"
    assert cast_voice("worf", "windows", win) == "Microsoft David Desktop"
    assert cast_voice("worf", "mac", []) is None                           # nothing at all: the engine's own default
    offered = choices("chekov", MAC)
    assert "Yuri" in offered and "Zarvox" not in offered and "Albert" not in offered and "Thomas" not in offered
    assert set(OFFICERS) | set(RACES) <= set(CAST)
    assert all(CAST[p].manner for p in CAST)


def test_no_two_officers_share_a_voice_while_there_are_enough() -> None:
    cast = cast_all("mac", MAC, {})
    assert cast["computer"] == "Samantha" and cast["seven"] == "Karen"     # a stock Mac: Seven isn't the computer
    officers = [cast[p] for p in OFFICERS]
    assert len(set(officers)) == len(officers) - 1    # four men's voices and Yuri for six men: one pair shares
    assert cast_all("mac", MAC, {"seven": "Samantha"})["computer"] != "Samantha"   # the player's choice comes first
    win = [VoiceInfo("Microsoft David Desktop", "en-US", False), VoiceInfo("Microsoft Zira Desktop", "en-US", True)]
    two = cast_all("windows", win, {})
    assert two["seven"] == two["computer"] == "Microsoft Zira Desktop"     # one woman's voice: shared, pitch apart
    assert CAST["seven"].pitch != CAST["computer"].pitch or CAST["seven"].rate != CAST["computer"].rate


def test_who_speaks_a_line() -> None:
    assert part_for("worf") == "worf"
    assert part_for(None) == "computer"
    assert part_for(None, "klingon") == "klingon"
    assert part_for(None, "ferengi") == "captain"


def test_lines_are_cleaned_for_the_ear() -> None:
    assert speakable("Spock: Torpedo inbound, Captain. Evasive manoeuvres? (Y makes it so, N belays)") == \
        "Spock: Torpedo inbound, Captain. Evasive manoeuvres?"
    assert speakable("Firing all phasers at the Sandstorm (FR) › #12 at 13,088 units.") == \
        "Firing all phasers at the Sandstorm contact 12 at 13088 units."


# ------------------------------------------------------------------ the engines' command lines

def test_the_engines_are_asked_in_their_own_terms(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    voices = parse_say_voices("Daniel              en_GB    # Hello! My name is Daniel.\n"
                              "Reed (English (US)) en_US    # Hello! My name is Reed.\nnot a voice\n")
    assert [(v.name, v.lang) for v in voices] == [("Daniel", "en_GB"), ("Reed (English (US))", "en_US")]
    ran: list[list[str]] = []
    from begin.speech import engines

    monkeypatch.setattr(engines._Process, "run", lambda self, args, stdin=None: ran.append(args))
    MacSay().speak(Spoken("Aye, Captain.", "Ralph", 0.9, 0.72, 0.5))
    assert ran[-1][:5] == ["say", "-r", "166", "-v", "Ralph"]
    assert ran[-1][-1].startswith("[[volm 0.50]] [[pbas 35]]") and ran[-1][-1].endswith("Aye, Captain.")
    monkeypatch.setattr(Espeak, "program", staticmethod(lambda: "espeak-ng"))
    Espeak().speak(Spoken("Aye.", "en-us+m1", 1.0, 0.72, 0.8))
    assert ran[-1] == ["espeak-ng", "-s", "185", "-p", "36", "-a", "120", "-v", "en-us+m1", "--", "Aye."]
    assert sapi_rate(1.0) == 0 and sapi_rate(1.3) == 3 and sapi_rate(3.0) == 10
    assert 'pitch="-28%"' in sapi_ssml("A & B", 0.72) and "A &amp; B" in sapi_ssml("A & B", 0.72)


def test_no_engine_speaks_when_speech_is_off_in_the_environment(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    from begin.speech.engines import Silent, make_engine

    assert isinstance(make_engine("off"), Silent)
    monkeypatch.setenv("BEGIN_SPEECH", "off")
    assert isinstance(make_engine("auto"), Silent) and isinstance(make_engine("system"), Silent)


# ------------------------------------------------------------------ one voice at a time

def test_one_voice_at_a_time_warnings_first_and_stale_lines_dropped() -> None:
    eng = FakeEngine(took=0.3)
    sp = Speaker({}, engine=eng)
    assert sp.say("Course 090, warp 6.", "sulu", kind="readback")
    assert _wait(lambda: len(eng.spoken) == 1)
    for i in range(4):
        sp.say(f"Routine {i}.", "geordi")
    sp.say("Hull breach on deck four!", "worf", urgent=True)
    assert _wait(lambda: eng.stops >= 1)                    # the warning cut the routine line short
    assert _wait(lambda: len(eng.spoken) >= 2)
    assert eng.spoken[1].text == "Hull breach on deck four!" and eng.spoken[1].voice == "Ralph"
    assert _wait(lambda: len(eng.spoken) == 4, 3.0)
    assert [x.text for x in eng.spoken[2:]] == ["Routine 2.", "Routine 3."]   # the older routine ones were dropped
    sp.close()


def test_answers_outlast_remarks_repeats_are_said_once_and_old_warnings_lapse() -> None:
    eng = FakeEngine(took=0.4)
    sp = Speaker({}, engine=eng)
    sp.say("First.", "spock")
    assert _wait(lambda: len(eng.spoken) == 1)
    sp.say("Warp 6.", "sulu", kind="readback")
    sp.say("Warp 6.", "sulu", kind="readback")              # said twice in a breath: heard once
    sp.say("A remark.", "geordi")
    sp.say("Another remark.", "geordi")                      # the queue is full: a remark goes, not the answer
    assert _wait(lambda: len(eng.spoken) == 3, 3.0)
    assert [x.text for x in eng.spoken[1:]] == ["Warp 6.", "Another remark."]
    for i in range(4):
        sp.say(f"Warning {i}!", "worf", urgent=True)
    assert _wait(lambda: len(eng.spoken) >= 5, 4.0)
    time.sleep(0.6)
    warned = [x.text for x in eng.spoken if x.text.startswith("Warning")]
    assert len(warned) <= 3 and "Warning 3!" in warned          # the newest, not a backlog of four
    sp.close()


def test_a_cut_that_lands_before_the_engine_starts_is_not_lost() -> None:
    class Late(FakeEngine):
        def speak(self, line: Spoken) -> None:
            time.sleep(0.08)                                 # the process is still starting when the cut comes
            super().speak(line)

    eng = Late(took=2.0)
    sp = Speaker({}, engine=eng)
    sp.say("A long routine report about nothing in particular.", "spock")
    time.sleep(0.02)
    sp.say("Incoming torpedoes!", "worf", urgent=True)
    assert _wait(lambda: any(x.text == "Incoming torpedoes!" for x in eng.spoken), 1.5)
    sp.close()


def test_figures_and_noughts_are_for_the_eye_only() -> None:
    assert speakable("Target out of phaser range (12,467 > 2,000).") == "Target out of phaser range."
    assert speakable("Course 202, warp 4.0 of 9.5 attainable.") == "Course 202, warp 4 of 9.5 attainable."
    assert speakable("Fire on #3 (Y makes it so, N belays)") == "Fire on contact 3"
    from begin.speech.engines import ESPEAK_VOICES

    assert {c.espeak for c in CAST.values()} <= set(ESPEAK_VOICES)   # Settings offers every voice the cast uses


def test_the_settings_decide_what_is_said_and_how() -> None:
    eng = FakeEngine()
    store: dict[str, object] = {"speak": "urgent", "volume": 0.4, "rate": 1.2}
    sp = Speaker(store, engine=eng)
    assert not sp.say("Course 090.", "sulu", kind="readback")
    assert sp.say("Shields failing!", "worf", urgent=True)
    assert _wait(lambda: len(eng.spoken) == 1)
    line = eng.spoken[0]
    assert line.volume == 0.4 and line.rate == pytest.approx(CAST["worf"].rate * 1.2) and line.pitch == CAST["worf"].pitch
    store.update({"enabled": False})
    assert not sp.say("Shields failing!", "worf", urgent=True)
    store.update({"enabled": True, "speak": "all", "cast": {"worf": "Fred"}})
    sp.hear("worf")
    assert _wait(lambda: len(eng.spoken) == 2) and eng.spoken[1].voice == "Fred"
    sp.close()


# ------------------------------------------------------------------ in battle and in Settings

pygame = pytest.importorskip("pygame")


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame.init()
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui.battle_scene import BattleScene

    eng = FakeEngine()
    sp = Speaker({}, engine=eng)
    p = {x.id: x for x in load_presets()}["border-incident"]
    sc = BattleScene(build_battle(content, p.setup()), (1280, 800), lambda: None, speaker=sp)
    sc.audio.muted = False
    yield sc, sp, eng
    sp.close()


def test_the_bridge_speaks_its_readbacks_proposals_and_warnings(scene) -> None:  # type: ignore[no-untyped-def]
    sc, sp, eng = scene
    sc.run_console("warp 6")
    sc.update(0.05)
    assert _wait(lambda: any("6" in x.text for x in eng.spoken))
    from begin.crew.proposals import Proposal

    sc.session.proposal = Proposal("worf", "Worf", "tactical", "Their shields are down. Fire all phasers?", "fire all phasers")
    sc.update(0.05)
    assert _wait(lambda: any("Their shields are down" in x.text for x in eng.spoken))
    assert any(part == "worf" for part, _ in sp.said)
    from begin.ui import theme

    sc.toast = ("Unable to comply: no torpedoes left.", theme.CAUTION, 2.0)
    sc.update(0.05)
    assert _wait(lambda: any("Unable to comply" in x.text for x in eng.spoken))
    n = len(eng.spoken)
    sc.audio.muted = True                     # M hushes the bridge too
    sc.run_console("warp 4")
    sc.update(0.05)
    time.sleep(0.1)
    assert len(eng.spoken) == n


def test_speak_sets_the_voices_from_the_console(scene) -> None:  # type: ignore[no-untyped-def]
    sc, sp, eng = scene
    sc.run_console("speak orders")
    sc.update(0.01)
    assert sp.settings.speak == "orders"
    sc.run_console("speak volume 50")
    sc.run_console("speak rate 120")
    sc.update(0.01)
    assert sp.settings.volume == 0.5 and sp.settings.rate == 1.2
    sc.run_console("speak off")
    sc.update(0.01)
    assert not sp.settings.enabled
    sc.run_console("speak")
    sc.update(0.01)
    assert sc.overlay == "speech"
    sc.run_console("speak on")
    sc.run_console("speak hear chekov")
    sc.update(0.01)
    assert _wait(lambda: any(v.voice == "Yuri" for v in eng.spoken))


def test_the_bridge_voices_page_and_the_settings_section_draw_clear(scene, content) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui import theme
    from begin.ui.menu_scene import MenuScene
    from tests.test_calm_screens import collisions

    sc, sp, _ = scene
    for size in ((1024, 640), (1280, 800), (1920, 1080)):
        surf = pygame.display.set_mode(size)
        sc.layout(size)
        sc.overlay = "speech"
        with theme.watching() as ink:
            sc.draw(surf)
        modal = [k.rect for k in ink if k.kind == "panel" and k.rect.width >= 400]
        page = modal[-1]
        inside = [k for k in ink if k.kind == "panel" or page.contains(k.rect)]
        assert not collisions(inside, surf), (size, collisions(inside, surf))
        assert any(k.text.lower() == "bridge voices" for k in ink)
        m = MenuScene(content, Settings(), lambda s: None, lambda: None, speaker=sp)
        m.open_settings()
        m.hub.go("speech")
        with theme.watching() as ink:
            m.draw(surf)
        assert not collisions(ink, surf), (size, collisions(ink, surf))
        assert any("Who sounds like whom".upper() in k.text for k in ink)


def test_the_battle_menu_opens_the_bridge_voices_page(scene) -> None:  # type: ignore[no-untyped-def]
    from begin.ui import theme

    sc, _, _ = scene
    surf = pygame.display.set_mode((1280, 800))
    sc.overlay = "menu"
    with theme.watching() as ink:
        sc.draw(surf)
    box = next(k.rect for k in ink if k.text == "Bridge voices")
    h = sc.ui.hit(box.center)
    assert h is not None
    h.action()
    assert sc.overlay == "speech"


def test_the_speech_package_never_touches_pygame() -> None:
    import ast
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "src" / "begin" / "speech"
    for f in root.glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
        names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
        assert not any(n.startswith("pygame") for n in names), f.name
