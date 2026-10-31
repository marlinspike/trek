"""The captain's log of a tour [E]: written with your officers and your squadron's captains, edited by you.

After each fight every bridge officer files a short entry for their station, each captain in
your squadron reports on their own ship, and a draft of the captain's entry is put together
from all of it. You can rewrite any of it in the Ready Room; your words are kept as written.

Everything here is written from the battle's record, in each officer's own phrasing, so the
log needs no language model. With one configured, `voice_request` asks it to put an entry in
the officer's voice (the Ready Room sends these in the background and swaps the text in as
the answers come, unless you've already edited that entry).

The log is also kept as Markdown, `config/tours/<tour id>-log.md`. Edit the captain's entries
there between sessions and the game reads your changes back (`read_markdown_edits`).
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ..sim.events import ObjectiveEnded
from ..sim.ship import ShipStatus
from .state import LogEntry, TourState

if TYPE_CHECKING:
    from ..battle import Battle
    from .run import Fight, TourRun

OFFICER_ORDER = ("spock", "worf", "geordi", "seven")
OFFICER_TITLES = {"spock": "Commander Spock, helm", "worf": "Lieutenant Worf, tactical",
                  "geordi": "Lieutenant Commander La Forge, engineering", "seven": "Seven of Nine, science"}


def _pct(v: float) -> str:
    return f"{v * 100:.0f}%"


def _ratio(hits: int, shots: int) -> str:
    return f"{hits} of {shots}" if shots else "none"


def facts_of(run: TourRun, battle: Battle, fight: Fight, outcome: str, captured: list[str], lost: list[str],
             standout: str) -> dict[str, Any]:
    """What happened, plainly: the material every entry is written from (and what a model is given)."""
    w = battle.world
    side = w.player_side
    ours = [w.ships[i] for i in fight.ship_ids if i in w.ships]
    flag = ours[0] if ours else None
    ours_ids = set(fight.ship_ids) | set(fight.friend_ids)
    called = {i for a in w.arrivals if a.tag == "starfleet" for i in a.ship_ids}
    enemies = [s for s in w.ships.values() if s.id not in ours_ids and s.id not in called
               and (s.side != side or s.name in captured)]
    destroyed = [s.name for s in enemies if s.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT)]
    escaped = [s.name for s in enemies if s.status == ShipStatus.ESCAPED]
    surrendered = [s.name for s in enemies if s.status == ShipStatus.SURRENDERED]
    st = flag.stats if flag is not None else None
    taken = sum(s.prisoners for s in w.ships.values() if s.name in captured and s.side == side)
    broken = [w.ships[i].name for i in w.faith_broken.get(side, set()) if i in w.ships]
    kinds: dict[str, int] = {}
    for s in enemies:
        k = f"{w.content.factions[s.faction].name} {s.cls.name.lower()}"
        kinds[k] = kinds.get(k, 0) + 1
    disabled = sum(s.stats.subsystems_disabled for s in ours)
    objectives = [ev for ev in battle.deeds if isinstance(ev, ObjectiveEnded)]
    f: dict[str, Any] = {
        "stop": fight.stop.title, "system": fight.stop.system, "outcome": outcome,
        "cycles": round(w.time), "stardate": run.state.stardate(),
        "enemy": _force(kinds) or "no enemy",
        "destroyed": destroyed, "escaped": escaped, "surrendered": surrendered, "captured": captured, "lost": lost,
        "prisoners": taken, "fired_on_surrendered": broken,
        "flagship": flag.name if flag else "", "standout": standout,
        "hull": round(max(0.0, flag.structure / max(1.0, flag.structure_max)), 3) if flag else 0.0,
        "crew": flag.crew if flag else 0, "crew_full": flag.cls.crew if flag else 0,
        "crew_lost": sum(s.stats.crew_lost for s in ours),
        "phasers": _ratio(st.phaser_hits, st.phaser_shots) if st else "none",
        "torpedoes": _ratio(st.torpedo_hits, st.torpedoes_fired) if st else "none",
        "torps_left": (flag.torps_remaining + sum(1 for t in flag.tubes if t.loaded is not None)) if flag else 0,
        "intercepts": st.ordnance_intercepted if st else 0,
        "dealt": round(st.damage_dealt) if st else 0, "taken": round(st.damage_taken) if st else 0,
        "systems_down": [s.label for s in flag.subsystems() if s.damage >= 50] if flag else [],
        "subsystems_hit": disabled,
        "scans": sum(1 for lc in w.command_log if lc.accepted and lc.command.name == "scan"
                     and lc.command.ship_id in fight.ship_ids),
        "objectives": len([o for o in objectives if o.outcome == "done"]),
        "called": len(fight.called),
        "squadron": [{"name": w.ships[i].name, "class": w.ships[i].cls.name, "captain": w.ships[i].captain,
                      "status": w.ships[i].status.value if w.ships[i].side == side else "taken by the enemy",
                      "hull": round(max(0.0, w.ships[i].structure / max(1.0, w.ships[i].structure_max)), 3),
                      "kills": w.ships[i].stats.kills, "dealt": round(w.ships[i].stats.damage_dealt)}
                     for i in fight.ship_ids[1:] if i in w.ships],
    }
    return f


NUMBERS = ("no", "a", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten")


def _force(kinds: dict[str, int]) -> str:
    """{"Klingon frigate": 2, "Klingon battle cruiser": 1} -> "two Klingon frigates and a Klingon battle cruiser"."""
    parts = []
    for k, n in sorted(kinds.items(), key=lambda kv: -kv[1]):
        if n == 1:
            parts.append(("an " if k[0].lower() in "aeiou" else "a ") + k)
        else:
            parts.append(f"{NUMBERS[n] if n < len(NUMBERS) else n} {k}s")
    return _list(parts)


def _n(n: int, word: str) -> str:
    return f"{n} {word}{'' if n == 1 else 's'}"


def _list(names: list[str]) -> str:
    if not names:
        return ""
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " and " + names[-1]


def station_entries(f: dict[str, Any]) -> dict[str, str]:
    """Each officer's entry, in their own manner, from the facts."""
    won = f["outcome"] == "victory"
    out: dict[str, str] = {}
    hull = f["hull"]
    # Spock: precise, the shape of the engagement
    s = (f"Engagement at {f['system']} lasted {f['cycles']} cycles against {f['enemy']}. "
         f"{'The enemy force was defeated' if won else 'We did not prevail'}")
    if f["destroyed"]:
        s += f"; {_list(f['destroyed'])} destroyed"
    if f["escaped"]:
        s += f"; {_list(f['escaped'])} withdrew beyond sensor range"
    if f["outcome"] == "lost":
        s += f". The {f['flagship']} was lost with the engagement."
    else:
        s += f". Hull integrity at the close: {_pct(hull)}."
        if f["torps_left"] == 0:
            s += " Our magazine is empty; we must close to phaser range until we can rearm."
        elif f["torps_left"] <= 6:
            s += f" Only {f['torps_left']} torpedoes remain; I recommend we husband them."
    out["spock"] = s
    # Worf: the weapons record
    w = (f"Our phasers hit with {f['phasers']} shots. " if f["phasers"] != "none" else "Our phasers were not fired. ")
    w += (f"{f['torpedoes'][0].upper()}{f['torpedoes'][1:]} torpedoes found their mark." if f["torpedoes"] != "none"
          else "We fired no torpedoes.")
    if f["intercepts"]:
        w += f" Point defense destroyed {_n(f['intercepts'], 'incoming round')}."
    if f["captured"]:
        w += f" Our boarding parties took {_list(f['captured'])}. A worthy prize."
        if f.get("prisoners"):
            w += f" {f['prisoners']} of her crew surrendered without a fight and are held under guard."
    elif f["destroyed"]:
        w += f" {_list(f['destroyed'])} will not trouble the border again."
    if not won:
        w += " We will have our chance to answer this."
    out["worf"] = w
    # Geordi: damage and repairs
    if f["outcome"] == "lost":
        out["geordi"] = f"We lost her. {f['crew_lost']} crew went with her. I'm sorry, Captain."
        out["seven"] = "Sensor logs end with the loss of the ship. They have been transmitted to Starfleet."
        return out
    g = f"Hull's at {_pct(hull)}."
    if f["systems_down"]:
        g += f" {_list(f['systems_down'][:4])} took a beating; my people are on it."
    else:
        g += " Nothing we can't patch on the way."
    if f["crew_lost"]:
        g += f" We lost {f['crew_lost']} crew across the squadron. The repair crews are feeling it."
    if hull < 0.75:
        g += " We can patch her to about 75% out here. Anything past that needs a starbase."
    out["geordi"] = g
    # Seven: sensors and findings
    v = "Sensor logs for the engagement are complete."
    if f["scans"]:
        v += (f" {_n(f['scans'], 'detailed scan')} {'was' if f['scans'] == 1 else 'were'} taken; the data is filed "
              f"for the next encounter.")
    if f["objectives"]:
        v += f" {_n(f['objectives'], 'assigned objective')} {'was' if f['objectives'] == 1 else 'were'} achieved."
    if f["escaped"]:
        v += f" {_list(f['escaped'])} will report our tactics to their command. Adaptation is to be expected."
    else:
        v += " No enemy vessel escaped to report on us."
    out["seven"] = v
    return out


def captain_reports(f: dict[str, Any]) -> dict[str, str]:
    """Each squadron captain's report on their own ship."""
    out = {}
    for sh in f["squadron"]:
        cap = f"Captain {sh['captain']}" if sh["captain"] else "Her captain"
        if sh["status"] == "active":
            text = (f"{cap} reports {sh['name']} at {_pct(sh['hull'])} hull"
                    + (f", with {sh['kills']} kill{'s' if sh['kills'] != 1 else ''} to her name" if sh["kills"] else "")
                    + ". Ready for the next assignment." if sh["hull"] >= 0.5 else
                    f"{cap} reports {sh['name']} badly hurt, hull {_pct(sh['hull'])}. Requests time for repairs.")
        elif sh["status"] == "escaped":
            text = f"{sh['name']} broke off and withdrew from the battle area. {cap} rejoins at the next stop."
        else:
            text = f"{sh['name']} was lost ({sh['status']}). Her last report is filed with this log."
        out[sh["name"]] = text
    return out


def captain_draft(f: dict[str, Any]) -> str:
    """A draft of the captain's own entry, for you to keep, edit or rewrite."""
    won = f["outcome"] == "victory"
    t = (f"Captain's log, stardate {f['stardate']}. At {f['system']} we met {f['enemy']}. ")
    if won:
        t += "The engagement went our way"
        if f["captured"]:
            t += f", and {_list(f['captured'])} now sails under our colours"
        t += ". "
    elif f["outcome"] == "base lost":
        t += "We could not hold the starbase. "
    elif f["outcome"] == "lost":
        t += f"The {f['flagship']} has been lost. "
        others = [n for n in f["lost"] if n != f["flagship"]]
        if others:
            t += f"So were {_list(others)}. "
        if f["crew_lost"]:
            t += f"{f['crew_lost']} of our people did not come home. "
        return t.strip()
    else:
        t += "We broke off the engagement. "
    if f["lost"]:
        t += f"We lost {_list(f['lost'])}; their crews will be remembered. "
        if f["crew_lost"]:
            t += f"In all, {f['crew_lost']} of our people did not come home. "
    elif f["crew_lost"]:
        t += f"We lost {_n(f['crew_lost'], 'crewman' if f['crew_lost'] == 1 else 'crew member')}. "
    if f.get("prisoners"):
        t += (f"{f['prisoners']} of the enemy's crew surrendered and are held as prisoners of war; they will be "
              "treated as the conventions of war require. ")
    if f.get("fired_on_surrendered"):
        t += (f"We fired on {_list(f['fired_on_surrendered'])} after they had yielded. Their captains will remember "
              "it, and so will I. ")
    if f["standout"]:
        t += f"{f['standout']} "
    t += f"The {f['flagship']} stands at {_pct(f['hull'])} hull with {f['torps_left']} torpedoes in the magazine."
    return t.strip()


def draft_entry(run: TourRun, battle: Battle, fight: Fight, outcome: str, captured: list[str], lost: list[str],
                standout: str) -> LogEntry:
    f = facts_of(run, battle, fight, outcome, captured, lost, standout)
    return LogEntry(fight.stop.id, fight.stop.title, f["stardate"], outcome, station_entries(f), captain_reports(f),
                    captain_draft(f), facts=f)


# ------------------------------------------------------------------ with a language model

def voice_request(entry: LogEntry, who: str, persona: str, style: str) -> tuple[str, str]:
    """(system prompt, user message) asking a model to write one entry in its writer's voice."""
    facts = "\n".join(f"- {k}: {v}" for k, v in entry.facts.items() if v not in ("", [], 0, None))
    if who == "captain":
        system = ("You are the captain of a Federation starship writing your own captain's log after a battle, in a "
                  "2D tactical starship game. Write the entry in the first person, in a measured, reflective "
                  "Starfleet captain's voice: at most five sentences. Begin with 'Captain's log, stardate "
                  f"{entry.stardate}.' Use only the facts given; never invent ships, names or numbers. Reply with "
                  "the entry only.")
        draft = entry.captain
    elif who in entry.stations:
        system = (persona + "\n\nWrite your station's entry for the captain's log after the battle: at most three "
                  "sentences, first person, in your own voice. Use only the facts given; never invent ships, names "
                  "or numbers. Reply with the entry only, no quotes or headings. " + style).strip()
        draft = entry.stations[who]
    else:
        system = ("You are the captain of a Federation starship in the player's squadron, filing a short report on "
                  "your own ship for the flagship's log after a battle. At most two sentences, first person, crisp "
                  "Starfleet voice. Use only the facts given. Reply with the report only.")
        draft = entry.captains.get(who, "")
    return system, f"Facts:\n{facts}\n\nThe entry as drafted (keep its facts, say it your way):\n{draft}"


# ------------------------------------------------------------------ Markdown

_ENTRY = re.compile(r"<!-- captain:(?P<id>[\w.-]+) -->\n(?P<text>.*?)\n<!-- /captain -->", re.S)


def markdown(run: TourRun) -> str:
    st, tour = run.state, run.tour
    out = [f"# {tour.title}: captain's log", "",
           f"_{tour.description}_" if tour.description else "", "",
           "Edit the text between the `captain` markers to change your entries; the game reads them back "
           "the next time you open this tour. Everything else here is rewritten by the game.", ""]
    for e in st.log:
        out += [f"## {e.title} (stardate {e.stardate}): {e.outcome}", "", "### Captain", "",
                f"<!-- captain:{e.stop_id} -->", e.captain, "<!-- /captain -->", ""]
        for oid in OFFICER_ORDER:
            if oid in e.stations:
                out += [f"**{OFFICER_TITLES.get(oid, oid)}.** {e.stations[oid]}", ""]
        for name, text in e.captains.items():
            out += [f"**USS {name}.** {text}", ""]
    if st.over:
        grade, lines = run.rating()
        out += ["## The end of the tour", "", f"**{grade}.**", ""] + [f"- {ln}" for ln in lines] + [""]
    return "\n".join(out).replace("\n\n\n", "\n\n")


def write_markdown(run: TourRun, folder: Path) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{run.tour.id}-log.md"
    path.write_text(markdown(run))
    return path


def read_markdown_edits(state: TourState, folder: Path) -> int:
    """Take back the captain's entries you edited in the Markdown log. Returns how many changed."""
    path = folder / f"{state.tour_id}-log.md"
    try:
        text = path.read_text()
    except OSError:
        return 0
    n = 0
    by_id = {e.stop_id: e for e in state.log}
    for m in _ENTRY.finditer(text):
        e = by_id.get(m.group("id"))
        new = m.group("text").strip()
        if e is not None and new and new != e.captain.strip():
            e.captain = new
            e.edited = True
            n += 1
    return n


__all__ = ["captain_draft", "captain_reports", "draft_entry", "facts_of", "markdown", "read_markdown_edits",
           "station_entries", "voice_request", "write_markdown"]
