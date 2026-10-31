"""Running a tour of duty: from the squadron you pick, through each stop's battle, to the finale [E].

`TourRun` joins a `TourDef` (the patrol as written) to a `TourState` (how it stands). It
builds each stop's battle with your squadron as it is now, takes the ships back when the
battle ends (`finish`), writes the log page, and moves on. It knows nothing about pygame,
so tests and `begin --tour-test` can play whole tours headless.

How a stop goes:

1. In the Ready Room you make the stop's choice (if it has one) and may call for
   reinforcements; `launch` then applies the transit (field repairs on the way, or a refit
   at the starbase) and builds the battle.
2. In battle, `request reinforcements` asks Starfleet for a ship; she drops out of warp after
   the stop's ETA (`reinforcement_arrival`).
3. `finish` writes back every ship (hull, systems, crew, magazines, morale), adds prizes and
   reinforcements to the squadron, records what the enemy has learned, and drafts the log.
"""

from __future__ import annotations

import copy
import math
import random
from dataclasses import dataclass, field

from ..battle import Battle, BattleSetup, FleetSpec, ShipSpec
from ..content.schema import ContentDB
from ..sim.arrivals import Arrival
from ..sim.commands import FirePhasers, FireTorpedoes, SelectTarget
from ..sim.rules import DEFAULT_RULES, Rules
from ..sim.ship import Ship, ShipStatus
from .log import draft_entry
from .model import Stop, TourDef
from .state import LogEntry, ShipRecord, StopResult, TourState, apply_record, fleet_cost, harvest, record_of, refit, resupply, transit

CAUTION_PER_AIMED = 0.25      # how much warier the enemy gets for each fight in which we aimed at their systems
CAUTION_PER_CAPTURE = 0.2     # ...and for each ship of theirs we took
CAUTION_MAX = 0.8
MERCY_PER_SURRENDER = 0.2    # [E] each enemy ship that surrendered to us and was spared: word spreads
MERCY_PER_TRUCE = 0.1        # ...each that we let withdraw as agreed
RUTHLESS_PER_BROKEN = 0.5    # ...each we fired on after it surrendered or agreed to withdraw
REPUTATION_MAX = 1.0
PRISONERS_PER_CALL = 40      # prisoners handed to Starfleet that earn the squadron another reinforcement call
PRESS_LOW_MAGAZINE = 0.35     # our flagship's magazine below this share: the enemy knows, and closes in
REINFORCEMENT_EDGE = 16000.0  # how far from the battle Starfleet's ship drops out of warp
REINFORCEMENT_MIN = 15.0      # the soonest one can arrive, cycles


@dataclass
class Fight:
    """The battle for one stop, and which record each of your ships came from."""
    stop: Stop
    setup: BattleSetup
    records: list[ShipRecord]
    ship_ids: list[int] = field(default_factory=list)
    friend_ids: list[int] = field(default_factory=list)
    called: list[Arrival] = field(default_factory=list)


class TourRun:
    def __init__(self, tour: TourDef, state: TourState, content: ContentDB, rules: Rules = DEFAULT_RULES) -> None:
        self.tour = tour
        self.state = state
        self.content = content
        self.rules = rules
        self.fight: Fight | None = None

    # ------------------------------------------------------------ starting

    @staticmethod
    def new(tour: TourDef, content: ContentDB, escorts: list[str], seed: int = 1,
            flagship_name: str = "Enterprise") -> TourRun:
        """A fresh tour: the flagship and the escorts you picked, every ship named and crewed."""
        rng = random.Random(seed)
        used = {flagship_name}
        captains: set[str] = set()
        squadron = [ShipRecord(tour.flagship, flagship_name, role="flagship")]
        for cid in escorts:
            squadron.append(ShipRecord(cid, _name(content, cid, used, rng), role="escort",
                                       captain=_captain(content, cid, rng, captains)))
        state = TourState(tour.id, squadron, calls_left=tour.reinforcement_calls, seed=seed)
        return TourRun(tour, state, content)

    @staticmethod
    def budget_left(tour: TourDef, content: ContentDB, escorts: list[str]) -> int:
        return tour.budget - sum(fleet_cost(c, content) for c in escorts)

    # ------------------------------------------------------------ where we are

    @property
    def stop(self) -> Stop | None:
        s = self.state.stop
        return self.tour.stops[s] if s < len(self.tour.stops) else None

    @property
    def over(self) -> bool:
        return bool(self.state.over)

    def flags(self) -> set[str]:
        return set(self.state.flags)

    def transit_cycles(self) -> float:
        stop = self.stop
        if stop is None:
            return 0.0
        ch = self.chosen()
        return ch.transit if ch is not None and ch.transit is not None else stop.transit

    def chosen(self):  # type: ignore[no-untyped-def]
        stop = self.stop
        if stop is None or self.state.choice is None or not stop.choices:
            return None
        return stop.choices[min(self.state.choice, len(stop.choices) - 1)]

    def choose(self, i: int) -> None:
        self.state.choice = i

    def needs_choice(self) -> bool:
        stop = self.stop
        return stop is not None and bool(stop.choices) and self.state.choice is None

    def projected(self) -> list[ShipRecord]:
        """The squadron as it will be when the next fight starts: after the transit's repairs (or the refit)."""
        recs = copy.deepcopy(self.state.squadron)
        self._travel(recs)
        return recs

    def _travel(self, recs: list[ShipRecord]) -> None:
        ch = self.chosen()
        cycles = self.transit_cycles()
        for r in recs:
            if r.lost:
                continue
            if r.reserve or (ch is not None and ch.refit):
                refit(r, self.content)
            else:
                transit(r, self.content, self.rules, cycles)
                resupply(r, self.content, self.tour.resupply)

    def lesson_lines(self) -> list[str]:
        """What the enemy knows about us, as the briefing puts it."""
        out = []
        caution = self.state.lessons.get("caution", 0.0)
        if caution >= 0.5:
            out.append("Word of our aimed fire and our boarding parties has spread. Expect their captains to keep "
                       "their distance and turn fresh shields to us early.")
        elif caution > 0:
            out.append("They will have heard how we fought at the last stop. Expect more care at the start.")
        if self._low_magazine():
            out.append("Our magazines are low, and their scouts will have counted our torpedoes. Expect them to close "
                       "to phaser range.")
        trust = self.reputation()
        if trust <= -0.3:
            out.append("Word has spread that we fired on ships that had struck their colours. Expect no surrenders: "
                       "their captains will fight to the end, and they will not believe our terms.")
        elif trust >= 0.3:
            out.append("Word has spread that we take surrenders and treat prisoners decently. Their captains will be "
                       "readier to yield.")
        elif trust > 0:
            out.append("Some of their captains will have heard that we honour a surrender.")
        return out

    def reputation(self) -> float:
        """-1..1: how the enemy's captains expect us to treat a surrender, from what we did earlier in the tour."""
        lessons = self.state.lessons
        return max(-1.0, min(1.0, lessons.get("mercy", 0.0) - lessons.get("ruthless", 0.0)))

    def hand_over_prisoners(self) -> str:
        """In the Ready Room: a Starfleet transport takes the prisoners off our hands [E]."""
        n = self.state.prisoners
        if n <= 0:
            return "We hold no prisoners. Take a ship that has surrendered and her crew come aboard as prisoners."
        self.state.prisoners = 0
        calls = n // PRISONERS_PER_CALL
        if calls:
            self.state.calls_left += calls
        for r in self.state.squadron:
            if r.active:
                resupply(r, self.content, 0.25)
        thanks = (f" Starfleet Command is grateful: {'another ship is' if calls == 1 else f'{calls} more ships are'} "
                  "ours to call on." if calls else "")
        return (f"A Starfleet transport has taken our {n} prisoners of war to a detention facility, and left us "
                f"torpedoes and probes in exchange for the room.{thanks}")

    def _low_magazine(self) -> bool:
        f = self.state.flagship
        full = self.content.classes[f.class_id].torps_carried
        return full > 0 and f.torps_now(self.content) < full * PRESS_LOW_MAGAZINE

    # ------------------------------------------------------------ reinforcements

    def request_from_ready_room(self) -> str:
        """Ask Starfleet before the fight: the ship meets us at the next stop, late if the trip is short."""
        if self.state.calls_left <= 0:
            return "Starfleet has nothing more to send. We are on our own."
        cid = self._pick_reinforcement(len(self.state.pending) + len(self.state.results))
        if cid is None:
            return "Starfleet has no ships to spare."
        self.state.calls_left -= 1
        self.state.pending.append(cid)
        stop = self.stop
        late = max(0.0, (stop.eta if stop else 0.0) - self.transit_cycles())
        cls = self.content.classes[cid]
        when = "and will be there when we arrive" if late <= 0 else f"and will reach us {late:.0f} cycles into the fight"
        return f"Starfleet is sending a {cls.name.lower()} {when}."

    def _pick_reinforcement(self, n: int) -> str | None:
        pool = [c for c in self.tour.reinforcements if c in self.content.classes]
        if not pool:
            return None
        rng = random.Random(self.state.seed * 7919 + n)
        return rng.choice(pool)

    def reinforcement_arrival(self, battle: Battle, player_ship: Ship | None) -> tuple[Arrival | None, str]:
        """`request reinforcements` in battle: Starfleet answers with a ship and an ETA."""
        fight = self.fight
        if fight is None or self.state.calls_left <= 0:
            return None, "Starfleet has nothing more to send. We are on our own."
        w = battle.world
        cid = self._pick_reinforcement(len(self.state.results) * 10 + len(fight.called) + 100)
        if cid is None:
            return None, "Starfleet has no ships to spare."
        self.state.calls_left -= 1
        rng = random.Random(self.state.seed * 31 + w.tick)
        eta = max(REINFORCEMENT_MIN, fight.stop.eta * rng.uniform(0.85, 1.15))
        name = _name(self.content, cid, {s.name for s in w.ships.values()} | w.reserved_names, rng)
        x, y, heading = self._entry_point(battle, player_ship)
        a = Arrival(side=w.player_side, ships=(cid,), kind="reinforcement", at=w.time + eta, at_x=x, at_y=y,
                    heading=heading, names=(name,), tag="starfleet",
                    message=f"USS {name} has dropped out of warp to join us.")
        w.arrivals.append(a)
        fight.called.append(a)
        cls = self.content.classes[cid]
        return a, f"Starfleet acknowledges. USS {name}, {cls.name.lower()}, ETA {eta:.0f} cycles."

    def _entry_point(self, battle: Battle, me: Ship | None) -> tuple[float, float, float]:
        """Where Starfleet's ship drops out of warp: behind our nearest base or ship, away from the enemy."""
        w = battle.world
        side = w.player_side
        ours = [s for s in w.ships.values() if s.alive and s.side == side]
        anchor = next((s for s in ours if s.cls.is_base), me if me is not None and me.alive else (ours[0] if ours else None))
        enemies = [s for s in w.ships.values() if s.alive and s.side != side]
        ax, ay = (anchor.x, anchor.y) if anchor is not None else (0.0, 0.0)
        if enemies:
            ex = sum(e.x for e in enemies) / len(enemies)
            ey = sum(e.y for e in enemies) / len(enemies)
            away = math.atan2(ax - ex, ay - ey)
        else:
            away = math.pi
        x, y = ax + math.sin(away) * REINFORCEMENT_EDGE, ay + math.cos(away) * REINFORCEMENT_EDGE
        heading = math.degrees(math.atan2(ax - x, ay - y)) % 360.0
        return x, y, heading

    # ------------------------------------------------------------ the battle

    def launch(self) -> Fight:
        """Travel to the next stop (repairs, or a refit) and set up its battle."""
        stop = self.stop
        assert stop is not None and not self.over
        ch = self.chosen()
        self._travel(self.state.squadron)
        if ch is not None:
            for f in ch.flags:
                if f not in self.state.flags:
                    self.state.flags.append(f)
        flags = self.flags()
        active = self.state.active()
        mine = FleetSpec(0, [ShipSpec(r.class_id, name=r.name) for r in active], player=True, center=stop.player_center)
        fleets = [mine]
        if stop.friends:
            fleets.append(FleetSpec(0, [ShipSpec(c, name=self.tour.starbase if self.content.classes[c].is_base else None)
                                         for c in stop.friends], center=stop.friends_center))
        fleets.append(FleetSpec(1, [ShipSpec(c) for c in stop.enemy_ships(flags)], center=stop.enemy_center))
        arrivals = []
        for wv in stop.active_waves(flags):
            cx, cy = wv.center
            arrivals.append(Arrival(side=1, ships=wv.ships, kind="wave", at=wv.at, after_clear=wv.after_clear,
                                    at_x=cx, at_y=cy, heading=math.degrees(math.atan2(-cx, -cy)) % 360.0,
                                    message=wv.message))
        # reinforcements asked for in the Ready Room: there at the start, or partway in if the trip was short
        late = max(0.0, stop.eta - self.transit_cycles())
        rng = random.Random(self.state.seed * 13 + self.state.stop)
        called = []
        for cid in self.state.pending:
            name = _name(self.content, cid, {r.name for r in self.state.squadron}, rng)
            if late <= 0:
                mine.ships.append(ShipSpec(cid, name=name))
                active.append(ShipRecord(cid, name, role="reinforcement", joined=stop.id,
                                         captain=_captain(self.content, cid, rng, {r.captain for r in self.state.squadron})))
            else:
                px, py = stop.player_center
                called.append(Arrival(side=0, ships=(cid,), kind="reinforcement", at=late, at_x=px, at_y=py - 12000.0,
                                      heading=0.0, names=(name,), tag="starfleet",
                                      message=f"USS {name} has dropped out of warp to join us."))
        for r in active:
            if r.role == "reinforcement" and r not in self.state.squadron:
                self.state.squadron.append(r)
        self.state.pending = []
        lean: dict[str, float] = {}
        if self.reputation():
            lean["trust"] = self.reputation()
        if self.state.lessons.get("caution"):
            lean["caution"] = self.state.lessons["caution"]
        if self._low_magazine():
            lean["press"] = 0.6
        setup = BattleSetup(fleets, seed=self.state.seed * 1000 + stop.seed, title=stop.title,
                            description=f"{stop.system}: {self.tour.title}, stop {self.state.stop + 1} of "
                                        f"{len(self.tour.stops)}.",
                            arrivals=arrivals + called, personalities={1: lean} if lean else {})
        self.fight = Fight(stop, setup, active)
        self.fight.called.extend(called)
        return self.fight

    def prepare(self, battle: Battle) -> None:
        """The battle is built: make every ship of ours the ship her record says she is."""
        fight = self.fight
        assert fight is not None
        w = battle.world
        ours = [s for s in w.ships.values() if s.side == w.player_side]
        n = len(fight.records)
        fight.ship_ids = [s.id for s in ours[:n]]
        fight.friend_ids = [s.id for s in ours[n:]]
        for rec, sid in zip(fight.records, fight.ship_ids):
            apply_record(w.ships[sid], rec)
        if fight.ship_ids:
            w.ships[fight.ship_ids[0]].prisoners = self.state.prisoners   # the brig comes along
        # the reinforcements called in from the Ready Room are named already; their records were made at launch

    def finish(self, battle: Battle, standout: str = "") -> LogEntry:
        """The battle is over: take the ships back, add prizes and reinforcements, learn, log, and move on."""
        fight = self.fight
        assert fight is not None
        w = battle.world
        side = w.player_side
        stop = fight.stop
        before_lost = {r.name for r in self.state.squadron if r.lost}
        for rec, sid in zip(fight.records, fight.ship_ids):
            harvest(w.ships[sid], rec, side)
            if rec.lost and not rec.lost_at:
                rec.lost_at = stop.id
        known = set(fight.ship_ids) | set(fight.friend_ids)
        captured: list[str] = []
        for s in w.ships.values():
            if s.id in known or s.side != side or not s.alive or s.cls.is_base:
                continue
            role = "reinforcement" if any(s.id in a.ship_ids for a in w.arrivals if a.tag == "starfleet") else "prize"
            rec = record_of(s, role, stop.id)
            rec.lost = False
            self.state.squadron.append(rec)
            if role == "prize":
                captured.append(s.name)
        lost = [r.name for r in self.state.squadron if r.lost and r.name not in before_lost]
        # prisoners held aboard ships that are still ours (on a ship we lost, they are free again)
        self.state.prisoners = sum(s.prisoners for s in w.ships.values() if s.side == side and s.alive)
        won = w.outcome.over and w.outcome.winner == side
        friends_ok = all(w.ships[i].alive for i in fight.friend_ids)
        flag = self.state.flagship
        if flag.lost:
            outcome = "lost"
        elif won and (friends_ok or not stop.finale):
            outcome = "victory"
        elif stop.finale and not friends_ok:
            outcome = "base lost"
        else:
            outcome = "withdrew"
        kills = sum(w.ships[i].stats.kills for i in fight.ship_ids if i in w.ships)
        self.state.results.append(StopResult(stop.id, outcome, round(w.time, 1), kills, captured, lost))
        self._learn(battle, fight, captured)
        if outcome == "victory" and stop.win_flag and stop.win_flag not in self.state.flags:
            self.state.flags.append(stop.win_flag)
        # crew spirits: a win lifts them, a loss of shipmates weighs on them
        for r in self.state.squadron:
            if r.active and r.morale is not None:
                r.morale = max(0.0, min(100.0, r.morale + (5.0 if outcome == "victory" else -5.0) - 6.0 * len(lost)))
        entry = draft_entry(self, battle, fight, outcome, captured, lost, standout)
        self.state.log.append(entry)
        if outcome == "lost" or outcome == "base lost":
            self.state.over = "lost"
        else:
            self.state.stop += 1
            self.state.choice = None
            if self.state.stop >= len(self.tour.stops):
                self.state.over = "won"
        self.fight = None
        return entry

    def _learn(self, battle: Battle, fight: Fight, captured: list[str]) -> None:
        """What the enemy takes away from this fight: aimed fire and boarding make them wary."""
        aimed = any(lc.accepted and lc.command.ship_id in fight.ship_ids and
                    isinstance(lc.command, (SelectTarget, FirePhasers, FireTorpedoes)) and lc.command.subsystem
                    for lc in battle.world.command_log)
        c = self.state.lessons.get("caution", 0.0)
        if aimed:
            c += CAUTION_PER_AIMED
        c += CAUTION_PER_CAPTURE * len(captured)
        if c > 0:
            self.state.lessons["caution"] = round(min(CAUTION_MAX, c), 2)
        # [E] how we treated those who yielded: the enemy's captains will hear of it
        w = battle.world
        side = w.player_side
        broken = w.faith_broken.get(side, set())
        spared = [s for s in w.ships.values() if s.id not in broken and s.surrender_time > 0
                  and (s.status == ShipStatus.SURRENDERED or (s.side == side and s.prisoners > 0))]
        truces = [s for s in w.ships.values() if s.id not in broken and s.side != side and s.mood.terms
                  and s.status == ShipStatus.ESCAPED]
        mercy = self.state.lessons.get("mercy", 0.0) + MERCY_PER_SURRENDER * len(spared) + MERCY_PER_TRUCE * len(truces)
        ruthless = self.state.lessons.get("ruthless", 0.0) + RUTHLESS_PER_BROKEN * len(broken)
        if mercy:
            self.state.lessons["mercy"] = round(min(REPUTATION_MAX, mercy), 2)
        if ruthless:
            self.state.lessons["ruthless"] = round(min(REPUTATION_MAX, ruthless), 2)

    # ------------------------------------------------------------ the end

    def rating(self) -> tuple[str, list[str]]:
        """The tour's final rating, and the record behind it."""
        st = self.state
        won = st.over == "won"
        content = self.content
        crew_out = sum(self.content.classes[r.class_id].crew for r in st.squadron if r.role in ("flagship", "escort"))
        crew_home = sum(r.crew_now(content) for r in st.squadron if not r.lost and r.role in ("flagship", "escort"))
        prizes = sum(len(r.captured) for r in st.results)
        kills = sum(r.kills for r in st.results)
        victories = sum(1 for r in st.results if r.outcome == "victory")
        lost = sum(1 for r in st.squadron if r.lost)
        points = victories * 10 + prizes * 8 + kills * 3 - lost * 6 + int(20 * crew_home / max(1, crew_out))
        if not won:
            grade = "Tour failed"
        elif points >= 80:
            grade = "Commendation: the Christopher Pike Medal of Valor"
        elif points >= 60:
            grade = "Commendation: the Starfleet Citation for Conspicuous Gallantry"
        elif points >= 40:
            grade = "Tour completed with distinction"
        else:
            grade = "Tour completed"
        lines = [
            f"{victories} of {len(self.tour.stops)} stops won" if won else f"{victories} stops won before the end",
            f"{kills} enemy ships destroyed, {prizes} taken as prizes",
            f"{lost} of our ships lost",
            f"{crew_home} of {crew_out} crew brought home",
            f"{st.calls_left} call{'s' if st.calls_left != 1 else ''} for reinforcements left unused",
        ]
        return grade, lines


def _name(content: ContentDB, cid: str, used: set[str], rng: random.Random) -> str:
    cls = content.classes[cid]
    free = [n for n in cls.ship_names if n not in used]
    name = rng.choice(free) if free else f"{cls.abbrev}-{rng.randrange(100, 999)}"
    used.add(name)
    return name


def _captain(content: ContentDB, cid: str, rng: random.Random, used: set[str] | None = None) -> str:
    """A captain for a ship that joins the squadron: one not already commanding another of its ships."""
    faction = content.factions[content.classes[cid].faction]
    names = [n for n in faction.captain_names if used is None or n not in used] or list(faction.captain_names)
    name = rng.choice(names) if names else ""
    if used is not None and name:
        used.add(name)
    return name


__all__ = ["Fight", "TourRun"]
