"""Talking to the bridge officers.

`Bridge` sits between the console and the officers. The captain can:

* ask an officer anything: `ask worf status`, `spock, what do you recommend?`;
* give an officer an order in plain words or as a console command:
  `worf, fire all torpedoes`, `geordi, take engineering`;
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
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable

from ..core.angles import bearing
from ..help.coach import HelpContext, tips
from ..llm.providers.base import Message
from ..llm.service import LLMService
from ..sim.events import (
    ContactChanged, Event, HullHit, MoraleShift, ObjectiveEnded, PhaserFired, ProjectCompleted, ScanCompleted, ShipStatusChanged, SubsystemRepaired, TorpedoLaunched,
)
from ..sim.observation import Observation
from ..sim.ship import HULL, KIND_LABEL, Kind, Ship, repair_words
from ..sim.commands import AddressCrew
from ..console.reports import morale_words
from .characters import OfficerProfile, Relationships
from ..sim.objectives import DISABLE_GROUPS
from . import collaborations
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

# steps worth saying aloud as they start, how long each must last first (seconds), and the gap between callouts
CALLOUT_KINDS = ("evade", "close", "open", "fight", "bait", "salvo", "between", "phasers", "hunt")
CALLOUT_SETTLE = {"evade": 0.0, "bait": 0.0, "salvo": 0.0, "between": 0.0, "close": 2.0, "open": 2.0, "fight": 2.0}
CALLOUT_GAP = 4.0
CALLOUT_REPEAT = {"bait": 20.0, "salvo": 20.0, "between": 20.0, "phasers": 30.0, "close": 10.0, "open": 10.0,
                  "fight": 15.0, "hunt": 20.0, "evade": 5.0}   # seconds before the same kind of step is said again

LINE_TAG = "\0line:"         # an officer's remark being put in their own words
VOICE_STALE = 6.0           # seconds after which a remark is no longer worth saying
ADDRESS_TAG = "\0address"   # the model's verdict on the captain's speech, not an officer's answer
MORALE_GAP = 20.0           # seconds between remarks on the crew's spirits
REPAIR_REPORT_DAMAGE = 25   # % damage before a system is worth reporting
REPAIR_GAP = 12.0           # seconds between repair reports

MORALE_CAUSES = {
    ("damage", False): " after that damage", ("loss", False): " after losing a ship", ("shield", False): "",
    ("hits", True): " with every hit we land", ("kill", True): " after that kill", ("repairs", True): " as repairs come in",
    ("address", True): " after your words",
}

_PRAISE = re.compile(r"\b(thanks?|thank you|well done|good (job|work|shooting)|nice|great|excellent|bravo)\b")
_RUDE = re.compile(r"\b(stupid|idiot|useless|incompetent|shut up|moron|fool)\b")
_GREET = re.compile(r"^(hello|hi|hey|greetings|report in)\b")
_TAKE = re.compile(r"\b(take over|take (the |your )?(helm|station|tactical|weapons|engineering|science|sensors)"
                   r"|you have the (helm|station)|your station|take charge|you'?re in charge|handle it)\b")
# the whole bridge, not one station [E]
_BRIDGE_TAKE = re.compile(r"\b(take (the )?(bridge|conn|ship)|you have the (bridge|conn|ship)|take command|"
                          r"you'?re in command|you have command|command the ship|fight the ship)\b")
_BRIDGE_RELEASE = re.compile(r"\b(i have the (bridge|conn|ship)|i'?ll take (the bridge|the conn|command)|"
                             r"i'?m taking (the bridge|the conn|command)|i have command|i relieve you|"
                             r"(the )?captain'?s? on the bridge|give me (the bridge|the conn|command))\b")
_RELEASE = re.compile(r"\b(stand down|i have (the|it)|i'?ll (take|handle) (it|the)|i relieve you|belay)\b")
# "seven, cease fire" / "stop firing" / "belay that" / "stand down": every weapon stops and her objectives end [E]
_CEASE = re.compile(r"\b(cease ?fire|hold (your )?fire|stop (firing|shooting|the attack|attacking|that|it|this)|"
                    r"belay|stand down|cancel (that|it|this|your|the)|abort|break (it )?off|call (it )?off|knock it off|"
                    r"never ?mind)\b|^\s*stop\W*$")
# "disable the Klingons' shields", "knock out Gorkon's torpedoes", "cancel that objective"
_DISABLE = re.compile(r"\b(disable|disarm|cripple|knock out|take out|neutrali[sz]e|shut down|destroy|eliminate|"
                      r"finish off|kill|sink|blow up)\b")
# "worf, capture the Votek" / "seize her" / "take her intact" / "take her as a prize"
_CAPTURE = re.compile(r"\b(capture|seize|take (her|it|them|the [\w'-]+) (intact|alive|as (a )?prize))\b")
_KILL_VERBS = ("take out", "destroy", "eliminate", "finish off", "kill", "sink", "blow up", "knock out")
_FIRING = re.compile(r"^\s*(fire\b|tachyon\s+\S)")  # an order to fire the round, not to design one
# "spock, manage repairs" / "repairs are yours"; "I'll handle repairs" takes them back [E]
_REPAIRS_TAKE = re.compile(r"\b(manage|handle|run|direct|see to|take (care of|over)|look after|oversee|in charge of|"
                           r"prioriti[sz]e)\b[^.]*\brepairs?\b|\brepairs? (are|is) (yours|up to you)\b")
_REPAIRS_RELEASE = re.compile(r"\b(i'?ll|i will|let me) (manage|handle|direct|run|do) (the )?repairs?\b|"
                              r"\brepairs? (are|is) mine\b|\b(stop|quit) (managing|directing) (the )?repairs?\b")
_STATUS = re.compile(r"\b(status|report|sitrep|situation|how are|how's|condition)\b")
_ADVICE = re.compile(r"\b(advice|advise|recommend|suggest|what (should|do you|now|next)|ideas?|options?|thoughts?|opinion)\b")


def _could_be_officer(word: str) -> bool:
    """A lone first word names an officer only if it can't also be a console command ('sc' is scan, not a name starting sc)."""
    from ..console.parser import VERBS

    if len(word) < 3:
        return False
    return not any(sp.startswith(word) for spellings in VERBS.values() for sp in spellings)


class Bridge:
    def __init__(self, crew: Crew, hidden: dict[str, object], llm: LLMService | None = None,
                 seed: int = 0, chatter: bool = True) -> None:
        self.crew = crew
        self.hidden = hidden
        self.llm = llm
        self.hold_voices = False      # the captain is waiting on the model: say remarks as written
        self.rng = random.Random(seed ^ 0x5EB)
        self.chatter = chatter
        self.relationships = Relationships.from_settings(hidden)
        for o in crew.officers.values():
            if o.rapport_floor > -1.0:
                self.relationships.get(o.id).hold_at_least(o.rapport_floor)
        self.recent: dict[str, deque[str]] = {}          # officer -> what they said lately, so the model varies it
        self._voicing: dict[int, tuple[str, int, str]] = {}   # request -> (officer, tick asked, the canned line)
        self.history: dict[str, list[Message]] = {}
        self.suggested: dict[str, tuple[int, list[str]]] = {}   # officer -> (tick, commands)
        self.asking: dict[str, bool] = {}   # officer -> the pending LLM request is a question, not an order
        self._nudged: set[str] = set()      # officers whose empty answer has been asked for again
        self._last_line: dict[str, int] = {}
        self._last_any = -999
        self._hull_band = 4
        self._repair_seen: set[str] = set()        # damaged systems already reported
        self._repair_band = 4                      # quarter of the hull last reported
        self._repair_said = -999                   # tick of the last repair report
        self._repair_prio: object = None           # the priority last announced by the officer managing repairs
        self._address_pending: AddressCrew | None = None   # a speech the model is judging
        self._addresses: list[AddressCrew] = []              # judged speeches, ready to take effect
        self._morale_said = -999
        self._threats = 0
        self._llm_note_given = False
        self._conn_target: int | None = None
        self._disabled_seen: set[tuple[str, int]] = set()
        self._step_said: dict[str, str] = {}     # officer -> the step kind last called out
        self._callout_at: dict[str, int] = {}    # officer -> tick of their last callout
        self._kind_said: dict[tuple[str, str], int] = {}
        self._knocked: dict[tuple[str, int], int] = {}   # (group, ship) -> systems seen knocked out
        self._names: dict[int, str] = {}                     # ship names we have known, for after they're gone   # (group, ship) already reported knocked out

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
        # no comma: "seven take the bridge", "sev status", "Seven of Nine report"
        words = text.strip().split()
        for n in (3, 2, 1):
            if len(words) < n:
                continue
            name = " ".join(words[:n]).lower()
            if n == 1 and not _could_be_officer(name):
                continue
            o = self.find(name)
            if o is not None:
                return o, " ".join(words[n:])
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
        turn = self.handover(low)
        if turn == "release" and not (ctx.ship is not None and ctx.ship.conn):
            turn = None   # nobody has the bridge: "I relieve you" means this officer's station
        if turn is not None:
            err = run(f"conn {officer.id}" if turn == "take" else "conn captain", officer)
            if err:
                return [self._say(officer, err, "caution")]
            return self.handover_lines(officer, turn == "take")
        if _CEASE.search(low):
            return self.cease(officer, low, run)
        if _REPAIRS_RELEASE.search(low) or _REPAIRS_TAKE.search(low):
            taking = not _REPAIRS_RELEASE.search(low)
            err = run(f"repair auto {officer.id}" if taking else "repair manual", officer)
            if err:
                return [self._say(officer, err, "caution")]
            self._repair_said = -999
            if not taking:
                return [self._say(officer, "The repair crews are yours, Captain.")]
            return [self._say(officer, "Understood. I will direct the repair crews and tell you what I am doing.")]
        m = _CAPTURE.search(low)
        if m is not None:
            if m.group(1) in ("capture", "seize"):
                rest = low[m.end():]
            else:
                rest = "" if m.group(2) in ("her", "it", "them") else m.group(2)   # "her": the current target
            return self.objective(officer, f"capture {rest}", run)
        m = _DISABLE.search(low)
        if m is not None:
            rest = low[m.end():]
            from ..console.parser import Parser

            names_systems = any(w.strip(".,!?'\"").removesuffix("'s") in Parser._DISABLE_WORDS for w in rest.split())
            if m.group(1) in _KILL_VERBS and not names_systems:
                verb = "destroy"     # "take out the Wraith": the whole ship
            else:
                verb = "disarm" if m.group(1) == "disarm" else "cripple"   # both always mean the enemy's systems
            return self.objective(officer, f"{verb} {rest}", run)
        collab = None if _FIRING.match(low) else collaborations.matching(officer.id, low)
        if collab is not None:
            return self.collaborate(officer, collab, run)
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

    @staticmethod
    def handover(text: str) -> str | None:
        """'take' when the captain gives an officer the bridge, 'release' when taking it back, else None."""
        low = text.lower()
        if _BRIDGE_RELEASE.search(low):
            return "release"
        if _BRIDGE_TAKE.search(low):
            return "take"
        return None

    def handover_lines(self, officer: OfficerProfile, taking: bool) -> list[Utterance]:
        if taking:
            return [self._line(officer, "bridge") or self._say(officer, "Aye, Captain. I have the bridge.")]
        return [self._line(officer, "bridge_released") or self._say(officer, "The bridge is yours, Captain.")]

    def cease(self, officer: OfficerProfile, low: str, run: RunCommand) -> list[Utterance]:
        """The captain tells an officer to stop: no language model, no delay. Every weapon ceases fire and the
        officers' objectives end; "stand down" also hands back their station."""
        err = run("cease fire", officer)
        if err:
            return [self._say(officer, err, "caution")]
        if "stand down" in low:
            run(f"assume {officer.station}", officer)    # not delegated is fine: the cease fire is what matters
            return [self._say(officer, "Standing down. Weapons are cold, Captain.")]
        return [self._say(officer, "Ceasing fire, Captain.")]

    def objective(self, officer: OfficerProfile, line: str, run: RunCommand) -> list[Utterance]:
        """The captain sets the officer a standing objective; they say how they'll go about it."""
        err = run(line, officer)
        if err:
            return [self._say(officer, err, "caution")]
        if any(w in line.split() for w in ("off", "cancel", "stop", "belay", "abort")):
            return [self._line(officer, "ack") or self._say(officer, "Understood.")]
        return [self._line(officer, "objective") or self._say(officer, "Understood. I will see to it, Captain.")]

    def collaborate(self, officer: OfficerProfile, collab: collaborations.Collaboration,
                    run: RunCommand) -> list[Utterance]:
        """Officers set to work together on a project; each says their part."""
        from ..sim.projects import PROJECTS

        err = run(f"design {collab.project}", officer)
        proj = PROJECTS.get(collab.project)
        if err and proj is not None and proj.use and "already set up" in err:
            err = run(proj.use, officer)     # it's built: use it
            return [self._say(officer, err, "caution")] if err else [self._line(officer, "ack") or self._say(officer, "Aye.")]
        if err:
            return [self._say(officer, err, "caution")]
        return self._chorus(collab.start)

    def _chorus(self, lines: Iterable[tuple[str, str]], **fill: object) -> list[Utterance]:
        out: list[Utterance] = []
        for oid, text in lines:
            o = self.find(oid)
            if o is not None:
                out.append(self._say(o, text.format(**fill)))
        return out

    # ------------------------------------------------------------ the captain's address

    def judge_address(self, cmd: AddressCrew, ctx: HelpContext) -> bool:
        """Ask the model how rousing the captain's words are; False when there is no model (an ordinary speech)."""
        if self.llm is None or self._address_pending is not None or not cmd.text:
            return False
        self._address_pending = cmd
        system = ("You judge a starship captain's address to the crew in the middle of a space battle. Score how "
                  "rousing it is from 0 to 1.5: 1 is a competent, ordinary address; 1.5 is truly stirring and fits the "
                  "moment; 0.3 or less is flat, rude, confusing or demoralising. Then give the first officer's one-line "
                  "remark on how the crew took it, in character. Reply only with JSON: "
                  '{"score": <number>, "reaction": "<one line>"}\n\nThe situation:\n' + situation(ctx))
        self.llm.submit(ADDRESS_TAG, system, [{"role": "user", "content": cmd.text}])
        return True

    def _voiced(self, rid: int, text: str | None, ctx: HelpContext) -> list[Utterance]:
        """An officer's remark in their own words; too late, and the moment has passed; failed, the line as written."""
        oid, asked, canned = self._voicing.pop(rid, ("", 0, ""))
        o = self.find(oid) if oid else None
        if o is None:
            return []
        tick = ctx.obs.tick if ctx.obs is not None else asked
        if tick - asked > VOICE_STALE * (ctx.obs.rules.ticks_per_cycle if ctx.obs is not None else 10):
            return []
        line = spoken(text or "")
        if not line or len(line) > 240:
            line = canned
        return [self._say(o, line)]

    def take_addresses(self) -> list[AddressCrew]:
        out, self._addresses = self._addresses, []
        return out

    def address_reaction(self, cmd: AddressCrew, said: str = "") -> list[Utterance]:
        """The first officer remarks on how the crew took the captain's words."""
        o = self.find("spock") or self.crew.officer("science") or next(iter(self.officers()), None)
        if o is None:
            return []
        if not said:
            if cmd.rousing >= 1.2:
                said = "The crew is with you, Captain. I have rarely seen them so resolved."
            elif cmd.rousing >= 0.8:
                said = "The crew heard you, Captain. Spirits are up."
            else:
                said = "The crew heard you, Captain. I am not certain it helped."
        return [self._say(o, said)]

    def _judged(self, text: str | None) -> list[Utterance]:
        cmd, self._address_pending = self._address_pending, None
        if cmd is None:
            return []
        said = ""
        if text:
            try:
                m = re.search(r"\{.*\}", text, re.S)
                data = json.loads(m.group(0)) if m else {}
                cmd.rousing = max(0.0, min(1.5, float(data.get("score", 1.0))))
                said = str(data.get("reaction", "")).strip()
            except (ValueError, TypeError):
                cmd.rousing = 1.0
        self._addresses.append(cmd)
        return self.address_reaction(cmd, said)

    def poll(self, ctx: HelpContext, run: RunCommand) -> list[Utterance]:
        """LLM answers that have arrived since the last frame."""
        if self.llm is None:
            return []
        out: list[Utterance] = []
        for r in self.llm.poll():
            if r.tag == ADDRESS_TAG:
                out.extend(self._judged(r.text))
                continue
            if r.tag.startswith(LINE_TAG):
                out.extend(self._voiced(r.request_id, r.text, ctx))
                continue
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
            if not say and not commands and officer.id not in self._nudged:
                # the model said nothing at all: ask once more for a spoken answer before giving up on it
                self._nudged.add(officer.id)
                self.llm.submit(officer.id, self.system_prompt(officer, ctx) + "\n\n" + NUDGE, hist)
                continue
            if not say and not commands:
                if hist and hist[-1]["role"] == "user":
                    hist.pop()
                self._nudged.discard(officer.id)
                self.asking.pop(officer.id, None)
                out.append(self._line(officer, "unknown") or self._say(officer, "I don't follow, Captain."))
                continue
            self._nudged.discard(officer.id)
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
        out: list[Utterance] = []
        if not low or _GREET.match(low):
            out.append(self._line(o, "greeting") or self._say(o, "Captain."))
        elif _RUDE.search(low):
            out.append(self._line(o, "rude") or self._say(o, "Understood, Captain."))
        elif _PRAISE.search(low) and not _ADVICE.search(low):
            out.append(self._line(o, "thanks") or self._say(o, "Thank you, Captain."))
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

    def character(self, o: OfficerProfile) -> str:
        """Who the officer is for the model: the persona, their traits, and what they said lately."""
        out = o.persona
        if o.traits:
            out += (f" Your character traits: {', '.join(o.traits)}. Let them colour how you speak and how you are "
                    "with the captain; they never change how well you do your job.")
        said = list(self.recent.get(o.id, ()))
        if said:
            out += (" Things you have said lately (never repeat them or their wording; find a fresh way to say "
                    "it): " + " | ".join(said[-8:]))
        return out

    @staticmethod
    def style(o: OfficerProfile) -> str:
        """The officer's response style, said last and plainly so even a small model keeps to it."""
        if not o.response_style:
            return ""
        return (f"YOUR VOICE, above all else: {o.response_style}. Every word you say must sound like this; "
                "a reply in a plain, neutral voice is wrong.")

    def _voice(self, o: OfficerProfile, canned: str, obs: Observation) -> bool:
        """With a model, an officer's remark in their own words, never the same twice; False to say it as written."""
        if self.llm is None or self.hold_voices or self.llm.busy(LINE_TAG + o.id):
            return False
        rel = self.relationships.get(o.id)
        s = obs.own(self.crew.ship_id)
        mood = f" The crew's morale is {morale_words(s.morale)}." if s is not None else ""
        system = (self.character(o) + f" Your relationship with the captain: {rel.mood}.{mood} You are on the bridge in "
                  "the middle of a starship battle. Say ONE short remark (at most 20 words) to the effect of the line "
                  "below, in your own voice and words, keeping every name and number exactly. Reply with the "
                  "remark only, no quotes, JSON or stage directions. Variation " + str(self.rng.randrange(10 ** 6))
                  + ". " + self.style(o)).strip()
        rid = self.llm.submit(LINE_TAG + o.id, system, [{"role": "user", "content": canned}])
        self._voicing[rid] = (o.id, obs.tick, canned)
        return True

    def system_prompt(self, o: OfficerProfile, ctx: HelpContext) -> str:
        rel = self.relationships.get(o.id)
        stations = ", ".join(STATION_NAMES[s] for s in o.advises)
        return "\n".join([
            self.character(o),
            "",
            "Setting: the captain is speaking to you on the bridge during a real-time battle in a 2D tactical "
            "starship game. Courses are compass bearings (0 = up the map, 90 = right). Distances are in units; "
            "warp 1 = 100 units per second.",
            (f"The captain has given you command of the bridge: you run every station and may use any command "
             "below, but the captain's orders come first. " if ctx.ship is not None and ctx.ship.conn == o.id else
             f"You run the {STATION_NAMES[o.station]} station and advise on: {stations}. ")
            + f"Your relationship with the captain: {rel.mood}.",
            "Answer with ONE JSON object and nothing else:",
            '{"say": "<what you say aloud, at most three short sentences>", "commands": ["<console command>", ...]}',
            "Always say something in reply. The captain may simply talk to you, about the battle or anything else: "
            "then answer in character, in conversation, and leave the command list empty. "
            "Put commands in the list only when the captain orders you to act; when the captain asks a question, "
            "the list holds what you recommend, and the captain decides. Use only commands for your stations, "
            "written exactly in this console syntax:",
            COMMAND_SYNTAX,
            "",
            "What the ship knows right now:",
            situation(ctx),
            "",
            self.style(o),
        ]).strip()

    # ------------------------------------------------------------ chatter

    def react(self, events: Iterable[Event], ctx: HelpContext) -> list[Utterance]:
        """Officers comment on what just happened (rate limited)."""
        s, obs = ctx.ship, ctx.obs
        if s is None or obs is None:
            return []
        for c in obs.contacts().values():
            if c.identified:
                self._names[c.id] = _name(obs, c.id)
        out = self._objective_reports(events, s, obs)   # asked-for work is always reported
        out.extend(self._callouts(s, obs))
        out.extend(self._repair_reports(s, obs))
        out.extend(self._morale_remarks(events, s, obs))
        if not self.chatter:
            return out
        delegated = s.delegated
        commander = self.find(s.conn) if s.conn else None
        if commander is not None and s.target is not None and s.target != self._conn_target:
            self._maybe(out, obs, "", "bridge_target", 1.0, gap=4.0, officer=commander, target=_name(obs, s.target))
        self._conn_target = s.target if commander is not None else None
        for ev in events:
            if isinstance(ev, ProjectCompleted) and ev.ship_id == s.id:
                collab = collaborations.for_project(ev.project)
                if collab is not None and (ev.tube is not None or "{tube}" not in str(collab.done)):
                    out.extend(self._chorus(collab.done, tube=(ev.tube or 0) + 1))
                    self._last_any = obs.tick
            elif isinstance(ev, (TorpedoLaunched, PhaserFired)) and ev.ship_id == s.id and s.objectives:
                continue   # the officer working the objective says what she is firing and why
            elif isinstance(ev, TorpedoLaunched) and ev.ship_id == s.id and commander is not None:
                self._maybe(out, obs, "", "bridge_torpedoes", 0.5, officer=commander)
            elif isinstance(ev, TorpedoLaunched) and ev.ship_id == s.id and "tactical" in delegated:
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
        if threats > self._threats and "helm" not in s.delegated and not s.evasive:
            self._maybe(out, obs, "helm", "incoming", 0.5)   # advice: with an officer at the helm, they just dodge
        self._threats = threats
        temp = max((d.temp for d in s.drives if not d.destroyed), default=0.0)
        if temp > obs.rules.temp_limit * 0.85:
            self._maybe(out, obs, "engineering", "hot", 1.0, gap=20.0)
        return out

    def _callouts(self, s: Ship, obs: Observation) -> list[Utterance]:
        """Officers flying the ship or working an objective say what they're doing as they start each step
        [E], so the captain can follow it: "Evading two torpedoes, coming to 270 warp 6." Rate limited."""
        out: list[Utterance] = []
        tpc = obs.rules.ticks_per_cycle
        for a in self.crew.activity(obs):
            if a.kind == self._step_said.get(a.officer_id) or a.kind not in CALLOUT_KINDS:
                if a.kind not in CALLOUT_KINDS:
                    self._step_said[a.officer_id] = a.kind
                continue
            if obs.tick - a.since < CALLOUT_SETTLE.get(a.kind, 1.0) * tpc:
                continue   # wait until the step has stuck, so a helm that changes its mind doesn't chatter
            if obs.tick - self._callout_at.get(a.officer_id, -10 ** 9) < CALLOUT_GAP * tpc:
                continue
            if obs.tick - self._kind_said.get((a.officer_id, a.kind), -10 ** 9) < CALLOUT_REPEAT.get(a.kind, 0.0) * tpc:
                self._step_said[a.officer_id] = a.kind   # the same move again: once is enough for a while
                continue
            o = self.find(a.officer_id)
            if o is None:
                continue
            self._step_said[a.officer_id] = a.kind
            self._callout_at[a.officer_id] = self._kind_said[(a.officer_id, a.kind)] = obs.tick
            out.append(self._say(o, a.doing.rstrip(".") + "."))
        out.extend(self._knockouts(s, obs))
        return out

    def _morale_remarks(self, events: Iterable[Event], s: Ship, obs: Observation) -> list[Utterance]:
        """The first officer says when the crew's spirits shift sharply (a band of 20 points)."""
        shifts = [ev for ev in events if isinstance(ev, MoraleShift) and ev.ship_id == s.id and ev.cause != "rest"]
        if not shifts or obs.tick - self._morale_said < MORALE_GAP * obs.rules.ticks_per_cycle:
            return []
        o = self.find("spock") or self.crew.officer("science")
        if o is None:
            return []
        ev = shifts[-1]
        self._morale_said = obs.tick
        word = morale_words(ev.morale)
        why = MORALE_CAUSES.get((ev.cause, ev.rising), "")
        if ev.rising:
            text = f"Morale is rising, Captain{why}: the crew is {word} ({ev.morale:.0f})."
        else:
            text = f"Captain, the crew is {word}{why} (morale {ev.morale:.0f})."
            if ev.morale < 40 and obs.tick - s.last_address >= obs.rules.morale_address_cycles * obs.rules.ticks_per_cycle:
                text += " A word from you might steady them."
        u = self._say(o, text, "crew" if ev.rising else "caution")
        if not ev.rising:
            u.commands = ["address crew "]
        return [u]

    def _repair_reports(self, s: Ship, obs: Observation) -> list[Utterance]:
        """Spock (or the engineer) says when systems or the hull need repairs and offers to direct the crews;
        once directing them, says where he sends them. Spoken even with chatter off, like callouts."""
        tpc = obs.rules.ticks_per_cycle
        manager = self.crew.repair_officer(s)
        if manager is not None:
            prio = s.repair_priority
            if prio != self._repair_prio and obs.tick - self._repair_said >= REPAIR_GAP * tpc / 2:
                self._repair_prio = prio
                self._repair_said = obs.tick
                where = ("the hull" if prio == HULL else f"the {KIND_LABEL[prio].lower()}s" if isinstance(prio, Kind)
                         else "every damaged system")
                return [self._say(manager, f"Repair crews to {where}.")]
            return []
        self._repair_prio = s.repair_priority
        reporter = self.find("spock") or self.crew.officer("engineering")
        if reporter is None or not s.alive:
            return []
        damaged = {sub.sid: sub for sub in s.subsystems() if sub.damage >= REPAIR_REPORT_DAMAGE}
        new = [damaged[sid] for sid in damaged if sid not in self._repair_seen]
        self._repair_seen &= set(damaged)
        hull = max(0.0, s.structure) / max(1.0, s.structure_max)
        band = int(hull * 4)
        worse_hull = band < self._repair_band
        if not new and not worse_hull:
            self._repair_band = band     # repaired back up: a later drop is news again
            return []
        if obs.tick - self._repair_said < REPAIR_GAP * tpc:
            return []
        self._repair_said = obs.tick
        self._repair_seen |= {sub.sid for sub in new}
        self._repair_band = band
        parts = []
        if new:
            worst = sorted(new, key=lambda sub: -sub.damage)
            names = ", ".join(f"{sub.label.lower()} {'destroyed' if sub.destroyed else f'{sub.damage}%'}"
                              for sub in worst[:3])
            more = f" and {len(worst) - 3} more" if len(worst) > 3 else ""
            parts.append(f"{names}{more} need repairs")
        if worse_hull or hull < 0.75:
            parts.append(f"hull at {hull * 100:.0f}%")
        text = "Captain, " + "; ".join(parts) + ". Shall I direct the repair crews?"
        u = self._say(reporter, text)
        u.commands = [f"repair auto {reporter.id}"]
        return [u]

    def _knockouts(self, s: Ship, obs: Observation) -> list[Utterance]:
        """'Wraith: 3 of 6 shields out.' as each scan shows another of the asked-for systems down."""
        from .objectives import group_state, label

        out: list[Utterance] = []
        for o in s.objectives:
            if o.goal != "disable":
                continue
            officer = (self.find(o.officer) if o.officer else None) or self.crew.officer("science")
            if officer is None:
                continue
            for t in o.targets:
                st = group_state(obs.contact(t), o.group)
                if st is None or st[0] == 0:
                    continue
                key = (o.group, t)
                if st[1] > self._knocked.get(key, 0) and st[1] < st[0] and key not in self._disabled_seen:
                    what = DISABLE_GROUPS.get(o.group, o.group)
                    out.append(self._say(officer, f"{label(obs, t, self.crew.names)}: {st[1]} of {st[0]} {what} out."))
                self._knocked[key] = st[1]
        return out

    def _objective_reports(self, events: Iterable[Event], s: Ship, obs: Observation) -> list[Utterance]:
        out = self._objective_progress(s, obs)
        for ev in events:
            if not (isinstance(ev, ObjectiveEnded) and ev.ship_id == s.id and ev.outcome != "cancelled"):
                continue
            o = (self.find(ev.officer) if ev.officer else None) or self.crew.officer("science")
            if o is None:
                continue
            systems = DISABLE_GROUPS.get(ev.group, ev.group)
            names = ", ".join(self._names.get(t, f"#{t}") for t in ev.targets)
            if ev.outcome == "done" and ev.goal == "capture":
                out.append(self._line(o, "objective_captured", targets=names)
                           or self._say(o, f"{names} is ours, Captain. The boarding parties hold her."))
            elif ev.outcome == "done" and ev.goal == "destroy":
                out.append(self._line(o, "objective_destroyed", targets=names)
                           or self._say(o, f"{names}: destroyed, Captain."))
            elif ev.outcome == "done":
                out.append(self._line(o, "objective_done", targets=names, systems=systems)
                           or self._say(o, f"Done, Captain: {names} have lost their {systems}."))
            else:
                out.append(self._line(o, "objective_failed", reason=ev.reason)
                           or self._say(o, f"I can't finish that: {ev.reason}.", "caution"))
            pl = self.crew.planners.get(o.id)
            if pl is not None and pl.tally_for[:2] == (ev.goal, ev.group):
                from .objectives import summary

                out.append(self._say(o, "That took " + summary(pl, obs.tick, obs.rules.ticks_per_cycle), "dim"))
            self._last_any = obs.tick
        return out

    def _objective_progress(self, s: Ship, obs: Observation) -> list[Utterance]:
        """Report each enemy ship as its asked-for systems go down (judged, like the officer does, by scans)."""
        from .objectives import disabled

        out: list[Utterance] = []
        for o in s.objectives:
            if o.goal != "disable":
                continue   # a ship taken out is reported as it goes
            officer = (self.find(o.officer) if o.officer else None) or self.crew.officer("science")
            if officer is None:
                continue
            gone = obs.gone()
            for t in o.targets:
                key = (o.group, t)
                if key in self._disabled_seen or not disabled(obs.contact(t), o.group):
                    continue
                self._disabled_seen.add(key)
                left = [x for x in o.targets if x not in gone and not disabled(obs.contact(x), o.group)]
                if not left:
                    continue   # the closing report says it
                more = f"{len(left)} to go."
                systems = DISABLE_GROUPS.get(o.group, o.group)
                out.append(self._line(officer, "objective_progress", target=_name(obs, t), systems=systems, left=more)
                           or self._say(officer, f"{_name(obs, t)}'s {systems} are down. {more}"))
        return out

    def outcome(self, won: bool | None) -> list[Utterance]:
        o = self.crew.officer("helm") or next(iter(self.crew.officers.values()), None)
        if o is None or won is None:
            return []
        u = self._line(o, "victory" if won else "defeat")
        return [u] if u else []

    def _maybe(self, out: list[Utterance], obs: Observation, station: str, event: str, p: float,
               gap: float = 8.0, officer: OfficerProfile | None = None, **fill: object) -> None:
        o = officer or self.crew.officer(station)
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
            if not self._voice(o, u.text, obs):
                out.append(u)

    # ------------------------------------------------------------ bits

    def _say(self, o: OfficerProfile, text: str, tone: str = "crew") -> Utterance:
        if tone == "crew":
            self.recent.setdefault(o.id, deque(maxlen=12)).append(text)
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
  scan <ship> | design tachyon (Spock and Seven build a detector round for cloaked ships)
  tachyon <bearing> <range> | tachyon <ship> (burst the loaded detector round there)
  design deflector (set the dish up for tachyon pulses) | pulse (expose cloaked ships ahead of the bow)
  disable <shields|phasers|torpedoes|weapons|engines|sensors> <ships|all> | disable off   (a standing objective)
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


_SAY = re.compile(r'"say"\s*:\s*"((?:\\.|[^"\\])*)', re.S)


NUDGE = ("Your last answer had nothing to say aloud. Reply now, in character, with at least one short sentence "
         "in \"say\".")


def first_object(text: str) -> dict[str, object] | None:
    """The first JSON object in a model's answer, even with prose, code fences or a second copy around it."""
    dec = json.JSONDecoder()
    i = text.find("{")
    while i >= 0:
        try:
            data, _ = dec.raw_decode(text, i)
        except ValueError:
            data = None
        if isinstance(data, dict):
            return data
        i = text.find("{", i + 1)
    return None


def spoken(text: str) -> str:
    """What to show as speech from an answer that may be JSON, broken JSON, or plain words."""
    data = first_object(text)
    if data is not None:
        return str(data.get("say", "")).strip()
    m = _SAY.search(text)                       # broken or cut-off JSON: rescue the words, never show the braces
    if m:
        try:
            return str(json.loads('"' + m.group(1).rstrip("\\") + '"')).strip()
        except ValueError:
            return m.group(1).replace('\\"', '"').strip()
    if "{" in text and '"' in text and ":" in text:
        text = text[:text.find("{")]           # some other JSON-ish tail: keep only the words before it
    return text.strip().strip("`").strip().strip('"').strip()


def parse_reply(text: str) -> tuple[str, list[str]]:
    """The model's JSON reply → (spoken text, commands). Plain text is accepted as speech."""
    data = first_object(text)
    if data is None:
        return spoken(text), []
    cmds = data.get("commands") or []
    if not isinstance(cmds, list):
        cmds = [cmds]
    return str(data.get("say", "")).strip(), [c for c in (clean_command(str(x)) for x in cmds) if c][:4]


def situation(ctx: HelpContext) -> str:
    """A compact, factual summary of what the player's side knows (no hidden information)."""
    s, obs = ctx.ship, ctx.obs
    if s is None or obs is None:
        return "No ship."
    lines = [
        f"Our ship: {s.name}, {s.cls.name}. Hull {_pct(s.structure, s.structure_max)}, crew {s.crew}/{s.cls.crew}, "
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
        out += f" {damaged} systems damaged; repairs on {repair_words(s.repair_priority, 'everything')}."
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


__all__ = ["Bridge", "COMMAND_SYNTAX", "STATION_REPORTS", "Utterance", "first_object", "parse_reply", "situation", "spoken"]
