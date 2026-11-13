"""Live blocks for the captain's manual [E]: the crew, the powers, the crew's joint projects, the battles and tours
that ship with the game, and every order the console knows. Each is built from the game's own data, so the manual
changes when the game does (help/book.py, tests/test_manual.py).

They work like the coach's blocks (`{{crew_roster}}` in a help page) and are registered in `coach.BLOCKS`. Only
what ships with the game is shown: a player's own officers, tours or help pages never leak into the manual.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .coach import HelpContext

STATION_NAMES = {"helm": "Helm", "tactical": "Tactical", "engineering": "Engineering", "science": "Science",
                 "sickbay": "Sickbay"}

# a race's signature way of fighting (content/data/doctrines.toml `styles`), in a captain's words
STYLE_WORDS = {
    "charge": "the charge: a point-blank run at full speed, an alpha strike, a break to recharge, and again",
    "feint": "the feint: they turn and run when you close (cloaking if they can), then turn on the pursuer "
             "with a full spread",
    "raid": "the raid: in, one volley, and out of reach before you can answer",
}


def crew_roster(ctx: HelpContext) -> str:
    """Who is on the bridge, what each runs, who stands in for whom, and how they come across."""
    from ..crew.characters import load_officers

    officers = load_officers()
    rows = ["| Officer | Station | How they come across |", "|---|---|---|"]
    runs: dict[str, str] = {}
    for o in officers.values():
        runs.setdefault(o.station, o.name)            # the first officer listed for a station runs it
    for o in officers.values():
        name = f"{o.rank} {o.name}".strip()
        post = STATION_NAMES.get(o.station, o.station)
        if runs.get(o.station) != o.name:
            post = "Stands by"
        cover = [f"{STATION_NAMES.get(c, c).lower()} for {runs[c]}" for c in o.covers if runs.get(c, o.name) != o.name]
        if cover:
            post += f"; takes {' and '.join(cover)} when needed"
        rows.append(f"| **{name}** | {post} | {', '.join(o.traits)} |")
    return "\n".join(rows)


def faction_profiles(ctx: HelpContext) -> str:
    """Each power: its ships, its weapons, how its captains fight, and how they take a hail."""
    content = ctx.content
    out: list[str] = []
    for f in content.factions.values():
        d = f.doctrine
        ships = sorted((c for c in content.classes.values() if c.faction == f.id and not c.story and not c.craft),
                       key=lambda c: c.mass)
        torps = ", ".join(content.torpedoes[t].name for t in f.torpedoes if t in content.torpedoes) or "none"
        probes = ", ".join(content.probes[p].name for p in f.probes if p in content.probes) or "none"
        out.append(f"### {f.long_name or f.name}")
        out.append("")
        out.append(f"- **Ships:** {', '.join(c.name for c in ships)}.")
        out.append(f"- **Torpedoes:** {torps}. **Probes:** {probes}.")
        lean = {"phaser": "phasers", "torpedo": "torpedoes", "probe": "probes"}[
            max(d.weapon_bias, key=lambda k: d.weapon_bias[k])]
        style = next(iter(d.styles), "")
        fights = [f"they lean on their {lean}"]
        if style in STYLE_WORDS:
            fights.append(f"many of their captains favour {STYLE_WORDS[style]}")
        if d.cloak_ambush > 0:
            fights.append("they cloak to close and to reposition")
        if f.orders:
            fights.append(f"their helms are drilled in {', '.join(f.orders)} manoeuvres")
        out.append(f"- **How they fight:** {'; '.join(fights)}.")
        if f.collective is not None:
            out.append("- **Terms:** none. The Collective never bargains, never retreats and never surrenders.")
        else:
            temper = "angry" if f.temper >= 0.6 else "frightened" if f.temper <= 0.25 else "wary"
            stubborn = ("very stubborn" if f.obstinacy >= 0.7 else "stubborn" if f.obstinacy >= 0.5
                        else "easily talked round")
            yields = ("almost never" if d.surrender_willingness < 0.05 else "rarely" if d.surrender_willingness < 0.3
                      else "readily")
            out.append(f"- **Terms:** watching their allies battered makes them {temper}; at the start they are "
                       f"{stubborn}, and they {yields} strike their colours. Crew spirits start at {f.morale_start:.0f}.")
        out.append("")
    return "\n".join(out).rstrip()


def collaborations(ctx: HelpContext) -> str:
    """The projects officers build together when asked: who, and what it is for."""
    from ..crew.collaborations import COLLABORATIONS
    from ..crew.characters import load_officers
    from ..sim.projects import PROJECTS

    officers = load_officers()
    rows = ["| Project | Built by | Ask for it with |", "|---|---|---|"]
    for c in COLLABORATIONS:
        p = PROJECTS.get(c.project)
        what = p.title if p is not None else c.project
        names = [officers[o].name for o in c.officers if o in officers]
        who = ", ".join(names[:-1]) + (" and " if len(names) > 1 else "") + names[-1] if names else "-"
        rows.append(f"| {what[:1].upper()}{what[1:]} | {who} | `design {c.project}` |")
    return "\n".join(rows)


def preset_list(ctx: HelpContext) -> str:
    """The curated battles on the main menu."""
    from ..presets import load_presets

    return "\n".join(f"- **{p.title}.** {p.description}" for p in load_presets())


def tour_list(ctx: HelpContext) -> str:
    """The tours of duty that ship with the game, and their stops."""
    from ..tour.model import load_tours

    out: list[str] = []
    for t in load_tours(user_dir=None)[0]:
        stops = " → ".join(s.title for s in t.stops)
        out.append(f"- **{t.title}** ({t.sector or 'patrol'}). {t.description} *Stops:* {stops}.")
    return "\n".join(out)


def order_index(ctx: HelpContext) -> str:
    """Every word the console takes as an order, with its other spellings and the page that explains it."""
    from ..console.vocab import VERBS
    from .docs import HelpLibrary, BUNDLED_DIR

    lib = HelpLibrary(dirs=(BUNDLED_DIR,))
    lib.refresh()
    rows = ["| Order | Also | Explained in |", "|---|---|---|"]
    for verb, words in sorted(VERBS.items()):
        also = ", ".join(f"`{w}`" for w in words if w != verb) or "-"
        topic = next((t for t in lib.ordered() if verb == t.id or verb in t.aliases), None) or lib.resolve(verb)
        page = f"[[{topic.id}|{topic.title}]]" if topic is not None else "-"
        rows.append(f"| `{verb}` | {also} | {page} |")
    return "\n".join(rows)


LORE_BLOCKS = {
    "crew_roster": crew_roster,
    "faction_profiles": faction_profiles,
    "collaborations": collaborations,
    "preset_list": preset_list,
    "tour_list": tour_list,
    "order_index": order_index,
}

__all__ = ["LORE_BLOCKS", "collaborations", "crew_roster", "faction_profiles", "order_index", "preset_list",
           "tour_list"]
