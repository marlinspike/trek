"""Split fire [E]: some tubes or banks on one ship and the rest on another, by the captain's words or the
tactical officer's judgement ("engage the Zantha and the Bismark"), shown calmly in the Weapons panel."""

from __future__ import annotations

import pytest

from begin.ai.computer import ShipComputer
from begin.console.parser import ParseContext, parse
from begin.console.plain import plain_order, split_line
from begin.console.readback import readback, runs, split_words
from begin.crew.objectives import Planner, plan_engage
from begin.crew.split_fire import divide, worth_splitting
from begin.sim.commands import (
    EndObjective, FireTorpedoes, SelectTarget, SetFireMode, SetObjective, SplitFire, split_locks,
)
from begin.sim.objectives import ENGAGE_GROUP
from begin.sim.ship import FireMode

from .conftest import charge_all, make_world


@pytest.fixture()
def duel(content):  # type: ignore[no-untyped-def]
    """The Enterprise (a Dreadnought: 6 banks, 8 tubes) with two Klingons ahead of her."""
    w = make_world(content)
    me = w.add_ship("federation.dn", 0, 0, 0, name="Enterprise")
    zantha = w.add_ship("klingon.bc", 1, -2500, 7000, name="Zantha")
    bismark = w.add_ship("klingon.fr", 1, 2500, 7000, name="Bismark")
    w.step()
    return w, me, zantha, bismark


def run(w, me, text):  # type: ignore[no-untyped-def]
    r = parse(text, ParseContext(me.id, w.observe(0)))
    assert r.error is None, f"{text!r}: {r.error}"
    return r


def only(r, cls):  # type: ignore[no-untyped-def]
    found = [c for c in r.commands if isinstance(c, cls)]
    assert len(found) == 1, r.commands
    return found[0]


# ------------------------------------------------------------------ words

def test_runs_and_split_words_read_as_a_captain_counts() -> None:
    assert runs([0, 1, 2, 3]) == "1-4"
    assert runs([0, 1]) == "1 and 2"
    assert runs([0, 1, 4]) == "1, 2 and 5"
    names = {2: "Zantha", 3: "Bismark"}.__getitem__
    assert split_words({2: (0, 1)}, {2: (0, 1, 2, 3), 3: (4, 5, 6, 7)}, names) == \
        "Tubes 1-4 on the Zantha, 5-8 on the Bismark; phasers on the Zantha."
    assert split_words({}, {3: (0, 1)}, names) == "Tubes on the Bismark."


@pytest.mark.parametrize("line, words", [
    ("torpedoes 1 through 4 on the zantha and the rest on the bismark", "split"),
    ("target tubes 1,2 on the zantha, the rest on the bismark", "split"),
    ("fire tubes 1-4 at the zantha and 5-8 at the bismark", "split"),
    ("fight both the zantha and the bismark", "engage"),
    ("take on the zantha and the bismark", "engage"),
    ("phasers on the zantha and torpedoes on the bismark", "split"),
])
def test_plain_english_becomes_a_split_or_an_engage(line: str, words: str) -> None:
    out = split_line(line)
    assert out is not None and out.split()[0] == words, out
    assert plain_order(line).split()[0] == words


@pytest.mark.parametrize("line", ["attack the zantha", "attack the zantha and pursue her", "engage off",
                                  "hit their shields and their engines", "fire all torpedoes"])
def test_ordinary_orders_are_not_mistaken_for_a_split(line: str) -> None:
    assert split_line(line) is None


# ------------------------------------------------------------------ the console

def test_split_tubes_by_number_and_the_rest(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    cmd = only(run(w, me, "split tubes 1-4 on zantha, rest on bismark, phasers on zantha"), SplitFire)
    assert dict(cmd.tubes) == {z.id: (0, 1, 2, 3), b.id: (4, 5, 6, 7)}
    assert dict(cmd.banks) == {z.id: tuple(range(len(me.banks)))}
    names = {z.id: "Zantha", b.id: "Bismark"}.__getitem__
    assert readback(cmd, names) == "Splitting fire. Tubes 1-4 on the Zantha, 5-8 on the Bismark; phasers on the Zantha."
    assert w.execute(cmd) is None
    assert [t.lock for t in me.tubes] == [z.id] * 4 + [b.id] * 4
    assert set(split_locks(me)) == {z.id, b.id}


def test_split_now_fires_each_group_at_its_own_ship(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    charge_all(w)
    r = run(w, me, "split tubes 1 2 on zantha, 3 4 on bismark now")
    fires = [c for c in r.commands if isinstance(c, FireTorpedoes)]
    assert {(c.target, c.tubes) for c in fires} == {(z.id, (0, 1)), (b.id, (2, 3))}


def test_a_tube_the_ship_lacks_or_one_named_twice_is_refused(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    assert "does not exist" in (parse("split tubes 9 on zantha", ParseContext(me.id, w.observe(0))).error or "")
    err = parse("split tubes 1 2 on zantha, 2 3 on bismark", ParseContext(me.id, w.observe(0))).error
    assert err is not None and "2" in err


def test_split_with_only_ships_named_lets_the_officer_divide(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    charge_all(w)
    cmd = only(run(w, me, "split torpedoes zantha bismark"), SplitFire)
    tubes = dict(cmd.tubes)
    assert set(tubes) == {z.id, b.id} and sorted(i for v in tubes.values() for i in v) == list(range(8))
    assert not cmd.banks                               # only the torpedoes were named


def test_split_off_puts_everything_back_on_the_target(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    w.execute(only(run(w, me, "split tubes 1-4 on zantha, rest on bismark"), SplitFire))
    w.execute(only(run(w, me, "split off"), SelectTarget))
    assert split_locks(me) == {} and {t.lock for t in me.tubes} == {me.target}


def test_engage_two_ships_is_a_standing_objective(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    obj = only(run(w, me, "engage zantha and bismark"), SetObjective)
    assert obj.goal == "engage" and obj.group == ENGAGE_GROUP and set(obj.targets) == {z.id, b.id}
    off = only(run(w, me, "engage off"), EndObjective)
    assert off.group == ENGAGE_GROUP


# ------------------------------------------------------------------ the officer's judgement

def test_divide_puts_torpedoes_on_both_when_both_are_in_the_window(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    charge_all(w)
    d = divide(w.observe(0), me, (z.id, b.id))
    assert d is not None and d.kind in ("tubes", "both")
    assert set(d.tubes) == {z.id, b.id}
    assert sorted(i for v in d.tubes.values() for i in v) == list(range(len(me.tubes)))


def test_divide_finishes_off_a_crippled_ship_first(duel, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    import begin.crew.split_fire as sf

    w, me, z, b = duel
    charge_all(w)
    obs = w.observe(0)
    assert divide(obs, me, (b.id, z.id)).primary in (z.id, b.id)           # type: ignore[union-attr]
    monkeypatch.setattr(sf, "hull_left", lambda c: 0.3 if c is not None and c.id == b.id else 1.0)
    d = divide(obs, me, (z.id, b.id))
    assert d is not None and d.primary == b.id


def test_phasers_on_the_near_ship_and_torpedoes_on_the_far_one(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    me = w.add_ship("federation.dn", 0, 0, 0, name="Enterprise")
    near = w.add_ship("klingon.fr", 1, 0, 1500, name="Near")
    far = w.add_ship("klingon.bc", 1, 0, 9000, name="Far")
    w.step()
    charge_all(w)
    d = divide(w.observe(0), me, (near.id, far.id))
    assert d is not None and d.kind == "weapons"
    assert set(d.banks) == {near.id} and set(d.tubes) == {far.id}


def test_the_officer_engages_both_and_salvoes_each(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    charge_all(w)
    assert w.execute(SetObjective(ship_id=me.id, goal="engage", group=ENGAGE_GROUP, targets=(z.id, b.id),
                                  officer="worf")) is None
    p = Planner("worf", "Lt. Worf")
    o = me.objectives[0]
    fired_at: set[int] = set()
    for _ in range(int(6 * w.rules.ticks_per_cycle)):
        for cmd in plan_engage(p, w.observe(0), me, o, None):
            if isinstance(cmd, FireTorpedoes) and cmd.target is not None:
                fired_at.add(cmd.target)
            w.execute(cmd)
        w.step()
    assert set(split_locks(me)) == {z.id, b.id}
    assert fired_at == {z.id, b.id}
    assert p.tally.get("splits", 0) >= 1


def test_a_ship_destroyed_hands_her_mounts_to_the_target(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    w.execute(SplitFire(ship_id=me.id, tubes=((z.id, (0, 1, 2, 3)), (b.id, (4, 5, 6, 7))), primary=z.id))
    w.destroy_ship(b, "test")
    w.step()
    assert {t.lock for t in me.tubes} == {z.id} and split_locks(me) == {}


def test_assisted_tubes_fire_each_at_its_own_lock(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    (z.x, z.y), (b.x, b.y) = (-1200.0, 3500.0), (1200.0, 3500.0)     # well inside the fire computer's window
    charge_all(w)
    w.execute(SplitFire(ship_id=me.id, tubes=((z.id, (0, 1, 2, 3)), (b.id, (4, 5, 6, 7))), primary=z.id))
    w.execute(SetFireMode(ship_id=me.id, weapon="tube", mode=FireMode.ASSISTED))
    fc = ShipComputer(me.id, 0, w.rng.derive("fire"))
    w.add_controller(fc)
    for _ in range(int(4 * w.rules.ticks_per_cycle)):
        w.step()
    said = " ".join(text for _, text in fc.trace.entries)
    assert "torpedoes at Zantha" in said and "torpedoes at Bismark" in said
    assert all(t.loaded is None for t in me.tubes)                 # each group went, at its own ship


def test_worth_splitting_needs_two_ships_in_reach_and_one_lock(duel) -> None:  # type: ignore[no-untyped-def]
    w, me, z, b = duel
    charge_all(w)
    assert worth_splitting(w.observe(0), me) is None              # no target yet
    w.execute(SelectTarget(ship_id=me.id, target=z.id, lock_weapons=True))
    assert worth_splitting(w.observe(0), me) == (z.id, b.id)
    w.execute(SplitFire(ship_id=me.id, tubes=((z.id, (0, 1)), (b.id, (2, 3)))))
    assert worth_splitting(w.observe(0), me) is None              # already split


# ------------------------------------------------------------------ proposals and counsel

def test_worf_proposes_dividing_fire_and_one_belay_quiets_every_pair(duel) -> None:  # type: ignore[no-untyped-def]
    from begin.crew.characters import load_officers
    from begin.crew.proposals import Proposer, candidates

    w, me, z, b = duel
    charge_all(w)
    w.execute(SelectTarget(ship_id=me.id, target=z.id, lock_weapons=True))
    crew = load_officers()
    officers = {crew[i].station: crew[i] for i in ("worf", "spock", "geordi", "seven")}
    props = [p for p in candidates(w.observe(0), me, officers) if p.line.startswith("engage")]
    assert props and props[0].line == "engage Zantha and Bismark" and props[0].station == "tactical"
    pr = Proposer()
    pr.belay(props[0], 0.0)
    shown = pr.next(w.observe(0), me, officers, 1.0, "often", False)
    assert shown is None or not shown.line.startswith("engage")


# ------------------------------------------------------------------ the Weapons panel

@pytest.mark.parametrize("size", [(1024, 640), (1600, 900), (1920, 1080)])
def test_the_weapons_panel_tags_each_mount_with_its_ship_and_nothing_overflows(content, size) -> None:  # type: ignore[no-untyped-def]
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene
    from begin.ui.hud import WeaponsPanel, split_tags

    from .test_text_fits import overflows

    pygame.init()
    surf = pygame.display.set_mode(size)
    preset = {p.id: p for p in load_presets()}["dreadnought-duel"]
    sc = BattleScene(build_battle(content, preset.setup()), size, lambda: None)
    sc.paused = False
    for _ in range(300):
        sc.update(1 / 30)
    names = {c.label.split(" (")[0].lower(): c.id for c in sc.obs.hostile_contacts() if c.identified}
    a, b = sorted(names)[:2]
    sc.run_console(f"split tubes 1-4 on {a}, rest on {b}, phasers on {a}")
    sc.update(1 / 30)
    assert set(split_locks(sc.player)) == {names[a], names[b]}
    tags = split_tags(sc, sc.player)
    assert len({t for t, _, _ in tags.values()}) == 2 and list(tags)[0] == sc.player.target
    sc.draw(surf)
    if sc.side_tabs.folded:
        sc.side_tabs.show(WeaponsPanel)
    with theme.watching() as ink:
        sc.draw(surf)
    assert not overflows(ink), overflows(ink)
    said = [k.text for k in ink if k.kind != "panel"]
    assert a.title() in said or any(a.title() in t for t in said)          # the key names the ships
