"""Each station's report on the battle, and the situation summary the officers' language model is given."""

from __future__ import annotations

import math
import re
from typing import Callable

from ..console.reports import morale_words
from ..help.coach import HelpContext, tips
from ..sim.observation import Observation
from ..sim.ship import Ship, repair_words


def situation(ctx: HelpContext) -> str:
    """A compact, factual summary of what the player's side knows (no hidden information)."""
    s, obs = ctx.ship, ctx.obs
    if s is None or obs is None:
        return "No ship."
    lines = [
        f"Our ship: {s.name}, {s.cls.name}. Hull {pct(s.structure, s.structure_max)}, crew {s.crew}/{s.cls.crew}, "
        f"morale {s.morale:.0f}/100 ({morale_words(s.morale)}). "
        f"Course {s.course:.0f}, warp {s.warp:.1f} (max attainable {s.max_attainable_warp:.1f}). "
        f"Stations run by officers: {', '.join(sorted(s.delegated)) or 'none'}.",
        STATION_REPORTS["engineering"](s, obs),
        STATION_REPORTS["tactical"](s, obs),
    ]
    contacts = sorted((c for c in obs.contacts().values() if c.visible), key=lambda c: c.distance_to(s.x, s.y))
    for c in contacts[:8]:
        d = c.distance_to(s.x, s.y)
        brg = math.degrees(math.atan2(c.x - s.x, c.y - s.y)) % 360
        what = c.cls.name if c.cls else "unidentified"
        scan = ""
        if c.scan is not None:
            scan = f", scanned: hull {c.scan.structure_frac * 100:.0f}%, shields " + "/".join(
                f"{max(0, x):.0f}" for x in c.scan.shields)
        lines.append(f"Contact {contact_name(obs, c.id)} ({what}): range {d:,.0f}, bearing {brg:.0f}, "
                     f"course {c.course:.0f}, warp {math.hypot(c.vx, c.vy) / obs.rules.units_per_warp:.1f}{scan}.")
    allies = [a for a in obs.own_ships() if a.id != s.id and a.alive]
    if allies:
        lines.append("Allies: " + ", ".join(f"{a.name} ({a.cls.abbrev}, hull {pct(a.structure, a.structure_max)})"
                                            for a in allies[:6]) + ".")
    threats = [o for o in obs.threats() if math.hypot(o.x - s.x, o.y - s.y) < 10000]
    if threats:
        lines.append(f"Incoming enemy ordnance: {len(threats)}.")
    advice = tips(ctx)[:3]
    if advice:
        lines.append("Tactical computer notes: " + " ".join(f"{t.title}: {plain(t.text)}" for t in advice))
    return "\n".join(lines)


def helm_report(s: Ship, obs: Observation) -> str:
    c = obs.contact(s.target) if s.target is not None else None
    out = f"Course {s.desired_course:.0f}, warp {s.warp:.1f} of {s.max_attainable_warp:.1f} attainable."
    if c is not None:
        d = c.distance_to(s.x, s.y)
        brg = math.degrees(math.atan2(c.x - s.x, c.y - s.y)) % 360
        out += f" {contact_name(obs, c.id)} bears {brg:.0f} at {d:,.0f}."
    return out


def tactical_report(s: Ship, obs: Observation) -> str:
    parts = []
    if s.banks:
        full = s.cls.banks_charge
        ready = sum(1 for b in s.banks if b.intact and b.charge >= full - 1e-6)
        parts.append(f"{ready}/{len(s.banks)} phaser banks charged")
    if s.tubes:
        loaded = sum(1 for t in s.tubes if t.loaded is not None)
        parts.append(f"{loaded}/{len(s.tubes)} tubes loaded, {s.torps_remaining} torpedoes left")
    if s.launchers:
        parts.append(f"{sum(1 for x in s.launchers if x.loaded)}/{len(s.launchers)} probe launchers ready")
    parts.append(f"point defense {s.pd_doctrine.value}")
    tgt = f"Target: {contact_name(obs, s.target)}." if s.target is not None else "No target selected."
    return f"{tgt} " + ", ".join(parts) + "."


def engineering_report(s: Ship, obs: Observation) -> str:
    sh = [x for x in s.shields if not x.destroyed]
    weakest = min(sh, key=lambda x: x.effective, default=None)
    temp = max((d.temp for d in s.drives if not d.destroyed), default=0.0)
    cap = s.battery_capacity()
    batt = f"batteries {pct(s.battery_charge(), cap)}" if cap > 0 else "no batteries"
    damaged = sum(1 for x in s.subsystems() if x.damage > 0)
    out = f"Hull {pct(s.structure, s.structure_max)}, {batt}, drive temperature {temp:.0f} of {obs.rules.temp_limit:.0f}."
    if weakest is not None:
        out += f" Weakest shield is {weakest.index + 1} at {weakest.effective:.0f}%."
    if damaged:
        out += f" {damaged} systems damaged; repairs on {repair_words(s.repair_priority, 'everything')}."
    return out


def science_report(s: Ship, obs: Observation) -> str:
    cs = list(obs.contacts().values())
    seen = [c for c in cs if c.visible]
    unscanned = [c for c in seen if c.scan is None]
    out = f"{len(seen)} contacts on sensors, {len(cs) - len(seen)} lost."
    if unscanned:
        out += " Not yet scanned: " + ", ".join(contact_name(obs, c.id) for c in unscanned[:4]) + "."
    return out


STATION_REPORTS: dict[str, Callable[[Ship, Observation], str]] = {
    "helm": helm_report, "tactical": tactical_report, "engineering": engineering_report, "science": science_report,
}


def contact_name(obs: Observation, sid: int | None) -> str:
    if sid is None:
        return "nothing"
    own = obs.own(sid)
    if own is not None:
        return own.name
    c = obs.contact(sid)
    if c is None:
        return f"#{sid}"
    return c.label.split(" (")[0] if c.identified else f"#{sid}"


def pct(v: float, of: float) -> str:
    return f"{100 * max(0.0, v) / max(1e-9, of):.0f}%"


def plain(md: str) -> str:
    return re.sub(r"\*\*|`", "", md).strip()


__all__ = ["STATION_REPORTS", "contact_name", "pct", "plain", "situation"]
