"""Talking to the bridge officers.

`Bridge` sits between the console and the officers. The captain can:

* ask an officer anything: `ask worf status`, `spock, what do you recommend?`;
* give an officer an order in plain words or as a console command:
  `worf, fire all torpedoes`, `scotty, take engineering`;
* hear the officers react to the battle (chatter), each in their own voice.

With no LLM configured the officers answer from the battle state: reports
for their station, the coach's advice for the stations they cover, and the
lines in `officers.toml`. With a provider configured, questions go to the
model with the officer's persona and a summary of what the ship knows; the
reply's commands go through the console parser like anything the captain
types, and only those for the officer's stations are carried out.

Officer chatter and conversation are presentation only: they read the
player's Observation and issue ordinary commands, so the simulation stays
deterministic.
"""

from __future__ import annotations

import json
import math
import random
import re
from dataclasses import dataclass, field
from typing import Callable, Iterable

from ..core.angles import bearing
from ..help.coach import HelpContext, tips
from ..llm.providers.base import Message
from ..llm.service import LLMService
from ..sim.events import (
    ContactChanged, Event, HullHit, PhaserFired, ScanCompleted, ShipStatusChanged, SubsystemRepaired, TorpedoLaunched,
)
from ..sim.observation import Observation
from ..sim.ship import Ship
from .characters import (
)
from .officers import STATION_NAMES, Crew


@dataclass
class Utterance:
    officer: str        # officer id
    speaker: str        # what the log shows
    text: str
    tone: str = "crew"  # crew | caution | dim
    commands: list[str] = field(default_factory=list)   # suggestions the captain can click or type


# runs a console line on behalf of an officer; returns an error, or None when it was carried out
RunCommand = Callable[[str, OfficerProfile], "str | None"]

_PRAISE = re.compile(r"\b(thanks?|thank you|well done|good (job|work|shooting)|nice|great|excellent|bravo)\b")
_RUDE = re.compile(r"\b(stupid|idiot|useless|incompetent|shut up|moron|fool)\b")
_GREET = re.compile(r"^(hello|hi|hey|greetings|report in)\b")
_TAKE = re.compile(r"\b(take over|take (the |your )?(conn|helm|station|tactical|weapons|engineering|science|sensors)"
                   r"|you have the (conn|helm|station)|your station|take charge|you'?re in charge|handle it)\b")
_RELEASE = re.compile(r"\b(stand down|i have (the|it)|i'?ll (take|handle) (it|the)|i relieve you|belay)\b")
_STATUS = re.compile(r"\b(status|report|sitrep|situation|how are|how's|condition)\b")
_ADVICE = re.compile(r"\b(advice|advise|recommend|suggest|what (should|do you|now|next)|ideas?|options?|thoughts?|opinion)\b")


class Bridge:
    def __init__(self, crew: Crew, hidden: dict[str, object], llm: LLMService | None = None,
                 seed: int = 0, chatter: bool = True) -> None:
        self.crew = crew
        self.hidden = hidden
        self.llm = llm
        self.rng = random.Random(seed ^ 0x5EB)
        self.chatter = chatter
        self.relationships = Relationships.from_settings(hidden)
        self.history: dict[str, list[Message]] = {}
        self.suggested: dict[str, tuple[int, list[str]]] = {}   # officer -> (tick, commands)
        self.asking: dict[str, bool] = {}   # officer -> the pending LLM request is a question, not an order
        self._last_line: dict[str, int] = {}
        self._last_any = -999
        self._hull_band = 4
        self._threats = 0
        self._llm_note_given = False

    # ------------------------------------------------------------ who

    def officers(self) -> list[OfficerProfile]:
        return list(dict.fromkeys(self.crew.officers.values()))

    def find(self, name: str) -> OfficerProfile | None:
        return self.crew.find(name)

    def addressed(self, text: str) -> tuple[OfficerProfile, str] | None:
        """`worf, fire` / `spock: report` / `seven what do you see` → (officer, the rest)."""
        m = re.match(r"^\s*([a-z][a-z ]{1,24}?)\s*[,:]\s*(.*)$", text, re.I)
        if m:
            o = self.find(m.group(1))
            if o is not None:
                return o, m.group(2).strip()
        return None

    # ------------------------------------------------------------ talking

    def ask(self, officer: OfficerProfile, text: str, ctx: HelpContext, run: RunCommand) -> list[Utterance]:
        """The captain speaks to an officer. Returns what is said now (an LLM answer arrives via `poll`)."""
        rel = self.relationships.get(officer.id)
        rel.exchanges += 1
        low = text.lower().strip()
        if _PRAISE.search(low):
            rel.nudge(0.03)
        if _RUDE.search(low):
            rel.nudge(-0.08)
        if self.llm is not None:
            if self.llm.busy(officer.id):
                return [self._say(officer, "One moment, Captain.", "dim")]
            system = self.system_prompt(officer, ctx)
            hist = self.history.setdefault(officer.id, [])
            hist.append({"role": "user", "content": text or "Report."})
            del hist[:-16]
            self.llm.submit(officer.id, system, hist)
            self.asking[officer.id] = is_question(low)
            return [self._say(officer, "…", "dim")]
        return self.offline(officer, low, ctx, run)

    def poll(self, ctx: HelpContext, run: RunCommand) -> list[Utterance]:
        """LLM answers that have arrived since the last frame."""
        if self.llm is None:
            return []
        out: list[Utterance] = []
        for r in self.llm.poll():
            officer = next((o for o in self.officers() if o.id == r.tag), None)
            if officer is None:
                continue
            hist = self.history.setdefault(officer.id, [])
            if r.text is None:
                if hist and hist[-1]["role"] == "user":
                    question = hist.pop()["content"]
                else:
                    question = ""
                out.append(self._say(officer, f"(LLM unavailable: {r.error}. Answering offline.)", "dim"))
                out.extend(self.offline(officer, question.lower(), ctx, run))
                continue
            say, commands = parse_reply(r.text)
            hist.append({"role": "assistant", "content": json.dumps({"say": say, "commands": commands})})
            u = self._say(officer, say or "…")
            out.append(u)
            if self.asking.pop(officer.id, False):
                # a question gets advice: the commands are suggestions the captain can type or click
                if commands:
                    u.commands = commands
                    self.suggested[officer.id] = (ctx.obs.tick if ctx.obs else 0, list(commands))
                continue
            for line in commands:
                err = run(line, officer)
                if err:
                    out.append(self._say(officer, f"Unable to comply with '{line}': {err}", "caution"))
        return out

    def offline(self, o: OfficerProfile, low: str, ctx: HelpContext, run: RunCommand) -> list[Utterance]:
        rel = self.relationships.get(o.id)
        out: list[Utterance] = []
        if not low or _GREET.match(low):
            out.append(self._line(o, "greeting") or self._say(o, "Captain."))
        elif _RUDE.search(low):
            out.append(self._line(o, "rude") or self._say(o, "Understood, Captain."))
        elif _PRAISE.search(low) and not _ADVICE.search(low):
            out.append(self._line(o, "thanks") or self._say(o, "Thank you, Captain."))
            if fl:
                out.append(self._say(o, fl))
        elif _RELEASE.search(low):
            err = run(f"assume {o.station}", o)
            out.append(self._say(o, err, "caution") if err else (self._line(o, "released") or self._say(o, "Aye.")))
        elif _TAKE.search(low):
            err = run(f"delegate {o.station}", o)
            out.append(self._say(o, err, "caution") if err else (self._line(o, "delegated") or self._say(o, "Aye.")))
        elif _ADVICE.search(low) or low.endswith("?") and not _STATUS.search(low):
            out.extend(self.advice(o, ctx))
        elif _STATUS.search(low):
            out.append(self._say(o, self.report(o, ctx)))
        else:
            command = re.sub(r"^(please|now|immediately)\s+|\s+(please|now|immediately)$", "", low).strip()
            err = run(command, o)
            if err is None:
                out.append(self._line(o, "ack") or self._say(o, "Aye, Captain."))
            elif err.startswith("Unknown command") or err.startswith("'"):
                out.append(self._line(o, "unknown") or self._say(o, "I don't follow, Captain."))
            else:
                out.append(self._say(o, err, "caution"))
        if intensity and self.rng.random() < intensity / 25.0 and out and out[-1].tone == "crew":
            if fl:
                out.append(self._say(o, fl))
        return out

    def advice(self, o: OfficerProfile, ctx: HelpContext) -> list[Utterance]:
        mine = [t for t in tips(ctx) if t.station in o.advises]
        if not mine:
            return [self._line(o, "nothing") or self._say(o, "Nothing to add, Captain.")]
        best = mine[0]
        text = _plain(best.text)
        self.suggested[o.id] = (ctx.obs.tick if ctx.obs else 0, list(best.commands))
        u = self._say(o, f"{best.title}. {text}")
        u.commands = list(best.commands)
        return [u]

    def report(self, o: OfficerProfile, ctx: HelpContext) -> str:
        s, obs = ctx.ship, ctx.obs
        if s is None or obs is None:
            return "No ship, Captain."
        return STATION_REPORTS[o.station](s, obs)

    def captain_ran(self, line: str, tick: int, cycles: float) -> None:
        """Credit an officer when the captain takes their suggestion within half a minute."""
        low = " ".join(line.lower().split())
        for oid, (t, cmds) in list(self.suggested.items()):
            if (tick - t) <= 30 * cycles and any(low == " ".join(c.lower().split()) for c in cmds):
                rel = self.relationships.get(oid)
                rel.nudge(0.04)
                rel.advice_taken += 1
                del self.suggested[oid]

    # ------------------------------------------------------------ the LLM brief

    def system_prompt(self, o: OfficerProfile, ctx: HelpContext) -> str:
        rel = self.relationships.get(o.id)
        stations = ", ".join(STATION_NAMES[s] for s in o.advises)
        return "\n".join([
            o.persona,
            "",
            "Setting: the captain is speaking to you on the bridge during a real-time battle in a 2D tactical "
            "starship game. Courses are compass bearings (0 = up the map, 90 = right). Distances are in units; "
            "warp 1 = 100 units per second.",
            f"You run the {STATION_NAMES[o.station]} station and advise on: {stations}. "
            f"Your relationship with the captain: {rel.mood}.",
            "Answer with ONE JSON object and nothing else:",
            '{"say": "<what you say aloud, at most three short sentences>", "commands": ["<console command>", ...]}',
            "Put commands in the list only when the captain orders you to act; when the captain asks a question, "
            "the list holds what you recommend, and the captain decides. Use only commands for your stations, "
            "written exactly in this console syntax:",
            COMMAND_SYNTAX,
            "",
            "What the ship knows right now:",
            situation(ctx),
        ])

    # ------------------------------------------------------------ chatter

    def react(self, events: Iterable[Event], ctx: HelpContext) -> list[Utterance]:
        """Officers comment on what just happened (rate limited)."""
        s, obs = ctx.ship, ctx.obs
        if not self.chatter or s is None or obs is None:
            return []
        out: list[Utterance] = []
        delegated = s.delegated
        for ev in events:
            if isinstance(ev, TorpedoLaunched) and ev.ship_id == s.id and "tactical" in delegated:
                self._maybe(out, obs, "tactical", "torpedoes", 0.6)
            elif isinstance(ev, PhaserFired) and ev.ship_id == s.id and "tactical" in delegated:
                self._maybe(out, obs, "tactical", "phasers", 0.15)
            elif isinstance(ev, ShipStatusChanged) and ev.status == "destroyed":
                c = obs.contact(ev.ship_id)
                if c is not None and not (c.side is not None and c.side == s.side):
                    self._maybe(out, obs, "tactical", "enemy_destroyed", 0.9, target=_name(obs, ev.ship_id))
            elif isinstance(ev, HullHit) and ev.ship_id == s.id and s.structure > 0:
                band = int(4 * max(0.0, s.structure) / max(1.0, s.structure_max))
                if band < self._hull_band:
                    self._hull_band = band
                    self._maybe(out, obs, "engineering", "hull", 1.0,
                                n=round(100 * max(0.0, s.structure) / max(1.0, s.structure_max)))
            elif isinstance(ev, ContactChanged) and ev.side == s.side and ev.acquired:
                c = obs.contact(ev.ship_id)
                if c is not None and c.visible:
                    self._maybe(out, obs, "science", "contact", 0.5, target=_name(obs, ev.ship_id))
            elif isinstance(ev, ContactChanged) and ev.side == s.side and not ev.acquired:
                # the science officer gives the last fix, so the captain knows where to look
                c = obs.contact(ev.ship_id)
                if c is not None and not c.visible and not c.cloaked_hint:
                    self._maybe(out, obs, "science", "lost", 1.0, gap=4.0, target=_name(obs, ev.ship_id),
                                bearing=f"{bearing(c.x - s.x, c.y - s.y):.0f}",
                                range=f"{math.hypot(c.x - s.x, c.y - s.y):,.0f}",
                                heading=f"{c.course:.0f}", warp=f"{c.warp:.1f}")
            elif isinstance(ev, ScanCompleted) and ev.ship_id == s.id:
                self._maybe(out, obs, "science", "scan", 0.7, target=_name(obs, ev.target_id))
            elif isinstance(ev, SubsystemRepaired) and ev.ship_id == s.id:
                self._maybe(out, obs, "engineering", "repaired", 0.3, n=ev.label)
        threats = len([o for o in obs.threats() if math.hypot(o.x - s.x, o.y - s.y) < 8000])
        if threats > self._threats:
            self._maybe(out, obs, "helm", "incoming", 0.5)
        self._threats = threats
        temp = max((d.temp for d in s.drives if not d.destroyed), default=0.0)
        if temp > obs.rules.temp_limit * 0.85:
            self._maybe(out, obs, "engineering", "hot", 1.0, gap=20.0)
        return out

    def outcome(self, won: bool | None) -> list[Utterance]:
        o = self.crew.officer("helm") or next(iter(self.crew.officers.values()), None)
        if o is None or won is None:
            return []
        u = self._line(o, "victory" if won else "defeat")
        return [u] if u else []

    def _maybe(self, out: list[Utterance], obs: Observation, station: str, event: str, p: float,
               gap: float = 8.0, **fill: object) -> None:
        o = self.crew.officer(station)
        if o is None or event not in o.lines:
            return
        tpc = obs.rules.ticks_per_cycle
        if obs.tick - self._last_line.get(o.id, -10 ** 9) < gap * tpc or obs.tick - self._last_any < 3 * tpc:
            return
        if self.rng.random() > p:
            return
        u = self._line(o, event, **fill)
        if u is not None:
            self._last_line[o.id] = self._last_any = obs.tick
            out.append(u)

    # ------------------------------------------------------------ bits

    def _say(self, o: OfficerProfile, text: str, tone: str = "crew") -> Utterance:
        return Utterance(o.id, o.name, text, tone)

    def _line(self, o: OfficerProfile, event: str, **fill: object) -> Utterance | None:
        text = o.line(event, self.rng, captain="Captain", **fill)
        return self._say(o, text) if text else None

    def save(self, hidden: dict[str, object]) -> None:
        self.relationships.to_settings(hidden)

    def close(self) -> None:
        if self.llm is not None:
            self.llm.close()


COMMAND_SYNTAX = """\
  (In this list <...> is a value to fill in, [...] is optional and a|b means one of them; never type the
  brackets themselves. Example commands: "target derango weapons", "fire all phasers spread 20", "helm 90 warp 6".)
  helm <course> warp <w> | warp <w> | stop | pursue <ship> [warp <w>] | elude <ship> [warp <w>]
  target <ship> [propulsion|weapons|shields|power|sensors] | fire all phasers [spread <10-45>]
  fire all torpedoes | fire probes at <ship> | autoload tor <torpedo id> | load all tubes <proximity>
  pd off|conservative|balanced|aggressive | mode phasers|tubes manual|assisted|automatic
  raise all | lower <shield numbers> | reinforce <1-6> | repair <system>|all | cloak on|off
  scan <ship>
  delegate <helm|tactical|engineering|science> | assume <station>   (hand a station to its officer, or take it back)"""


def clean_command(line: str) -> str:
    """Small models copy the syntax notation literally: 'target derango[weapons]', 'fire all phasers [spread 45]'."""
    line = re.sub(r"[\[\]<>`]", " ", line)
    return " ".join(line.split()).strip(" .;")


def is_question(low: str) -> bool:
    """Asking for advice or information, rather than giving an order."""
    low = low.strip()
    return low.endswith("?") or bool(_ADVICE.search(low)) or bool(re.match(
        r"(what|why|how|which|where|when|who|should|can|could|would|is|are|do|does|did)\b", low))


def parse_reply(text: str) -> tuple[str, list[str]]:
    """The model's JSON reply → (spoken text, commands). Plain text is accepted as speech."""
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            data = json.loads(m.group(0))
        except ValueError:
            data = None
        if isinstance(data, dict):
            say = str(data.get("say", "")).strip()
            cmds = data.get("commands") or []
            if not isinstance(cmds, list):
                cmds = [cmds]
            return say, [c for c in (clean_command(str(x)) for x in cmds) if c][:4]
    return text.strip().strip('"'), []


def situation(ctx: HelpContext) -> str:
    """A compact, factual summary of what the player's side knows (no hidden information)."""
    s, obs = ctx.ship, ctx.obs
    if s is None or obs is None:
        return "No ship."
    lines = [
        f"Our ship: {s.name}, {s.cls.name}. Hull {_pct(s.structure, s.structure_max)}, crew {s.crew}/{s.cls.crew}. "
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
        lines.append(f"Contact {_name(obs, c.id)} ({what}): range {d:,.0f}, bearing {brg:.0f}, "
                     f"course {c.course:.0f}, warp {math.hypot(c.vx, c.vy) / obs.rules.units_per_warp:.1f}{scan}.")
    allies = [a for a in obs.own_ships() if a.id != s.id and a.alive]
    if allies:
        lines.append("Allies: " + ", ".join(f"{a.name} ({a.cls.abbrev}, hull {_pct(a.structure, a.structure_max)})"
                                            for a in allies[:6]) + ".")
    threats = [o for o in obs.threats() if math.hypot(o.x - s.x, o.y - s.y) < 10000]
    if threats:
        lines.append(f"Incoming enemy ordnance: {len(threats)}.")
    advice = tips(ctx)[:3]
    if advice:
        lines.append("Tactical computer notes: " + " ".join(f"{t.title}: {_plain(t.text)}" for t in advice))
    return "\n".join(lines)


# ------------------------------------------------------------------ station reports (offline answers)

def _helm_report(s: Ship, obs: Observation) -> str:
    c = obs.contact(s.target) if s.target is not None else None
    out = f"Course {s.desired_course:.0f}, warp {s.warp:.1f} of {s.max_attainable_warp:.1f} attainable."
    if c is not None:
        d = c.distance_to(s.x, s.y)
        brg = math.degrees(math.atan2(c.x - s.x, c.y - s.y)) % 360
        out += f" {_name(obs, c.id)} bears {brg:.0f} at {d:,.0f}."
    return out


def _tactical_report(s: Ship, obs: Observation) -> str:
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
    tgt = f"Target: {_name(obs, s.target)}." if s.target is not None else "No target selected."
    return f"{tgt} " + ", ".join(parts) + "."


def _engineering_report(s: Ship, obs: Observation) -> str:
    sh = [x for x in s.shields if not x.destroyed]
    weakest = min(sh, key=lambda x: x.effective, default=None)
    temp = max((d.temp for d in s.drives if not d.destroyed), default=0.0)
    cap = s.battery_capacity()
    batt = f"batteries {_pct(s.battery_charge(), cap)}" if cap > 0 else "no batteries"
    damaged = sum(1 for x in s.subsystems() if x.damage > 0)
    out = f"Hull {_pct(s.structure, s.structure_max)}, {batt}, drive temperature {temp:.0f} of {obs.rules.temp_limit:.0f}."
    if weakest is not None:
        out += f" Weakest shield is {weakest.index + 1} at {weakest.effective:.0f}%."
    if damaged:
        out += f" {damaged} systems damaged; repairs on {s.repair_priority.value if s.repair_priority else 'everything'}."
    return out


def _science_report(s: Ship, obs: Observation) -> str:
    cs = list(obs.contacts().values())
    seen = [c for c in cs if c.visible]
    unscanned = [c for c in seen if c.scan is None]
    out = f"{len(seen)} contacts on sensors, {len(cs) - len(seen)} lost."
    if unscanned:
        out += " Not yet scanned: " + ", ".join(_name(obs, c.id) for c in unscanned[:4]) + "."
    return out


STATION_REPORTS: dict[str, Callable[[Ship, Observation], str]] = {
    "helm": _helm_report, "tactical": _tactical_report, "engineering": _engineering_report, "science": _science_report,
}


def _name(obs: Observation, sid: int | None) -> str:
    if sid is None:
        return "nothing"
    own = obs.own(sid)
    if own is not None:
        return own.name
    c = obs.contact(sid)
    if c is None:
        return f"#{sid}"
    return c.label.split(" (")[0] if c.identified else f"#{sid}"


def _pct(v: float, of: float) -> str:
    return f"{100 * max(0.0, v) / max(1e-9, of):.0f}%"


def _plain(md: str) -> str:
    return re.sub(r"\*\*|`", "", md).strip()


__all__ = ["Bridge", "COMMAND_SYNTAX", "STATION_REPORTS", "Utterance", "parse_reply", "situation"]
