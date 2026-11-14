"""The Ready Room's counsel [E]: each officer's view of the next stop, in two sentences.

Before a battle the officers know only what the tour knows: the enemy expected at the stop (and how their
navies like to fight), the mission if there is one, the squadron as Geordi expects it to arrive, the
reinforcement calls left and the choice the stop asks. Each officer reads that from their own station, as
in the battle's counsel (crew/counsel.py): Worf the force to beat, Spock the geometry, Geordi the ships and
the magazines, Seven what the sensors cannot yet tell us. Nothing here is drawn; ui/tour_scene.py shows it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..content.schema import Faction, ShipClass
from ..sim.mission import MissionDef
from .log import NUMBERS, _force
from .model import Stop, WaveDef
from .run import TourRun
from .state import ShipRecord

READY_ORDER = ("worf", "spock", "geordi", "seven")
STYLE_WORDS = {"charge": "the charge", "feint": "the feint", "raid": "the raid"}


@dataclass(frozen=True)
class ReadyView:
    officer: str                 # spock | worf | geordi | seven
    station: str                 # tactical | helm | engineering | science
    text: str                    # two sentences, in their manner


def _count(n: int) -> str:
    return NUMBERS[n] if n < len(NUMBERS) else str(n)


def _weight(cls: ShipClass) -> float:
    """A rough fighting weight, the same shape as the debrief's design value (sim/scoring.py)."""
    return 1.0 + cls.banks * cls.banks_range / 1000.0 + cls.tubes * 6.0 + cls.mass / 40.0


@dataclass(frozen=True)
class _Brief:
    """What the tour knows about the next stop, read once and shared by the four officers."""
    run: TourRun
    stop: Stop
    foes: list[ShipClass]                # the enemy expected there, by class
    waves: list[WaveDef]                 # more groups due after the first
    squadron: list[ShipRecord]           # ours, as Geordi expects them to arrive
    odds: float                          # their fighting weight over ours
    navy: dict[str, Faction]             # the enemy's navies
    styles: set[str]                     # those navies' favourite tactics
    borg: bool
    kinds: dict[str, int]                # "klingon battle cruiser" -> how many
    one_navy: bool                       # several ships, all of one navy

    @property
    def mission(self) -> MissionDef | None:
        return self.stop.mission

    @property
    def has_cube(self) -> bool:
        return any("cube" in c.name.lower() for c in self.foes)


def _brief(run: TourRun, stop: Stop) -> _Brief:
    content = run.content
    flags = run.flags()
    foes = [content.classes[c] for c in stop.enemy_ships(flags) if c in content.classes]
    waves = stop.active_waves(flags)
    squadron = [r for r in run.projected() if r.active]
    ours = [content.classes[r.class_id] for r in squadron]
    their_w = sum(_weight(c) for c in foes)
    our_w = sum(_weight(c) for c in ours)
    factions = {c.faction for c in foes}
    navy = {f: content.factions[f] for f in factions if f in content.factions}
    one_navy = len(navy) == 1 and len(factions) == 1 and len(foes) > 1
    kinds: dict[str, int] = {}
    for c in foes:
        k = (c.name.lower() if one_navy or c.faction not in navy
             else f"{navy[c.faction].name} {c.name.lower()}")
        kinds[k] = kinds.get(k, 0) + 1
    return _Brief(
        run=run, stop=stop, foes=foes, waves=waves, squadron=squadron,
        odds=their_w / our_w if our_w > 0 else 9.0, navy=navy,
        styles={s for f in navy.values() for s, p in f.doctrine.styles.items() if p >= 0.3},
        borg="borg" in factions, kinds=kinds, one_navy=one_navy,
    )


def _worf(b: _Brief) -> str:
    """The force to beat, and where to strike."""
    if not b.foes:
        return "Sensors show no enemy at the rendezvous yet. I do not trust an empty sky."
    if b.has_cube:
        w = "Nothing we have matches a cube ship for ship."
    elif b.odds >= 1.6:
        w = "They outgun us; we cannot trade blows evenly and win."
    elif b.odds >= 0.9:
        w = "The odds are close to even. The side that concentrates its fire will carry the day."
    else:
        w = "We have the stronger force. Press them hard and they will break."
    return w + _worf_aim(b)


def _worf_aim(b: _Brief) -> str:
    m = b.mission
    ranked = sorted(b.foes, key=_weight, reverse=True)
    biggest = ranked[0] if ranked else None
    second = _weight(ranked[1]) if len(ranked) > 1 else 0.0
    if m is not None and m.kind == "intercept":
        return " The runner is the target; her escorts only matter if they stand in our way."
    if m is not None and m.kind in ("rescue", "escort"):
        return f" Some of them will go for the {m.ward_name or 'ship we protect'}; those die first."
    if b.borg and b.has_cube:
        return " Power alone will not do it; we must find the opening and strike through it."
    if b.borg:
        return " Borg ships mend themselves; finish each one before you turn to the next."
    if biggest is not None and len(b.foes) > 1 and _weight(biggest) >= 1.3 * second:
        return f" Destroy the {biggest.name.lower()} first; without her the rest are only escorts."
    if len(b.foes) > 1:
        return " Concentrate on one ship at a time; a wounded enemy still fires, a destroyed one does not."
    return " Bring every tube to bear on her and do not let her recharge."


def _spock(b: _Brief) -> str:
    """The geometry of the engagement."""
    if b.borg:
        s = "The cube cannot be outrun indefinitely; distance buys time, not victory."
    elif "charge" in b.styles:
        s = ("Klingon captains favour the charge: meet it with torpedoes at long range, then turn away while "
             "their banks recharge.")
    elif "feint" in b.styles:
        s = "A Romulan who turns to run is usually inviting pursuit into a full spread; do not follow blindly."
    elif "raid" in b.styles:
        s = "Orion raiders strike and withdraw; keep close to what they want rather than chase them."
    elif b.foes:
        s = "I expect a conventional approach; the first exchange will be decided by who controls the range."
    else:
        s = "With no contact to plot, I will hold a course that keeps our options open."
    m = b.mission
    if m is not None and m.kind == "escort":
        s += f" The {m.ward_name or 'convoy'} will hold her course, so we must place ourselves between her and them."
    elif m is not None and m.kind == "rescue":
        s += (" Beaming people across means lowering our shield inside transporter range, so the approach must "
              "be covered.")
    elif m is not None and m.kind == "intercept":
        s += " She will hold her heading; an intercept course laid early costs far less than a stern chase."
    elif b.waves:
        s += " More ships are expected after the first; I would not spend everything on the opening exchange."
    return s


def _geordi(b: _Brief) -> str:
    """The ships and the magazines."""
    squadron = b.squadron
    flag = next((r for r in squadron if r.role == "flagship"), squadron[0] if squadron else None)
    if flag is None:
        return "We have nothing left to send, Captain."
    weakest = min(squadron, key=lambda r: r.hull)
    if flag.hull >= 0.95 and weakest.hull >= 0.95:
        g = ("Every ship should arrive at full strength." if len(squadron) > 1
             else f"The {flag.name} should arrive at full strength.")
    elif weakest is not flag and weakest.hull < flag.hull - 0.1:
        g = (f"The {weakest.name} will still be at about {round(weakest.hull * 100)}% hull when we get there; "
             f"she should not lead.")
    else:
        g = f"We should arrive at about {round(flag.hull * 100)}% hull."
    return g + _geordi_advice(b, flag)


def _geordi_advice(b: _Brief, flag: ShipRecord) -> str:
    run, content, squadron = b.run, b.run.content, b.squadron
    full = content.classes[flag.class_id].torps_carried
    torps = flag.torps_now(content)
    refit = next((c for c in b.stop.choices if c.refit and not c.flagship), None)   # repairs, not a story refit
    lean = [r for r in squadron if r is not flag and 0 < content.classes[r.class_id].torps_carried < 1000]
    short = min(lean, key=lambda r: r.torps_now(content), default=None)
    worn = flag.hull < 0.85 or (0 < full < 1000 and torps < full * 0.5) or any(r.hull < 0.6 for r in squadron)
    if refit is not None and worn:
        return f" If '{refit.label}' is on the table, I'd take it."
    if refit is not None:
        return f" We don't need '{refit.label}': I'd keep the time rather than spend it in dock."
    if 0 < full < 1000 and torps < full * 0.35:
        return f" We are down to {torps} torpedoes; make every one count."
    if run.state.calls_left > 0 and b.odds >= 1.3:
        late = max(0.0, b.stop.eta - run.transit_cycles())
        return (" Call Starfleet now and their ship meets us there"
                + (f", about {late:.0f} cycles in." if late > 0 else "."))
    if short is not None:
        return (f" The {short.name} carries only {short.torps_now(content)} torpedoes; she will run dry long before "
                "we do, so her salvos are for finishing a ship, not long shots.")
    return " Engineering is ready for whatever you need."


def _seven(b: _Brief) -> str:
    """What the sensors cannot yet tell us."""
    m = b.mission
    cloakers = [c for c in b.foes if c.can_cloak]
    if m is not None and m.kind == "rescue":
        v = (f"{m.people} people aboard the {m.ward_name or 'stricken ship'}"
             + (f", and her life support will fail in about {m.deadline:.0f} cycles." if m.deadline > 0 else "."))
    elif cloakers:
        v = (f"The {cloakers[0].name.lower()} can cloak; our sensors will lose her, but her torpedoes will "
             f"still give her away.")
    elif b.waves:
        v = "Long-range sensors show more ships behind the first group. Their number is not yet clear."
    elif b.foes:
        v = (f"Sensors read {_count(len(b.foes))} {next(iter(b.navy.values())).name} ships at the rendezvous: "
             f"{_force(b.kinds)}." if b.one_navy else f"Sensors read {_force(b.kinds)} at the rendezvous.")
    else:
        v = "Sensors read nothing at the rendezvous."
    if b.borg:
        v += " The Collective adapts to what it has seen; vary the attack and remodulate when it stops working."
    elif m is not None and m.kind == "intercept":
        v += " A scan of the runner will tell us which of her systems to disable."
    else:
        v += " A full scan early will show where their shields are weakest."
    return v


def ready_counsel(run: TourRun) -> list[ReadyView]:
    """Each officer's two sentences on the next stop ([] when the tour is over)."""
    stop = run.stop
    if stop is None or run.over:
        return []
    b = _brief(run, stop)
    out = [ReadyView("worf", "tactical", _worf(b)), ReadyView("spock", "helm", _spock(b)),
           ReadyView("geordi", "engineering", _geordi(b)), ReadyView("seven", "science", _seven(b))]
    order = {o: i for i, o in enumerate(READY_ORDER)}
    return sorted(out, key=lambda r: order[r.officer])


__all__ = ["READY_ORDER", "ReadyView", "ready_counsel"]
