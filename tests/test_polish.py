"""The finish: effects that follow the battle, synthesised sound, and the end-of-battle review."""

from __future__ import annotations

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.crew.characters import load_officers
from begin.crew.review import standout
from begin.presets import load_presets
from begin.sim.commands import Authority, SetHelm
from begin.sim.events import Detonation, ObjectiveEnded
from begin.sim.world import LoggedCommand
from begin.ui import audio, theme
from begin.ui.effects import Effects


def test_a_ship_breaking_up_leaves_shards_and_embers_and_damaged_ships_spark() -> None:
    fx = Effects()
    fx.ingest([Detonation(0, 0.0, 0.0, 1200.0, "ship", 500.0, owner=None)], 0, set(), set())
    assert fx.debris and fx.embers and fx.glows
    fx.update(1.0)
    assert fx.embers and not fx.glows            # the flash is gone; embers linger
    fx.update(3.0)
    assert not fx.debris and not fx.embers
    for _ in range(200):
        fx.smoulder(0.0, 0.0, 0.1, 1 / 60, 0.05)
    assert 5 < len(fx.sparks) < 80


def test_every_sound_is_made_without_clipping() -> None:
    makers = list(audio.SOUNDS.items()) + [(f"{n}-{v}", f) for n, vs in audio.VARIANTS.items() for v, f in vs.items()]
    for name, make in makers:
        x = make()
        assert len(x) > 1000, name
        peak = max(abs(v) for v in x)
        assert 3000 < peak < 32767, (name, peak)


def test_versions_and_the_players_own_sounds(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:  # type: ignore[no-untyped-def]
    folder = tmp_path / "sounds"
    folder.mkdir()
    audio.write_wav(folder / "Torpedo.wav", audio.launch_b())
    (folder / "notes.txt").write_text("not a sound")
    (folder / "warp.wav").write_bytes(b"")                 # not one of the game's sounds: ignored
    assert audio.own_sounds(folder) == {"launch": folder / "Torpedo.wav"}
    assert audio.own_sounds(tmp_path / "missing") == {}

    made: list[object] = []
    monkeypatch.setattr(pygame.mixer, "get_init", lambda: (22050, -16, 2))
    monkeypatch.setattr(pygame.mixer, "set_num_channels", lambda n: None)
    monkeypatch.setattr(pygame.mixer, "Sound", lambda *a, **k: made.append(k.get("buffer") or a[0]) or str(len(made)))
    a = audio.Audio(0.5, choice={"phaser": "c", "torpedo": "b", "shield": "z"}, folder=folder)
    assert a.choice == {"phaser": "c", "launch": "b"} and a.own == {"launch": folder / "Torpedo.wav"}
    assert str(folder / "Torpedo.wav") in made                       # the player's file replaced the launch
    assert audio._samples("phaser", True, "c") in made
    a.choose("phaser", "b")
    assert made[-1] == audio._samples("phaser", True, "b")
    a.choose("torpedo", "a")                                         # remembered, but their own file still plays
    assert a.settings() == {"phaser": "b", "torpedo": "a"} and made[-1] == audio._samples("phaser", True, "b")


def test_without_a_device_the_battle_is_silent_and_never_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_device(*a: object, **k: object) -> None:
        raise pygame.error("no audio device")

    monkeypatch.setattr(pygame.mixer, "get_init", lambda: None)
    monkeypatch.setattr(pygame.mixer, "init", no_device)
    a = audio.Audio(0.5)
    assert not a.available
    a.play("phaser", 0.0)
    a.events([Detonation(0, 0.0, 0.0, 100.0, "torpedo", 10.0)], 0.0, lambda x, y: (0.0, 1.0), set(),
             lambda sid: "beam", lambda sid: None)


class _Channel:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def set_volume(self, left: float, right: float) -> None:
        self.log.append(f"vol {left:.2f} {right:.2f}")

    def play(self, snd: object) -> None:
        self.log.append(f"play {snd}")


def test_sounds_are_panned_and_never_stack(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    monkeypatch.setattr(pygame.mixer, "find_channel", lambda: _Channel(log))
    a = audio.Audio.__new__(audio.Audio)
    a.volume, a.muted, a._last = 0.5, False, {}
    a.sounds = {"phaser": "PHASER", "blast": "BLAST"}     # type: ignore[dict-item]
    a.play("phaser", 1.0, pan=0.8)
    a.play("phaser", 1.01)                               # too soon after the last: dropped
    a.play("blast", 1.01)
    assert log == ["vol 0.10 0.50", "play PHASER", "vol 0.50 0.50", "play BLAST"]
    a.muted = True
    a.play("blast", 5.0)
    assert len(log) == 4


def test_sound_commands(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    ctx = ParseContext(b.player_ship_id, b.world.observe(0))
    assert parse("sound off", ctx).actions == [("sound", "off")]
    assert parse("volume 40", ctx).actions == [("sound", 40.0)]
    assert parse("mute", ctx).actions == [("sound", "off")]
    assert parse("sound loud", ctx).error is not None
    assert parse("sound phaser b", ctx).actions == [("sound", ("phaser", "b"))]
    assert parse("sound torpedoes", ctx).actions == [("sound", ("torpedo", None))]
    assert parse("sound torpedo z", ctx).error is not None
    assert parse("sound phaser d", ctx).actions == [("sound", ("phaser", "d"))]


def test_the_standout_officer_is_the_one_who_did_most() -> None:
    officers = load_officers()
    worf, spock = officers["worf"], officers["spock"]
    log = [LoggedCommand(5, SetHelm(ship_id=1, course=90.0, issuer=Authority.OFFICER, source=worf.title), True)
           for _ in range(4)]
    log += [LoggedCommand(5, SetHelm(ship_id=2, course=90.0, source=spock.title), True)] * 9   # another ship
    log += [LoggedCommand(5, SetHelm(ship_id=1, course=90.0, source=spock.title), False)] * 9  # refused
    best = standout(officers.values(), 1, log, [])
    assert best is not None and best.officer.id == "worf" and best.orders == 4
    assert "kept the weapons on target: 4 orders carried out" in best.line()
    done = [ObjectiveEnded(9, 1, "spock", "cripple", "g", (2,), "done")]
    best = standout(officers.values(), 1, log, done)
    assert best is not None and best.officer.id == "spock" and best.objectives == 1
    assert standout(officers.values(), 1, [], []) is None


def test_the_end_screen_and_red_alert_draw(content) -> None:  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
    me = sc.player
    enemy = next(s for s in b.world.ships.values() if s.id != me.id)
    enemy.x, enemy.y = me.x + 3000, me.y
    assert sc._red_alert() > 0
    sc.overlay = None
    sc.paused = False
    for _ in range(30):
        sc.update(0.05)
        sc.draw(surf)
    assert theme.border() == theme.BORDER      # the tint is only for the battle's own panels
    b.world.destroy_ship(enemy, "test", me.id)
    sc.update(0.05)
    sc.overlay = "debrief"
    sc.draw(surf)
    sc.run_console("sound 30")
    assert sc.audio.volume == pytest.approx(0.3)
    sc.run_console("sound torpedo c")
    assert sc.audio.choice.get("launch") == "c" and "version c" in sc.log[-1].text
    sc.close()


def test_hud_numbers_ease_and_flash_and_detail_is_on_request(content) -> None:  # type: ignore[no-untyped-def]
    from begin.ui.tween import Tweens

    tw = Tweens()
    assert tw.get("hull", 100.0) == 100.0
    assert tw.get("hull", 80.0) == 100.0                    # shown value starts where it was...
    assert tw.colour("hull", (10, 10, 10)) != (10, 10, 10)  # ...lit up for the change
    for _ in range(60):
        tw.update(1 / 60)
    assert abs(tw.get("hull", 80.0) - 80.0) < 0.1 and tw.colour("hull", (10, 10, 10)) == (10, 10, 10)
    tw.get("crew", 400.0)
    tw.get("crew", 399.8)                                   # a tiny drift doesn't flash
    assert tw.colour("crew", (10, 10, 10)) == (10, 10, 10)

    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    ctx = ParseContext(b.player_ship_id, b.world.observe(0))
    assert parse("hud detail", ctx).actions == [("hud", "detail")]
    assert parse("hud simple", ctx).actions == [("hud", "simple")]
    assert parse("hud", ctx).actions == [("hud", None)]
    assert parse("hud loud", ctx).error is not None


def test_torpedoes_leave_trails_and_the_lock_closes_in(content) -> None:  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
    me = sc.player
    enemy = next(s for s in b.world.ships.values() if s.id != me.id)
    sc.overlay, sc.paused = None, False
    for _ in range(120):                                    # let the tubes load
        sc.update(0.05)
    enemy.x, enemy.y = me.x + 2000, me.y + 3000             # far enough that the torpedoes fly a while
    sc.run_console(f"target #{enemy.id}")
    sc.run_console("fire all torpedoes")
    sc.overlay = None
    sc.draw(surf)
    assert sc.view._lock[0] == enemy.id
    for _ in range(8):
        sc.update(0.05)
        sc.overlay = None
        sc.draw(surf)
    assert sc.view.torp_trails and max(len(v) for v in sc.view.torp_trails.values()) >= 3
    sc.run_console("hud detail")
    assert sc.hud_detail and "every number" in sc.log[-1].text
    sc.draw(surf)
    sc.close()
