"""The weapons overhaul: beams that charge, travel and land where the blow really landed, torpedoes drawn by
race, inbound rounds marked, hits and shield collapses felt, and the new sounds."""

from __future__ import annotations

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.content.loader import ContentError, _weapon_colors
from begin.presets import load_presets
from begin.sim.events import HullHit, PhaserFired, ShieldHit, SubsystemDamaged, TorpedoLaunched
from begin.ui import audio
from begin.ui.beams import CHARGE, REACH, Beam, Stop
from begin.ui.camera import Camera
from begin.ui.effects import Effects
from begin.ui.torpedo_art import draw_round, round_size


def _shot(defensive: bool = False, power: float = 1.0) -> PhaserFired:
    return PhaserFired(0, 1, 2, (0.0, 0.0), 90.0, 20.0, 2000.0, [2], (1500.0, 0.0), defensive=defensive, power=power)


def _bodies(sid: int | None) -> tuple[float, float, float] | None:
    return {1: (0.0, 0.0, 300.0), 2: (1500.0, 0.0, 300.0)}.get(sid) if sid is not None else None


def test_a_beam_charges_then_reaches_then_fades() -> None:
    b = Beam(0, 0, 1000, 0, 20.0, (255, 160, 80), power=1.0)
    charge, arrive, tail, gone = b.timeline()
    assert charge == pytest.approx(CHARGE) and arrive == pytest.approx(CHARGE + REACH) and charge < arrive < tail < gone
    assert b.life == pytest.approx(gone)
    weak = Beam(0, 0, 1000, 0, 20.0, (255, 160, 80), power=0.3)
    assert weak.timeline()[2] - weak.timeline()[1] < tail - arrive        # a weak shot holds for less
    assert weak.weight < b.weight
    pd = Beam(0, 0, 1000, 0, 20.0, (255, 160, 80), defensive=True)
    assert pd.timeline()[0] == 0.0 and pd.weight < weak.weight            # point defence: no charge, thin
    bolts = Beam(0, 0, 1000, 0, 20.0, (98, 232, 90), style="pulse", power=1.0)
    assert bolts.bolts == 3 and bolts.arrives > 0


def test_a_beam_stops_on_the_shield_or_reaches_the_hull() -> None:
    cam = Camera(pygame.Rect(0, 0, 800, 600), zoom=0.2)
    on_shield = Beam(-1000, 0, 0, 0, 20.0, (255, 160, 80), stop=Stop(0, 0, 300, True))
    through = Beam(-1000, 0, 0, 0, 20.0, (255, 160, 80), stop=Stop(0, 0, 300, False))
    (_, e1), (_, e2) = on_shield.endpoints(cam), through.endpoints(cam)
    centre = cam.to_screen(0, 0)
    assert centre[0] - e1[0] > centre[0] - e2[0] > 0      # the shield stops it further out than the hull


def test_shots_land_on_the_shield_unless_they_get_through(content) -> None:  # type: ignore[no-untyped-def]
    fed = content.factions["federation"]
    held = [ShieldHit(0, 2, 0, 12.0, 0.0, False, attacker=1, strength=80.0), _shot()]
    fx = Effects()
    fx.ingest(held, 0, {1, 2}, {1}, lambda sid: fed, _bodies)
    (beam,) = fx.beams
    assert beam.stop is not None and beam.stop.on_shield and beam.power == 1.0
    assert fx.landing[(1, 2)] == pytest.approx(beam.arrives)            # its blow is shown when it gets there
    broke = [ShieldHit(0, 2, 0, 4.0, 9.0, False, attacker=1), HullHit(0, 2, 9.0, 3, 1), _shot()]
    fx = Effects()
    fx.ingest(broke, 0, {1, 2}, {1}, lambda sid: fed, _bodies)
    assert fx.beams[0].stop is not None and not fx.beams[0].stop.on_shield
    assert fx.vents and all(v.delay >= fx.landing[(1, 2)] for v in fx.vents)    # the breach vents after the beam lands
    for _ in range(14):                                                  # just after it lands (0.19 s)
        fx.update(1 / 60)
    assert fx.sparks                                                      # sparks thrown where it landed


def test_launches_and_system_hits_flash(content) -> None:  # type: ignore[no-untyped-def]
    fx = Effects()
    fx.ingest([TorpedoLaunched(0, 1, 7, 0, 1, "mk7"), SubsystemDamaged(0, 2, "w1", "warp core", 30, False, False)],
              0, {1, 2}, {1}, lambda sid: content.factions["federation"], _bodies)
    assert len(fx.flashes) == 2 and fx.flashes[1].delay > 0


def test_each_race_has_a_torpedo_look(content) -> None:  # type: ignore[no-untyped-def]
    styles = {f.id: f.torpedo_style for f in content.factions.values()}
    assert styles["federation"] == "photon" and styles["klingon"] == "disruptor" and styles["romulan"] == "plasma"
    with pytest.raises(ContentError):
        _weapon_colors({"id": "x", "colors": {"torpedo_style": "laser"}})
    assert round_size(21.6, 0.05) > round_size(14.4, 0.05) >= 3.0           # a heavier warhead, a bigger star
    assert round_size(14.4, 0.6) > round_size(14.4, 0.05)
    surf = pygame.Surface((80, 80))
    over = pygame.Surface((80, 80), pygame.SRCALPHA)
    for style in ("photon", "disruptor", "plasma", "pulse"):
        surf.fill((0, 0, 0))
        draw_round(surf, over, 40, 40, 45.0, (255, 94, 58), style, 5.0, 0.3, 1)
        assert surf.get_at((40, 40))[:3] != (0, 0, 0), style


def test_inbound_rounds_are_marked_and_heard_once(content) -> None:  # type: ignore[no-untyped-def]
    from begin.ui.tactical import TacticalView

    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    obs = b.world.observe(0)
    me = obs.own(b.player_ship_id)
    assert me is not None
    toward = TacticalView._inbound(obs, (me.x, me.y + 3000.0, 180.0))
    away = TacticalView._inbound(obs, (me.x, me.y + 3000.0, 0.0))
    assert toward == pytest.approx(3000.0, abs=1.0) and away is None


def test_a_heavy_blow_on_our_ship_jolts_the_map(content) -> None:  # type: ignore[no-untyped-def]
    from begin.ui.tactical import TacticalView

    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    view = TacticalView(Camera(pygame.Rect(0, 0, 800, 600)))
    view._player = b.player_ship_id
    obs = b.world.observe(0)
    view.ingest([HullHit(0, b.player_ship_id, 40.0, 10, None)], obs)
    view.update(1 / 60)
    assert view._shake > 2.0
    view.update(1.0)
    assert view._shake < 0.3


def test_new_sound_and_jolt_commands(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    ctx = ParseContext(b.player_ship_id, b.world.observe(0))
    assert parse("sound hum off", ctx).actions == [("sound", ("hum", 0.0))]
    assert parse("sound hum 50", ctx).actions == [("sound", ("hum", 0.5))]
    assert parse("sound hum", ctx).actions == [("sound", ("hum", None))]
    assert parse("hud jolt off", ctx).actions == [("hud", "jolt off")]
    assert parse("hud jolt maybe", ctx).error is not None


class _Ch:
    def __init__(self, log: list[str]) -> None:
        self.log = log

    def set_volume(self, *v: float) -> None:
        pass

    def play(self, snd: object) -> None:
        self.log.append(str(snd))


def _quiet_audio(monkeypatch: pytest.MonkeyPatch, log: list[str]) -> audio.Audio:
    monkeypatch.setattr(pygame.mixer, "find_channel", lambda: _Ch(log))
    a = audio.Audio.__new__(audio.Audio)
    a.volume, a.muted, a._last, a._later, a._duck, a._drive, a.hum = 0.5, False, {}, [], 0.0, 0.0, 0.0
    a._hum_ch = None
    a.sounds = {"phaser": "PHASER", "phaser~": "PHASER-FAR", "hull": "HULL", "shield": "SHIELD",   # type: ignore[dict-item]
                "launch": "LAUNCH", "thunk": "THUNK", "collapse": "COLLAPSE"}
    return a


def test_far_sounds_are_muffled_and_blows_wait_for_the_beam(monkeypatch: pytest.MonkeyPatch) -> None:
    log: list[str] = []
    a = _quiet_audio(monkeypatch, log)
    a.play("phaser", 1.0, 0.0, 0.9)
    a.play("phaser", 2.0, 0.0, 0.2)
    assert log == ["PHASER", "PHASER-FAR"]
    log.clear()
    events = [ShieldHit(0, 2, 0, 5.0, 0.0, True, attacker=1), HullHit(0, 2, 12.0, 4, 1), TorpedoLaunched(0, 1, 9, 0, 1, "mk7")]
    a.events(events, 10.0, lambda x, y: (0.0, 0.8), {1, 2}, lambda sid: "beam", lambda sid: (0.0, 0.0), {(1, 2): 0.2})
    assert log == ["LAUNCH", "THUNK"]                 # the launch at once; the blows when the beam lands
    a.tick(10.1)
    assert log == ["LAUNCH", "THUNK"]
    a.tick(10.25)
    assert log == ["LAUNCH", "THUNK", "COLLAPSE", "HULL"]


def test_the_alert_is_three_whoops_and_the_hum_loops_cleanly() -> None:
    whoops = audio.alert()
    assert len(whoops) == pytest.approx(audio.RATE * 0.62 * 3, abs=2)
    hum = audio.hum()
    assert len(hum) == int(audio.RATE * audio.HUM_SECONDS)
    assert abs(hum[0] - hum[-1]) < 2500                 # the loop's ends meet without a click
