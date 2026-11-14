"""The Ready Room's counsel [E]: each officer's view of the next stop, in two sentences.

Before a battle the officers know only what the tour knows: the enemy expected at the stop (and how their
navies like to fight), the mission if there is one, the squadron as Geordi expects it to arrive, the
reinforcement calls left and the choice the stop asks. Each officer reads that from their own station, as
in the battle's counsel (crew/counsel.py): Worf the force to beat, Spock the geometry, Geordi the ships and
the magazines, Seven what the sensors cannot yet tell us. Nothing here is drawn; ui/tour_scene.py shows it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..content.schema import ShipClass
from .log import NUMBERS, _force
from .run import TourRun

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


def ready_counsel(run: TourRun) -> list[ReadyView]:  # noqa: C901
    """Each officer's two sentences on the next stop ([] when the tour is over)."""
    stop = run.stop
    if stop is None or run.over:
        return []
    content = run.content
    flags = run.flags()
    foes = [content.classes[c] for c in stop.enemy_ships(flags) if c in content.classes]
    waves = stop.active_waves(flags)
    squadron = [r for r in run.projected() if r.active]
    ours = [content.classes[r.class_id] for r in squadron]
    their_w = sum(_weight(c) for c in foes)
    our_w = sum(_weight(c) for c in ours)
    odds = their_w / our_w if our_w > 0 else 9.0
    factions = {c.faction for c in foes}
    navy = {f: content.factions[f] for f in factions if f in content.factions}
    styles = {s for f in navy.values() for s, p in f.doctrine.styles.items() if p >= 0.3}
    borg = "borg" in factions
    cloakers = [c for c in foes if c.can_cloak]
    ranked = sorted(foes, key=_weight, reverse=True)
    biggest = ranked[0] if ranked else None
    second = _weight(ranked[1]) if len(ranked) > 1 else 0.0
    one_navy = len(navy) == 1 and len(factions) == 1 and len(foes) > 1
    kinds: dict[str, int] = {}
    for c in foes:
        k = (c.name.lower() if one_navy or c.faction not in navy
             else f"{navy[c.faction].name} {c.name.lower()}")
        kinds[k] = kinds.get(k, 0) + 1
    m = stop.mission
    out: list[ReadyView] = []

    # Worf: the force to beat, and where to strike
    if not foes:
        w = "Sensors show no enemy at the rendezvous yet. I do not trust an empty sky."
    else:
        if any("cube" in c.name.lower() for c in foes):
            w = "Nothing we have matches a cube ship for ship."
        elif odds >= 1.6:
            w = "They outgun us; we cannot trade blows evenly and win."
        elif odds >= 0.9:
            w = "The odds are close to even. The side that concentrates its fire will carry the day."
        else:
            w = "We have the stronger force. Press them hard and they will break."
        if m is not None and m.kind == "intercept":
            w += " The runner is the target; her escorts only matter if they stand in our way."
        elif m is not None and m.kind in ("rescue", "escort"):
            w += f" Some of them will go for the {m.ward_name or 'ship we protect'}; those die first."
        elif borg and any("cube" in c.name.lower() for c in foes):
            w += " Power alone will not do it; we must find the opening and strike through it."
        elif borg:
            w += " Borg ships mend themselves; finish each one before you turn to the next."
        elif biggest is not None and len(foes) > 1 and _weight(biggest) >= 1.3 * second:
            w += f" Destroy the {biggest.name.lower()} first; without her the rest are only escorts."
        elif len(foes) > 1:
            w += " Concentrate on one ship at a time; a wounded enemy still fires, a destroyed one does not."
        else:
            w += " Bring every tube to bear on her and do not let her recharge."
    out.append(ReadyView("worf", "tactical", w))

    # Spock: the geometry of the engagement
    if borg:
        s = "The cube cannot be outrun indefinitely; distance buys time, not victory."
    elif "charge" in styles:
        s = ("Klingon captains favour the charge: meet it with torpedoes at long range, then turn away while "
             "their banks recharge.")
    elif "feint" in styles:
        s = "A Romulan who turns to run is usually inviting pursuit into a full spread; do not follow blindly."
    elif "raid" in styles:
        s = "Orion raiders strike and withdraw; keep close to what they want rather than chase them."
    elif foes:
        s = "I expect a conventional approach; the first exchange will be decided by who controls the range."
    else:
        s = "With no contact to plot, I will hold a course that keeps our options open."
    if m is not None and m.kind == "escort":
        s += f" The {m.ward_name or 'convoy'} will hold her course, so we must place ourselves between her and them."
    elif m is not None and m.kind == "rescue":
        s += (" Beaming people across means lowering our shield inside transporter range, so the approach must "
              "be covered.")
    elif m is not None and m.kind == "intercept":
        s += " She will hold her heading; an intercept course laid early costs far less than a stern chase."
    elif waves:
        s += " More ships are expected after the first; I would not spend everything on the opening exchange."
    out.append(ReadyView("spock", "helm", s))

    # Geordi: the ships and the magazines
    flag = next((r for r in squadron if r.role == "flagship"), squadron[0] if squadron else None)
    if flag is None:
        g = "We have nothing left to send, Captain."
    else:
        weakest = min(squadron, key=lambda r: r.hull)
        if flag.hull >= 0.95 and weakest.hull >= 0.95:
            g = ("Every ship should arrive at full strength." if len(squadron) > 1
                 else f"The {flag.name} should arrive at full strength.")
        elif weakest is not flag and weakest.hull < flag.hull - 0.1:
            g = (f"The {weakest.name} will still be at about {round(weakest.hull * 100)}% hull when we get there; "
                 f"she should not lead.")
        else:
            g = f"We should arrive at about {round(flag.hull * 100)}% hull."
        full = content.classes[flag.class_id].torps_carried
        torps = flag.torps_now(content)
        refit = next((c for c in stop.choices if c.refit and not c.flagship), None)   # repairs, not a story refit
        lean = [r for r in squadron if r is not flag and 0 < content.classes[r.class_id].torps_carried < 1000]
        short = min(lean, key=lambda r: r.torps_now(content), default=None)
        worn = flag.hull < 0.85 or (0 < full < 1000 and torps < full * 0.5) or any(r.hull < 0.6 for r in squadron)
        if refit is not None and worn:
            g += f" If '{refit.label}' is on the table, I'd take it."
        elif refit is not None:
            g += f" We don't need '{refit.label}': I'd keep the time rather than spend it in dock."
        elif 0 < full < 1000 and torps < full * 0.35:
            g += f" We are down to {torps} torpedoes; make every one count."
        elif run.state.calls_left > 0 and odds >= 1.3:
            late = max(0.0, stop.eta - run.transit_cycles())
            g += (" Call Starfleet now and their ship meets us there"
                  + (f", about {late:.0f} cycles in." if late > 0 else ".") )
        elif short is not None:
            g += (f" The {short.name} carries only {short.torps_now(content)} torpedoes; she will run dry long before "
                  "we do, so her salvos are for finishing a ship, not long shots.")
        else:
            g += " Engineering is ready for whatever you need."
    out.append(ReadyView("geordi", "engineering", g))

    # Seven: what the sensors cannot yet tell us
    if m is not None and m.kind == "rescue":
        v = (f"{m.people} people aboard the {m.ward_name or 'stricken ship'}"
             + (f", and her life support will fail in about {m.deadline:.0f} cycles." if m.deadline > 0 else "."))
    elif cloakers:
        v = (f"The {cloakers[0].name.lower()} can cloak; our sensors will lose her, but her torpedoes will "
             f"still give her away.")
    elif waves:
        v = "Long-range sensors show more ships behind the first group. Their number is not yet clear."
    elif foes:
        v = (f"Sensors read {_count(len(foes))} {next(iter(navy.values())).name} ships at the rendezvous: "
             f"{_force(kinds)}." if one_navy else f"Sensors read {_force(kinds)} at the rendezvous.")
    else:
        v = "Sensors read nothing at the rendezvous."
    if borg:
        v += " The Collective adapts to what it has seen; vary the attack and remodulate when it stops working."
    elif m is not None and m.kind == "intercept":
        v += " A scan of the runner will tell us which of her systems to disable."
    else:
        v += " A full scan early will show where their shields are weakest."
    out.append(ReadyView("seven", "science", v))
    order = {o: i for i, o in enumerate(READY_ORDER)}
    return sorted(out, key=lambda r: order[r.officer])


__all__ = ["READY_ORDER", "ReadyView", "ready_counsel"]
