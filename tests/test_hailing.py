"""Hailing enemy captains: how watching their allies battered shifts them, and what a hail can get you."""

from __future__ import annotations

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.console.parser import ParseContext, parse
from begin.crew.hails import Comms, classify, load_lines
from begin.sim.commands import Hail, Transport
from begin.sim.events import CaptainMood, HailAnswered
from begin.sim.ship import ShipStatus
from begin.sim.systems import disposition
from begin.sim.systems.damage import DamageKind, apply_damage


def _battle(content, enemy: str = "klingon.bc", n: int = 3, seed: int = 3):  # type: ignore[no-untyped-def]
    ships = [ShipSpec(enemy, x=1500.0 * i, y=900.0) for i in range(n)]
    setup = BattleSetup([FleetSpec(side=0, player=True, center=(0.0, 0.0), ships=[ShipSpec("federation.hc")]),
                         FleetSpec(side=1, center=(0.0, 900.0), ships=ships)], seed=seed)
    b = build_battle(content, setup)
    w = b.world
    me = w.ships[b.player_ship_id]
    them = [s for s in w.ships.values() if s.side == 1]
    w.run(0.5)
    return b, w, me, them


def _wreck(w, me, victim, hits: int = 40) -> None:  # type: ignore[no-untyped-def]
    for sh in victim.shields:
        sh.up = False
    for _ in range(hits):
        if victim.status != ShipStatus.ACTIVE:
            break
        apply_damage(w, victim, 30, me.x, me.y, DamageKind.BLAST, me.id, None)
    w.run(0.2)


def _hail(w, me, t, intent: str, **kw) -> HailAnswered:  # type: ignore[no-untyped-def]
    t.mood.last_hailed = -10**9
    cmd = Hail(ship_id=me.id, target=t.id, intent=intent, **kw)
    assert w.execute(cmd) is None
    assert isinstance(cmd.answered, HailAnswered)
    return cmd.answered


def test_captains_get_a_temperament_from_their_race(content) -> None:  # type: ignore[no-untyped-def]
    _, _, _, klingons = _battle(content, "klingon.bc")
    _, _, _, orions = _battle(content, "orion.cr" if "orion.cr" in content.classes else
                              next(c.id for c in content.classes_of("orion", include_bases=False)))
    assert all(k.mood.seated for k in klingons + orions)
    assert sum(k.mood.temper for k in klingons) / 3 > 0.6         # Klingons are angered by losses
    assert sum(o.mood.temper for o in orions) / 3 < 0.45           # Orions are cowed by them
    assert all(k.mood.resolve == k.mood.obstinacy for k in klingons)


def test_watching_an_ally_destroyed_angers_the_hot_and_cows_the_cool(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content)
    hot, cool, victim = them
    hot.mood.temper, cool.mood.temper = 0.95, 0.05
    before = (hot.mood.resolve, cool.mood.resolve)
    _wreck(w, me, victim)
    assert victim.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT)
    assert hot.mood.anger > 0.4 and hot.mood.anger > hot.mood.fear
    assert cool.mood.fear > 0.4 and cool.mood.fear > cool.mood.anger
    assert hot.mood.nemesis == me.id                                    # and they blame us
    assert hot.mood.resolve < before[0] and cool.mood.resolve < before[1]   # both are worn down
    moods = {e.ship_id: e.mood for e in w.take_events() if isinstance(e, CaptainMood)}
    assert moods.get(hot.id) == "enraged" and moods.get(cool.id) == "shaken"


def test_an_obstinate_captain_comes_round_after_watching_allies_battered(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, "orion.cr" if "orion.cr" in content.classes else
                             next(c.id for c in content.classes_of("orion", include_bases=False)))
    target, *others = them
    target.mood.temper, target.mood.obstinacy, target.mood.resolve = 0.2, 0.9, 0.9
    fresh = disposition.captain_odds(w, me, target, "withdraw")
    for o in others:
        _wreck(w, me, o)
    battered = disposition.captain_odds(w, me, target, "withdraw")
    assert battered > fresh + 0.3


def test_a_surrender_drops_shields_and_boarding_takes_her_without_bloodshed(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, n=1)
    kl = them[0]
    kl.mood.fear, kl.mood.resolve, kl.mood.anger = 1.0, 0.0, 0.0
    kl.structure = kl.structure_max * 0.2
    ev = _hail(w, me, kl, "surrender", persuasion=1.5)
    assert ev.outcome == "surrender"
    assert kl.status == ShipStatus.SURRENDERED
    assert all(not s.up for s in kl.shields) and all(not bk.enabled for bk in kl.banks)
    crew_before, ours_before = kl.crew, me.crew
    for sh in me.shields:
        sh.up = False
    w.run(0.3)
    me.x, me.y = kl.x, kl.y - 500
    assert w.execute(Transport(ship_id=me.id, target=kl.id, count=10)) is None
    w.run(1.5)
    assert kl.side == me.side                                    # she is ours
    assert kl.prisoners == crew_before                           # every one of her crew a prisoner
    assert me.crew == ours_before - 10 and kl.crew == 10         # and nobody of ours was lost


def test_firing_on_a_surrendered_ship_costs_trust(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, n=2)
    kl, other = them
    w.surrender(kl)
    apply_damage(w, kl, 20, me.x, me.y, DamageKind.BLAST, me.id, None)
    w.run(0.2)
    assert other.mood.distrust > 0.2
    assert any(isinstance(e, CaptainMood) and e.mood == "betrayed" for e in w.take_events())


def test_a_withdrawal_holds_their_fire_until_we_break_it(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, n=1)
    kl = them[0]
    kl.mood.fear, kl.mood.resolve, kl.mood.anger = 0.9, 0.0, 0.0
    ev = _hail(w, me, kl, "withdraw", persuasion=1.5)
    assert ev.outcome == "withdraw" and kl.hold_fire and kl.mood.terms == "withdraw"
    w.run(1.0)
    assert b.captains[kl.id].withdrawing
    apply_damage(w, kl, 10, me.x, me.y, DamageKind.PHASER, me.id, None)
    w.run(0.2)
    assert kl.mood.terms == "" and not kl.hold_fire and kl.mood.anger > 0.3


def test_a_confident_captain_refuses_and_a_bluff_they_can_see_through_angers_them(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, n=2)
    kl = them[0]
    kl.mood.resolve = 0.9
    ev = _hail(w, me, kl, "surrender")
    assert ev.outcome in ("refuse", "defy", "waver", "silence")
    assert kl.status == ShipStatus.ACTIVE
    me.structure = me.structure_max * 0.3
    intel = w.intel[kl.side].contacts[me.id]
    from begin.sim.systems.sensors import perform_scan
    perform_scan(w, kl, me)
    assert intel.scan is not None
    anger = kl.mood.anger
    ev = _hail(w, me, kl, "surrender", bluff=True)
    assert "scans" in ev.reason and kl.mood.anger > anger


def test_hails_are_rate_limited_and_only_for_enemies(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, n=1)
    kl = them[0]
    assert w.execute(Hail(ship_id=me.id, target=kl.id, intent="talk")) is None
    assert "just answered" in (w.execute(Hail(ship_id=me.id, target=kl.id, intent="talk")) or "")
    assert w.execute(Hail(ship_id=me.id, target=me.id, intent="talk")) is not None


def test_the_console_reads_a_hail(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, n=1)
    kl = them[0]
    name = kl.name.lower().split()[0]
    res = parse(f"hail {name} surrender, and your crew will be treated well", ParseContext(me.id, w.observe(0)))
    assert res.error is None, res.error
    assert res.actions == [("hail", (kl.id, "surrender  and your crew will be treated well".replace("  ", " ")))] or \
        res.actions[0][1][0] == kl.id
    me.target = kl.id
    res = parse("open a channel", ParseContext(me.id, w.observe(0)))
    assert res.actions and res.actions[0][0] == "hail" and res.actions[0][1][0] == kl.id
    res = parse("hail all: stand down", ParseContext(me.id, w.observe(0)))
    assert res.actions == [("hail", (None, "stand down"))]
    assert parse("open fire", ParseContext(me.id, w.observe(0))).error is None
    assert parse("pr", ParseContext(me.id, w.observe(0))).error != "Unknown command 'pr'. Type 'help' for the list."
    # a word that reads as a ship that isn't there is not sent as speech
    assert "No ship named 'gargoyle'" in (parse("hail gargoyle", ParseContext(me.id, w.observe(0))).error or "")
    assert "hail them" in (parse("hail thm", ParseContext(me.id, w.observe(0))).error or "")
    near = name[:-1] + ("x" if name[-1] != "x" else "y")
    assert "Did you mean" in (parse(f"hail {near} surrender", ParseContext(me.id, w.observe(0))).error or "")
    res = parse("hail surrender", ParseContext(me.id, w.observe(0)))
    assert res.actions == [("hail", (kl.id, "surrender"))]
    res = parse("hail we come in peace", ParseContext(me.id, w.observe(0)))
    assert res.error is None and res.actions[0][1] == (kl.id, "we come in peace")


def test_offline_reading_of_the_captains_words() -> None:
    j = classify("Lower your shields and prepare to be boarded, or share the fate of your friends")
    assert j.intent == "surrender" and j.threat
    j = classify("Leave this sector and we will hold our fire. You have my word.")
    assert j.intent == "withdraw" and j.persuasion > 1.0
    j = classify("Surrender. A Starfleet squadron is on its way.")
    assert j.bluff
    assert classify("You cowards!").intent == "taunt"
    j = classify("Cease fire or we will destroy you")
    assert j.intent == "withdraw" and j.threat
    assert classify("Who are you?").intent == "talk"


def test_comms_answers_in_words_without_a_model(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, n=1)
    kl = them[0]
    comms = Comms(w, 0, None, lines=load_lines())
    out = comms.hail(me, kl.id, "Who commands that ship?", w.execute)
    assert out and out[0].tone == "enemy" and kl.name in out[0].speaker
    ch = comms.channels[kl.id]
    assert ch.status == "open" and ch.lines[0] == ("us", "Who commands that ship?") and ch.lines[1][0] == "them"
    assert "{" not in out[0].text


def test_comms_takes_the_models_reading_and_words(content) -> None:  # type: ignore[no-untyped-def]
    j = Comms.judged('{"intent": "withdraw", "threat": false, "bluff": false, "persuasion": 1.4, '
                     '"accept": "We go.", "refuse": "We stay."}', classify("hello"))
    assert (j.intent, j.persuasion, j.accept, j.refuse) == ("withdraw", 1.4, "We go.", "We stay.")
    j = Comms.judged("not json at all", classify("surrender now"))
    assert j.intent == "surrender" and j.refuse == "not json at all"


def test_shipped_hail_lines_are_plain_star_trek_language(content) -> None:  # type: ignore[no-untyped-def]
    lines = load_lines()
    text = " ".join(str(v) for t in lines.values() for v in t.values()).lower()
    for word in ("sex", "seduc", "kiss", "naked", "flirt"):
        assert word not in text


def test_prisoners_can_be_offered_back_for_a_withdrawal(content) -> None:  # type: ignore[no-untyped-def]
    b, w, me, them = _battle(content, n=1)
    kl = them[0]
    me.prisoners = 30
    kl.crew = kl.cls.crew - 40
    kl.mood.fear, kl.mood.resolve, kl.mood.anger = 0.9, 0.0, 0.0
    ev = _hail(w, me, kl, "withdraw", persuasion=1.5, release=True)
    assert ev.outcome == "withdraw" and "30 prisoners beamed back" in ev.reason
    assert me.prisoners == 0 and kl.crew == kl.cls.crew - 10
    j = classify("Leave now and we will return your people")
    assert j.intent == "withdraw"


def test_a_tour_remembers_how_we_treated_surrenders(content) -> None:  # type: ignore[no-untyped-def]
    from begin.ai.personality import Personality
    from begin.core.rng import Rng

    fac = content.factions["klingon"]
    p = Personality.roll(fac, Rng(5), {"trust": 0.8})
    q = Personality.roll(fac, Rng(5), {"trust": -0.8})
    assert p.trust == 0.8 and q.trust == -0.8 and p.aggression == q.aggression   # nothing else changes
    b, w, me, them = _battle(content, n=1)
    kl = them[0]
    kl.mood.seated = False
    disposition.seat(kl, p)
    trusting = (kl.mood.resolve, kl.mood.distrust)
    kl.mood.seated = False
    disposition.seat(kl, q)
    assert trusting[0] < kl.mood.resolve and kl.mood.distrust > trusting[1]


def test_handing_over_prisoners_in_the_ready_room(content) -> None:  # type: ignore[no-untyped-def]
    from begin.tour.model import load_tours
    from begin.tour.run import TourRun

    tour = load_tours()[0][0]
    run = TourRun.new(tour, content, [])
    calls = run.state.calls_left
    assert "no prisoners" in run.hand_over_prisoners().lower()
    run.state.prisoners = 85
    msg = run.hand_over_prisoners()
    assert "85 prisoners" in msg and run.state.prisoners == 0 and run.state.calls_left == calls + 2
    run.state.lessons["ruthless"] = 0.5
    assert any("fight to the end" in ln for ln in run.lesson_lines())


def test_an_officer_takes_a_surrendered_ship_without_a_fight(content) -> None:  # type: ignore[no-untyped-def]
    from begin.crew.objectives import Planner, plan_capture
    from begin.sim.commands import SetObjective
    from begin.sim.world import World

    w = World(content, seed=4)
    fed = w.add_ship("federation.hc", 0, 0, 0, name="Enterprise")
    kl = w.add_ship("klingon.bc", 1, 0, 2500, name="Votek")
    w.run(1.0)
    w.surrender(kl)
    crew, ours = kl.crew, fed.crew
    assert w.execute(SetObjective(ship_id=fed.id, goal="capture", group="crew", targets=(kl.id,))) is None
    p = Planner("worf", "Lt. Worf")
    o = fed.objectives[0]
    for _ in range(int(20 * w.rules.ticks_per_cycle)):
        for cmd in plan_capture(p, w.observe(0), fed, o, None):
            w.execute(cmd)
        w.step()
        if kl.side == fed.side:
            break
    assert kl.side == fed.side and kl.prisoners == crew
    assert fed.crew + kl.crew == ours                          # nobody of ours lost


def test_a_model_plays_the_enemy_captain(content) -> None:  # type: ignore[no-untyped-def]
    import time

    from begin.llm.service import LLMService

    class Fake:
        name = "fake"
        seen: list[str] = []

        def complete(self, system: str, messages: list[dict[str, str]]) -> str:
            Fake.seen.append(system)
            return ('{"intent": "withdraw", "threat": false, "bluff": false, "persuasion": 1.5, '
                    '"accept": "Very well, Enterprise. We go.", "refuse": "We stay and fight."}')

    b, w, me, them = _battle(content, n=1)
    kl = them[0]
    kl.mood.fear, kl.mood.resolve, kl.mood.anger = 0.95, 0.0, 0.0
    comms = Comms(w, 0, LLMService(Fake()), lines=load_lines())
    first = comms.hail(me, kl.id, "Go home, captain. Nobody else needs to die today.", w.execute)
    assert any("waiting" in u.text for u in first) and comms.channels[kl.id].status == "hailing"
    out = []
    for _ in range(100):
        out = comms.poll(me, w.execute)
        if out:
            break
        time.sleep(0.01)
    assert out[0].text in ("Very well, Enterprise. We go.", "We stay and fight.")
    assert kl.name in Fake.seen[0] and "Klingon" in Fake.seen[0]
    if out[0].text.startswith("Very"):
        assert kl.mood.terms == "withdraw"
    comms.close()
