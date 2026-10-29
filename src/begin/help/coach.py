"""Live help content: weapon tables from the game data and the tactical coach.

Help pages insert these with `{{name}}` placeholders:

* `{{torpedo_table}}`, `{{probe_table}}`, `{{class_table}}`: reference tables built from the content data;
* `{{my_weapons}}`: the weapons fitted to the ship you command;
* `{{phaser_falloff}}`: how your phaser hits weaken with range and spread;
* `{{coach}}`: advice for the situation you are in right now.

Everything is computed from the same numbers the simulation uses, so the
help stays right when the content files change. In battle the coach reads
only your side's `Observation`, the same information the AI gets.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

from ..ai.computer import torpedo_envelope
from ..content.schema import ContentDB, ProbeDef, TorpedoDef
from ..core.angles import bearing, norm360
from ..sim.observation import ContactView, Observation
from ..sim.ship import Ship


@dataclass
class HelpContext:
    content: ContentDB
    obs: Observation | None = None
    ship: Ship | None = None

    @property
    def upw(self) -> float:
        return self.obs.rules.units_per_warp if self.obs is not None else 100.0


WARHEAD = {0: "antimatter", 1: "shield-bore", 2: "plasma (fades with distance)"}


def _users(content: ContentDB, attr: str, oid: str) -> str:
    names = sorted({f"{content.factions[c.faction].name} {c.name}" for c in content.classes.values()
                    if getattr(c, attr) == oid})
    return ", ".join(names) if names else "-"


def torpedo_stats(t: TorpedoDef, upw: float) -> dict[str, float]:
    speed = t.velocity * upw
    return {"speed": speed, "arm": t.arm_time * speed, "reach": (t.arm_time + t.max_time_fuse) * speed}


def torpedo_table(ctx: HelpContext) -> str:
    rows = ["| Torpedo | Id | Warp | Warhead | Arms at | Reach | Max prox | Guidance | Reload | Carried by |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for t in sorted(ctx.content.torpedoes.values(), key=lambda t: -t.damage):
        st = torpedo_stats(t, ctx.upw)
        rows.append(
            f"| {t.name} | `{t.id}` | {t.velocity:g} | {t.damage:g} {WARHEAD.get(t.warhead_type, '')} | "
            f"{st['arm']:,.0f} | {st['reach']:,.0f} | {t.max_prox:,.0f} | {'homing' if t.homing else 'straight'} | "
            f"{t.charge_time:g} c | {_users(ctx.content, 'torpedo', t.id)} |")
    return "\n".join(rows)


def probe_table(ctx: HelpContext) -> str:
    rows = ["| Probe | Id | Warp | Warhead | Arms after | Time fuse | Reach | Max prox | Sensor | Carried by |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    for p in sorted(ctx.content.probes.values(), key=lambda p: -p.damage):
        reach = p.velocity * ctx.upw * p.max_time_fuse
        rows.append(
            f"| {p.name} | `{p.id}` | {p.velocity:g} | {p.damage:g} | {p.arm_time:g} c | {p.max_time_fuse:g} c | "
            f"{reach:,.0f} | {p.max_prox:,.0f} | {p.scan_range:,.0f} | {_users(ctx.content, 'probe', p.id)} |")
    return "\n".join(rows)


def class_table(ctx: HelpContext) -> str:
    rows = ["| Ship | Nation | Max warp | Phasers (range) | Tubes | Probes | Shields | Crew |",
            "|---|---|---|---|---|---|---|---|"]
    for c in sorted(ctx.content.classes.values(), key=lambda c: (c.faction, c.mass)):
        rows.append(f"| {c.name} (`{c.abbrev}`) | {ctx.content.factions[c.faction].name} | {c.max_warp:g} | "
                    f"{c.banks} ({c.banks_range:,.0f}) | {c.tubes} × {c.torpedo or '-'} | {c.launchers} × {c.probe or '-'} | "
                    f"{c.shields} × {c.shield_strength:g} | {c.crew} |")
    return "\n".join(rows)


def my_weapons(ctx: HelpContext) -> str:
    s = ctx.ship
    if s is None:
        return "> **Note** Start a battle to see the weapons of the ship you command."
    c = s.cls
    out = [f"You command the **{s.name}**, a {ctx.content.factions[s.faction].name} {c.name}.", ""]
    if s.banks:
        out.append(f"- **Phasers:** {len(s.banks)} banks, range {c.banks_range:,.0f}, full charge in {c.banks_rate:g} cycles.")
    if s.tubes:
        t = ctx.content.torpedoes.get(s.tubes[0].load_ordnance or c.torpedo)
        if t is not None:
            st = torpedo_stats(t, ctx.upw)
            out.append(f"- **Torpedoes:** {len(s.tubes)} tubes of {t.name} (`{t.id}`): warhead {t.damage:g}, "
                       f"warp {t.velocity:g}, arms after {st['arm']:,.0f}, runs out at {st['reach']:,.0f}. "
                       f"{s.torps_remaining} left.")
        others = [x for x in ctx.content.factions[s.faction].torpedoes if x != (t.id if t else "")]
        if others:
            out.append(f"  Also available to you: {', '.join(f'`{x}`' for x in others)} (switch with `autoload tor <id>`).")
    if s.launchers:
        p = ctx.content.probes.get(s.launchers[0].load_ordnance or c.probe)
        if p is not None:
            out.append(f"- **Probes:** {len(s.launchers)} launchers of {p.name} (`{p.id}`): warhead {p.damage:g}, "
                       f"warp {p.velocity:g}, {'homing' if p.homing else 'straight'}. {s.probes_remaining} left.")
    return "\n".join(out)


def phaser_falloff(ctx: HelpContext) -> str:
    s = ctx.ship
    cls = s.cls if s is not None else next(iter(ctx.content.classes.values()))
    rules = ctx.obs.rules if ctx.obs is not None else None
    mult = rules.phaser_dam_mult if rules else 45.0
    half = rules.phaser_half if rules else 0.5
    rows = [f"Damage per bank for a {cls.name} (charge {cls.banks_charge:g}, range {cls.banks_range:,.0f}) "
            "before shields:", "", "| Range | Spread 10 | Spread 20 | Spread 45 |", "|---|---|---|---|"]
    for f in (0.0, 0.25, 0.5, 0.75, 0.9):
        d = cls.banks_range * f
        k = math.sqrt(max(0.0, 1.0 - f)) * half
        rows.append(f"| {d:,.0f} | {cls.banks_charge * mult / 10 * k:.0f} | {cls.banks_charge * mult / 20 * k:.0f} | "
                    f"{cls.banks_charge * mult / 45 * k:.0f} |")
    return "\n".join(rows)


# ------------------------------------------------------------------ the coach

def _contact_name(c: ContactView) -> str:
    return c.label.split(" (")[0] if c.identified else f"#{c.id}"


# which bridge station each piece of advice belongs to (officers speak to their own)
TIP_STATIONS = {
    "Incoming ordnance": "tactical", "Pick a target": "tactical", "Find the enemy": "science",
    "Too close for torpedoes": "helm", "Out of torpedo reach": "helm", "Torpedo shot is on": "tactical",
    "Switch torpedoes": "tactical", "Heavier torpedo available": "tactical", "Proximity fuse": "tactical",
    "Phasers in range": "tactical", "Closing to phaser range": "helm", "Probe it": "tactical",
    "Scan the target": "science", "Their shields": "science", "Turn a fresh shield toward them": "helm",
    "Engines running hot": "engineering", "Power is running out": "engineering", "Badly damaged": "engineering",
}


@dataclass
class Tip:
    priority: int          # 0 is most urgent
    title: str
    text: str              # Markdown
    commands: list[str]
    station: str = "tactical"


def tips(ctx: HelpContext) -> list[Tip]:
    """Situational advice, most urgent first. Every suggestion comes with the command that carries it out."""
    s, obs = ctx.ship, ctx.obs
    if s is None or obs is None or not s.alive:
        return []
    out: list[Tip] = []
    upw = obs.rules.units_per_warp

    def tip(prio: int, title: str, text: str, *cmds: str) -> None:
        out.append(Tip(prio, title, text, list(cmds), TIP_STATIONS.get(title, "tactical")))

    threats = [o for o in obs.threats() if math.hypot(o.x - s.x, o.y - s.y) < 8000]
    if threats:
        n = len(threats)
        doctrine = s.pd_doctrine.value
        tip(0, "Incoming ordnance",
            f"{n} enemy {'weapon is' if n == 1 else 'weapons are'} inbound. Point defense is **{doctrine}**. "
            "Turning so a strong shield faces the threat, or running at right angles to its course, also helps.",
            *(["pd aggressive"] if doctrine in ("off", "conservative") else []))

    c = obs.contact(s.target) if s.target is not None else None
    if c is None:
        hostile = sorted((h for h in obs.hostile_contacts() if h.visible), key=lambda h: h.distance_to(s.x, s.y))
        if hostile:
            h = hostile[0]
            tip(1, "Pick a target", f"Nearest enemy: **{_contact_name(h)}** at {h.distance_to(s.x, s.y):,.0f}. "
                "Weapons locked on a target lead it automatically.", f"target {_contact_name(h).lower()}")
        else:
            tip(1, "Find the enemy", "Nothing hostile on sensors. Widen the display or check the chart.", "range 40000", "chart")
    else:
        d = c.distance_to(s.x, s.y)
        name = _contact_name(c)
        tcls = c.cls
        # torpedo envelope and choice
        if s.tubes and any(t.intact for t in s.tubes):
            options = [ctx.content.torpedoes[x] for x in ctx.content.factions[s.faction].torpedoes if x in ctx.content.torpedoes]
            cur_id = s.tubes[0].load_ordnance or s.cls.torpedo
            cur = ctx.content.torpedoes.get(cur_id)
            fits = []
            for t in options:
                lo, hi = torpedo_envelope(s, c.x, c.y, c.vx, c.vy, t.velocity, t.arm_time, t.max_time_fuse, upw)
                fits.append((t, lo, hi, lo <= d <= hi * 0.8))
            if cur is not None:
                lo, hi = next(((lo, hi) for t, lo, hi, _ in fits if t.id == cur.id),
                              torpedo_envelope(s, c.x, c.y, c.vx, c.vy, cur.velocity, cur.arm_time, cur.max_time_fuse, upw))
                loaded = sum(1 for t in s.tubes if t.loaded is not None)
                if d < lo:
                    tip(2, "Too close for torpedoes",
                        f"{name} is {d:,.0f} away but a {cur.name} only arms after about {lo:,.0f} at this closing speed. "
                        "Open the range or use phasers.")
                elif d > hi:
                    tip(3, "Out of torpedo reach",
                        f"{name} is {d:,.0f} away; your {cur.name} runs out at about {hi:,.0f} against this target. "
                        f"Close to under {hi * 0.7:,.0f} for a good shot.", f"pursue {name.lower()}")
                elif loaded:
                    tip(2, "Torpedo shot is on",
                        f"{name} is inside your {cur.name} envelope ({lo:,.0f}–{hi:,.0f}). {loaded} tube"
                        f"{'s are' if loaded != 1 else ' is'} loaded. Torpedoes fired at a manoeuvring target miss more "
                        "the farther they travel, so shots from the nearer half of the envelope hit best.", "fire all torpedoes")
                # better torpedo for this fight?
                better = [f for f in fits if f[3] and f[0].id != cur.id and f[0].damage > cur.damage]
                if better and not (lo <= d <= hi * 0.8):
                    b = max(better, key=lambda f: f[0].damage)[0]
                    tip(3, "Switch torpedoes",
                        f"At {d:,.0f} the {b.name} (warhead {b.damage:g}, warp {b.velocity:g}) fits this range better than "
                        f"your {cur.name} (warhead {cur.damage:g}, warp {cur.velocity:g}).", f"autoload tor {b.id}")
                elif better and d < hi * 0.5:
                    b = max(better, key=lambda f: f[0].damage)[0]
                    tip(4, "Heavier torpedo available",
                        f"Close in, the slower {b.name} hits {b.damage / max(1.0, cur.damage):.1f}× as hard as the {cur.name}.",
                        f"autoload tor {b.id}")
                # proximity fuse matched to the target's agility (the Begin AI's rule)
                if tcls is not None:
                    want = max(obs.rules.prox_floor, min(tcls.max_warp * 50.0, cur.max_prox))
                    have = s.tubes[0].load_prox or cur.max_prox
                    if abs(have - want) > want * 0.25:
                        tip(4, "Proximity fuse",
                            f"A {tcls.name} manoeuvres at up to warp {tcls.max_warp:g}; a proximity of about {want:,.0f} "
                            f"suits it (yours: {have:,.0f}). Wider fuses catch agile ships but deliver less of the blast.",
                            f"load tubes prox {want:.0f}")
        # phasers
        if s.banks and any(b.intact for b in s.banks):
            r = s.cls.banks_range
            ready = sum(1 for b in s.banks if b.intact and b.charge >= s.cls.banks_charge - 1e-6)
            if d < r:
                k = math.sqrt(max(0.0, 1 - d / r)) * 100
                tip(2, "Phasers in range",
                    f"{name} is at {d:,.0f} of your {r:,.0f} phaser range; hits land at {k:.0f}% of point-blank strength. "
                    f"{ready} bank{'s are' if ready != 1 else ' is'} charged. Spread 10 concentrates the hit on one ship.",
                    "fire all phasers spread 10")
            elif d < r * 2:
                tip(3, "Closing to phaser range", f"{d - r:,.0f} more to phaser range ({r:,.0f}). "
                    "Every 10% closer adds noticeably to each hit.", f"pursue {name.lower()}")
        # probes against slow ships
        if s.launchers and any(lch.loaded for lch in s.launchers) and tcls is not None:
            p = ctx.content.probes.get(s.launchers[0].load_ordnance or s.cls.probe)
            if p is not None and p.damage > 0 and tcls.max_warp < p.velocity:
                tip(4, "Probe it", f"A {tcls.name} tops out at warp {tcls.max_warp:g}; your {p.name} runs at warp "
                    f"{p.velocity:g} and homes, so it cannot be outrun. Its warhead is {p.damage:g}.", f"fire probes at {name.lower()}")
        # the enemy's shields
        if c.scan is None:
            tip(4, "Scan the target", f"A scan shows {name}'s shields, weapons and damage, so you know where to hit.",
                f"scan {name.lower()}")
        elif tcls is not None and c.scan.shields:
            facings = (0, 60, 300, 120, 240, 180)
            rel = norm360(bearing(s.x - c.x, s.y - c.y) - c.course)
            face = min(range(len(facings)), key=lambda i: abs((rel - facings[i] + 180) % 360 - 180))
            shields = c.scan.shields
            weakest = min(range(len(shields)), key=lambda i: shields[i] if shields[i] >= 0 else -1)
            if face < len(c.scan.shields):
                tip(3, "Their shields", f"You face {name}'s shield {face + 1} ({max(0, c.scan.shields[face]):.0f}%). "
                    f"Their weakest is shield {weakest + 1} ({max(0, c.scan.shields[weakest]):.0f}%), "
                    f"centred {facings[weakest]}° off their bow.")
        # our shield toward them
        if s.shields:
            rel = norm360(bearing(c.x - s.x, c.y - s.y) - s.course)
            sh = s.shield_for_bearing(rel)
            best = max((x for x in s.shields if not x.destroyed), key=lambda x: x.effective, default=None)
            if sh is not None and best is not None and sh.effective < 40 and best.effective > sh.effective + 30:
                turn = norm360(bearing(c.x - s.x, c.y - s.y) - best.facing)
                tip(1, "Turn a fresh shield toward them",
                    f"Shield {sh.index + 1} facing {name} is down to {sh.effective:.0f}%. Shield {best.index + 1} is at "
                    f"{best.effective:.0f}%: steer {turn:.0f} to put it toward them, or reinforce the weak one.",
                    f"helm {turn:.0f}", f"reenforce {sh.index + 1}")
    # engines and power
    live = [dv for dv in s.drives if not dv.destroyed]
    temp = max((dv.temp for dv in live), default=0.0)
    if temp > obs.rules.temp_limit * 0.8:
        tip(1, "Engines running hot", f"Warp drive temperature {temp:.0f} of {obs.rules.temp_limit:.0f}. "
            "Above the limit a drive burns out; drop to cruise speed for a few cycles.", f"warp {s.cls.cruise_warp:g}")
    cap = s.battery_capacity()
    if cap > 0 and s.battery_charge() < cap * 0.2 and s.power.net < 0:
        tip(1, "Power is running out", "Batteries are below 20% and draining. Lower shields facing away from the "
            "enemy, or disable some banks, until the reactors catch up.", "lower 4 5 6")
    if s.structure < s.structure_max * 0.35:
        tip(2, "Badly damaged", "Hull below 35%. Consider breaking off, docking with a base for repairs, "
            "or beaming to an ally.", "repair all", "fleet")
    out.sort(key=lambda t: t.priority)
    return out


def coach(ctx: HelpContext) -> str:
    """The coach page's live block: the tips as Markdown, with clickable commands."""
    s, obs = ctx.ship, ctx.obs
    if s is None or obs is None:
        return ("> **Coach** Start a battle and the coach will read the situation: your target's range against "
                "your weapons' envelopes, the best torpedo and proximity setting, your shields, heat and power.")
    if not s.alive:
        return "> **Coach** Your ship is out of action. Beam to an ally with `beam <ally>` if one is within 3,000."
    found = tips(ctx)
    if not found:
        return "> **Coach** Nothing urgent. Keep your best shield toward the enemy and watch the torpedo envelope."
    lines: list[str] = []
    for t in found[:7]:
        lines.append(f"### {t.title}")
        lines.append(t.text)
        if t.commands:
            lines.append("```console")
            lines.extend(t.commands)
            lines.append("```")
        lines.append("")
    return "\n".join(lines)


BLOCKS: dict[str, Callable[[HelpContext], str]] = {
    "torpedo_table": torpedo_table,
    "probe_table": probe_table,
    "class_table": class_table,
    "my_weapons": my_weapons,
    "phaser_falloff": phaser_falloff,
    "coach": coach,
}

_PLACEHOLDER = re.compile(r"\{\{\s*([a-z_]+)\s*\}\}")


def expand(body: str, ctx: HelpContext) -> str:
    def sub(m: re.Match[str]) -> str:
        fn = BLOCKS.get(m.group(1))
        if fn is None:
            return m.group(0)
        try:
            return fn(ctx)
        except Exception as e:  # noqa: BLE001 — a broken live block must not take the manual down
            return f"> **Note** This section could not be built ({e.__class__.__name__})."
    return _PLACEHOLDER.sub(sub, body)


__all__ = ["BLOCKS", "HelpContext", "TIP_STATIONS", "Tip", "coach", "expand", "probe_table", "tips", "torpedo_table"]
