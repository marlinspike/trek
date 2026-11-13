"""The showpiece Enterprise: baked sprites load, and menu flybys move, fire and draw."""

from __future__ import annotations

import math

import pygame

from begin.ui import showpiece
from begin.ui.showpiece import BAKED, Flybys, ship_image, sprite


def _display() -> pygame.Surface:
    pygame.init()
    return pygame.display.set_mode((1280, 800))


def test_every_baked_heading_loads() -> None:
    _display()
    for i in range(BAKED):
        img = sprite(i)
        assert img is not None and img.get_width() > 100 and img.get_height() > img.get_width()
    turned = ship_image(47.0, 0.5)
    assert turned is not None and turned.get_bounding_rect().width > 0


def test_a_flyby_crosses_fires_and_draws() -> None:
    surf = _display()
    played: list[str] = []
    f = Flybys(seed=3, sound=lambda name, level, pan: played.append(name))
    kinds: set[str] = set()
    for _ in range(12000):
        f.update(0.05, surf.get_size())
        kinds |= {s.kind for s in f.shots}
        if f.shots:
            surf.fill((0, 0, 0))
            f.draw(surf)
        if kinds == {"phaser", "torpedo"}:
            break
    assert kinds == {"phaser", "torpedo"} and {"phaser", "launch"} <= set(played)
    assert surf.get_bounding_rect().width > 0


def test_flybys_fall_back_quietly_without_sprites(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    surf = _display()
    showpiece.ship_image.cache_clear()
    monkeypatch.setattr(showpiece, "sprite", lambda i: None)
    try:
        f = Flybys(seed=5)
        for _ in range(400):
            f.update(0.05, surf.get_size())
            f.draw(surf)
    finally:
        showpiece.ship_image.cache_clear()


def test_each_pass_is_a_straight_line_at_one_heading() -> None:
    surf = _display()
    f = Flybys(seed=8)
    seen = 0
    while seen < 3:
        f.update(0.05, surf.get_size())
        p = f.current
        if p is None or p.t > 0.05:
            continue
        seen += 1
        pts = [p.at(u / 20) for u in range(21)]
        assert len({h for _, _, h in pts}) == 1                    # one heading, one sprite, all pass long
        (x0, y0, _), (x1, y1, _) = pts[0], pts[-1]
        for x, y, _ in pts:                                         # every point on the line from start to end
            assert abs((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) < 1e-6 * max(1.0, abs(x1 - x0) + abs(y1 - y0)) ** 2
        speed = math.hypot(x1 - x0, y1 - y0) / p.duration
        assert speed < 140                                          # a slow glide, in pixels a second


def test_torpedo_salvos_come_often_and_stay_in_view() -> None:
    surf = _display()
    w, h = surf.get_size()
    f = Flybys(seed=21)
    passes, salvos, seen = 0, 0, 0.0
    last = None
    while passes < 8:
        f.update(0.05, (w, h))
        if f.current is not None and f.current is not last:
            last = f.current
            passes += not f.current.foe                   # an enemy pass has its own fight instead
            salvos += any(kind == "torpedo" for _, kind, _ in f.current.fires)
        if any(s.kind == "torpedo" and s.trail and 0 <= s.pos[0] <= w and 0 <= s.pos[1] <= h for s in f.shots):
            seen += 0.05
    assert salvos >= 3                                  # firing passes take turns to lead with torpedoes
    assert seen >= 2.0                                  # and the torpedoes are on screen long enough to see


def test_symbols_fall_back_from_the_display_font() -> None:
    from begin.ui import theme

    _display()
    assert theme.render("QUICK BATTLE", theme.TEXT, 16, "display").get_width() > 0
    pause = theme.render("❚❚ Pause", theme.TEXT, 12, "display")
    assert pause.get_width() == theme.render("❚❚ Pause", theme.TEXT, 12, "ui").get_width()


def test_nav_lights_flash_and_engines_glow() -> None:
    from begin.ui.showpiece import NAV_FLASH, ship_lights

    _display()
    lit = []
    for t in (NAV_FLASH / 2, NAV_FLASH * 3):                  # mid-flash, then dark
        g = pygame.Surface((400, 400))
        g.fill((0, 0, 0))
        ship_lights(g, 200, 200, 0.0, 0.5, t)
        lit.append(sum(1 for x in range(0, 400, 2) for y in range(0, 400, 2) if max(g.get_at((x, y))[:3]) > 60))
    assert lit[1] > 0                                          # the engines glow all the time
    assert lit[0] > lit[1]                                     # and the nav lights add their flash


def test_a_klingon_decloaks_and_is_destroyed_on_a_distant_pass() -> None:
    surf = _display()
    f = Flybys(seed=4)
    f.encounter_odds = 1.0
    f.next_foe = "klingon"
    seen, boomed, scale = False, False, 1.0
    absorbed, wide, beams = False, False, False
    for _ in range(20 * 400):
        f.update(0.05, surf.get_size())
        e = f.encounter
        if e is not None:
            seen = True
            scale = e.scale
            boomed |= e.blast is not None and e.blast.t > 0.5
            absorbed |= any(fl.strength >= 1.0 for fl in e.her_flares)      # its torpedo on her shields
            beams |= any(fl.strength < 1.0 for fl in e.her_flares)          # its disruptors too
            wide |= any(b.wide and not b.done and b.trail for b in e.bolts)    # and one going wide
            f.draw(surf)
        elif seen:
            break
    assert seen and boomed and f.encounter is None              # it decloaked, blew up, and the scene cleared
    assert absorbed and beams and wide                          # it fired first, and her shields held
    assert scale <= 0.42 * 0.9 + 1e-9                          # only ever on a distant pass


def test_the_first_enemy_comes_early_and_k_summons_another() -> None:
    surf = _display()
    f = Flybys()
    t, first = 0.0, None
    while t < 30 and first is None:
        f.update(0.05, surf.get_size())
        t += 0.05
        if f.encounter is not None:
            first = t
    assert first is not None and first < 20                     # seen within seconds of the menu opening
    while f.encounter is not None:
        f.update(0.05, surf.get_size())
    f.summon()                                                   # K: her next pass meets a Klingon
    t = 0.0
    while t < 90 and f.encounter is None:
        f.update(0.05, surf.get_size())
        t += 0.05
    assert f.encounter is not None


def test_the_title_is_drawn_as_gold_lettering() -> None:
    from begin.ui import theme

    _display()
    art = theme.title_art("BEGIN", 84)
    box = art.get_bounding_rect()
    assert box.width > 250 and box.height > 50
    r, g, b, _ = art.get_at(box.center)
    assert r > b                                               # warm gold, not the old cyan


def _meet_the_cube(f: Flybys, size: tuple[int, int], limit: float = 120.0):  # type: ignore[no-untyped-def]
    from begin.ui.cube_battle import CubeBattle

    t = 0.0
    while t < limit:
        f.update(0.05, size)
        t += 0.05
        if isinstance(f.encounter, CubeBattle):
            return f.encounter
    return None


def test_a_borg_cube_comes_out_trades_salvos_and_is_destroyed() -> None:
    from begin.ui.cube_battle import CHAIN, CubeBattle

    surf = _display()
    w, h = surf.get_size()
    played: list[str] = []
    f = Flybys(seed=11, sound=lambda name, pan, level: played.append(name))
    f.summon("borg")
    cube = _meet_the_cube(f, (w, h))
    assert cube is not None
    assert cube.x - cube.side * 0.7 > 470 and cube.x + cube.side * 0.5 < w     # right of the menu, on screen
    cut_on_her = torp_on_her = adapted = failed = hull = boomed = False
    shield_flares = 0
    while f.encounter is cube:
        f.update(0.05, (w, h))
        cut_on_her |= any(fl.strength < 1.0 for fl in cube.her_flares)
        torp_on_her |= any(fl.strength >= 1.0 for fl in cube.her_flares)
        shield_flares = max(shield_flares, len(cube.flares))
        adapted |= cube.adapted_at is not None
        failed |= cube.shields_fail is not None
        hull |= cube.hull_hit is not None and len(cube.fires) >= 1
        boomed |= cube.blast is not None and cube.blast.t > 0.5
        f.draw(surf)
        assert cube.t < 30                                       # the whole fight is over well within a pass
    assert isinstance(cube, CubeBattle) and f.encounter is None   # it blew up and the scene cleared
    assert cut_on_her and torp_on_her                            # it cut at her and fired, and her shields held
    assert shield_flares >= 1 and adapted and failed and hull and boomed
    assert len(cube.fires) == 2 + len(CHAIN)                     # two rounds on the hull, then the fires inside
    assert {"hive", "cutter", "phaser", "launch", "collapse", "breakup"} <= set(played)


def test_the_borg_come_first_then_take_turns_with_the_klingon() -> None:
    from begin.ui.cube_battle import CubeBattle

    surf = _display()
    f = Flybys(seed=2)
    seen: list[str] = []
    last = None
    t = 0.0
    while len(seen) < 3 and t < 600:
        f.update(0.05, surf.get_size())
        t += 0.05
        if f.encounter is not None and f.encounter is not last:
            last = f.encounter
            seen.append("borg" if isinstance(f.encounter, CubeBattle) else "klingon")
    assert seen == ["borg", "klingon", "borg"]                 # the cube first, then turn about


def test_the_cube_fits_a_small_window() -> None:
    surf = _display()
    for seed in range(6):
        f = Flybys(seed=seed)
        f.summon("borg")
        cube = _meet_the_cube(f, (1024, 640))
        assert cube is not None
        assert cube.x - cube.side * 0.5 > 470 and cube.x + cube.side * 0.5 < 1024
        assert cube.side < 640 * 0.4
    assert surf is not None


def test_b_on_the_main_menu_summons_the_borg() -> None:
    from begin.content.loader import default_content
    from begin.settings import Settings
    from begin.ui.menu_scene import MenuScene

    _display()
    m = MenuScene(default_content(), Settings(), lambda setup: None, lambda: None)
    m.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_b, mod=0, unicode="b"))
    assert m.flybys.next_foe == "borg" and m.flybys.hurry
