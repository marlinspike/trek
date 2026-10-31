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

import difflib
import json
import random
import re
from collections import deque
from typing import Iterable

from ..console.plain import split_orders
from ..console.reports import morale_words
from ..console.vocab import DISABLE_WORDS, HAVE_WORDS
from ..help.coach import HelpContext, tips
from ..llm.providers.base import Message
from ..llm.reply import NUDGE, parse_reply, spoken
from ..llm.service import LLMService
from ..sim.commands import AddressCrew
from ..sim.observation import Observation
from ..sim.ship import RepairTarget
from . import collaborations
from .characters import OfficerProfile, Relationships
from .chatter import Chatter
from .intents import (
    ADVICE, BRIDGE_RELEASE, BRIDGE_TAKE, CAPTURE, CEASE, DISABLE_ORDER, FIRING, GREET, HONORIFIC, HONORIFIC_WORDS, KILL_VERBS, POLITE,
    PRAISE, RELEASE, REPAIRS_RELEASE, REPAIRS_TAKE, RUDE, SOFT_ORDER, STAND_DOWN, STATUS, TAKE, TARGET_ORDER, WEAPONS_STATE,
    could_be_officer, is_question,
)
from .officers import STATION_NAMES, Crew
from .station_reports import STATION_REPORTS, plain, situation
from .utterance import RunCommand, Utterance

LINE_TAG = "\0line:"         # an officer's remark being put in their own words
VOICE_STALE = 6.0           # seconds after which a remark is no longer worth saying
ADDRESS_TAG = "\0address"   # the model's verdict on the captain's speech, not an officer's answer


_STATION_HANDBACK = {"helm": "the helm is", "tactical": "the weapons station is", "engineering": "engineering is",
                     "science": "the science station is"}


class Bridge(Chatter):
    def __init__(self, crew: Crew, hidden: dict[str, object], llm: LLMService | None = None,
                 seed: int = 0, chatter: bool = True) -> None:
        self.crew: Crew = crew
        self.hidden: dict[str, object] = hidden
        self.llm: LLMService | None = llm
        self.hold_voices: bool = False      # the captain is waiting on the model: say remarks as written
        self.rng: random.Random = random.Random(seed ^ 0x5EB)
        self.chatter: bool = chatter
        self.relationships: Relationships = Relationships.from_settings(hidden)
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
        self._last_any: int = -999
        self._hull_band: int = 4
        self._repair_seen: set[str] = set()        # damaged systems already reported
        self._repair_band: int = 4                      # quarter of the hull last reported
        self._repair_said: int = -999                   # tick of the last repair report
        self._repair_prio: RepairTarget | None = None   # the priority last announced by the officer managing repairs
        self._address_pending: AddressCrew | None = None   # a speech the model is judging
        self._addresses: list[AddressCrew] = []              # judged speeches, ready to take effect
        self._morale_said: int = -999
        self._threats: int = 0
        self._llm_note_given: bool = False
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
        """`worf, fire` / `spock: report` / `seven what do you see` / `mr worf, fire` / `wrof, cease fire`
        → (officer, the rest)."""
        if WEAPONS_STATE.match(text):
            return None          # "weapons cold": an order about the weapons, not to the weapons officer
        text = HONORIFIC.sub("", text, count=1)
        m = re.match(r"^\s*([a-z][a-z ]{1,24}?)\s*[,:]\s*(.*)$", text, re.I)
        if m:
            o = self.find(m.group(1)) or self._near(m.group(1))
            if o is not None:
                return o, m.group(2).strip()
        # no comma: "seven take the bridge", "sev status", "Seven of Nine report"
        words = text.strip().split()
        for n in (3, 2, 1):
            if len(words) < n:
                continue
            name = " ".join(words[:n]).lower()
            if n == 1 and not could_be_officer(name):
                continue
            o = self.find(name)
            if o is not None:
                return o, " ".join(words[n:])
        return None

    def _near(self, name: str) -> OfficerProfile | None:
        """The officer a slip of the keyboard meant ("wrof", "sevn", "spok"), when only one is that close."""
        q = name.lower().strip()
        if len(q) < 3:
            return None
        names = {n: o for o in self.officers() for n in (o.id, o.name.lower(), *o.aliases) if len(n) >= 3}
        close = difflib.get_close_matches(q, list(names), n=3, cutoff=0.7)
        hits = list(dict.fromkeys(names[c] for c in close))
        return hits[0] if len(hits) == 1 else None

    def split_addressed(self, text: str) -> list[str]:
        """'worf, target their shields and spock, take the helm': one line for each officer addressed."""
        names = sorted({n for o in self.officers() for n in (o.id, o.name.lower(), *o.aliases) if len(n) >= 3},
                       key=len, reverse=True)
        alt = "|".join(re.escape(n) for n in names)
        # a name after "and"/"then" needs its comma ("... and seven, take the conn"); after a comma it need not
        cut = re.compile(r"\s*(?:(?:\band\s+then\b|\bthen\b|\band\b)\s*(?=" + HONORIFIC_WORDS + r"(?:" + alt
                         + r")\s*[,:])|[,;]\s*(?=" + HONORIFIC_WORDS + r"(?:" + alt + r")(?:\s*[,:]|\s+[a-z])))", re.I)
        pieces = [p.strip(" ,;") for p in cut.split(text) if p.strip(" ,;")]
        return pieces if len(pieces) > 1 else [text]

    def drop_orders(self, officer: str | None = None) -> None:
        """Forget what the model was asked to do for these officers (all of them, by default): an answer that
        arrives after a cease fire or a stand down must not set anyone to work again."""
        if self.llm is None:
            return
        for oid in self.llm.forget(None if officer is None else {officer},
                                   keep=lambda tag: tag == ADDRESS_TAG or tag.startswith(LINE_TAG)):
            hist = self.history.get(oid)
            if hist and hist[-1]["role"] == "user":
                hist.pop()
            self.asking.pop(oid, None)
            self._nudged.discard(oid)

    # ------------------------------------------------------------ talking

    def ask(self, officer: OfficerProfile, text: str, ctx: HelpContext, run: RunCommand) -> list[Utterance]:
        """The captain speaks to an officer. Returns what is said now (an LLM answer arrives via `poll`)."""
        rel = self.relationships.get(officer.id)
        rel.exchanges += 1
        said = text.lower().strip()
        # "can you target their shields?", "please cease fire": orders, put politely
        low = POLITE.sub("", said).strip(" ?!.") if (POLITE.search(said) or not is_question(said)) else said
        low = low or said
        asked = is_question(low)     # "should we disable their shields?" asks for advice: nothing is fired
        pieces = [] if asked else split_orders(low)
        if len(pieces) > 1:          # "worf, cease fire and target their engines": each order in turn
            rel.exchanges -= 1
            return [u for piece in pieces for u in self.ask(officer, piece, ctx, run)]
        if PRAISE.search(low):
            rel.nudge(0.03)
        if RUDE.search(low):
            rel.nudge(-0.08)
        turn = self.handover(low)
        if turn == "release" and not (ctx.ship is not None and ctx.ship.conn):
            turn = None   # nobody has the bridge: "I relieve you" means this officer's station
        if turn is not None:
            err = run(f"conn {officer.id}" if turn == "take" else "conn captain", officer)
            if err:
                return [self._say(officer, err, "caution")]
            return self.handover_lines(officer, turn == "take")
        if REPAIRS_RELEASE.search(low) or REPAIRS_TAKE.search(low):
            taking = not REPAIRS_RELEASE.search(low)
            err = run(f"repair auto {officer.id}" if taking else "repair manual", officer)
            if err:
                return [self._say(officer, err, "caution")]
            self._repair_said = -999
            if not taking:
                return [self._say(officer, "The repair crews are yours, Captain.")]
            return [self._say(officer, "Understood. I will direct the repair crews and tell you what I am doing.")]
        if CEASE.search(low):
            return self.cease(officer, low, run)
        if STAND_DOWN.search(low):
            return self.stand_down(officer, ctx, run)
        m = RELEASE.search(low)
        if m is not None:
            return self.release(officer, ctx, run, named=next((g for g in m.groups()[1:] if g), ""))
        m = None if asked else TARGET_ORDER.match(low)
        if m is not None:      # "worf, target their shields" / "focus fire on their engines": no model, no delay
            return self.objective(officer, f"target {m.group(1)}", run)
        m = None if asked else CAPTURE.search(low)
        if m is not None:
            if m.group(1) in ("capture", "seize"):
                rest = low[m.end():]
            else:
                rest = "" if m.group(2) in ("her", "it", "them") else m.group(2)   # "her": the current target
            return self.objective(officer, f"capture {rest}", run)
        if not asked and SOFT_ORDER.match(low):
            # "hit their shields", "take down her shields", "finish her off", "take them out": the console's words
            return self.objective(officer, low, run)
        m = None if asked else DISABLE_ORDER.search(low)
        if m is not None:
            rest = low[m.end():]
            names_systems = any(w.strip(".,!?'\"").removesuffix("'s") in DISABLE_WORDS for w in rest.split())
            if m.group(1) in KILL_VERBS and not names_systems:
                verb = "destroy"     # "take out the Wraith": the whole ship
            else:
                verb = "disarm" if m.group(1) == "disarm" else "cripple"   # both always mean the enemy's systems
            return self.objective(officer, f"{verb} {rest}", run)
        collab = None if FIRING.match(low) else collaborations.matching(officer.id, low)
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
            self.asking[officer.id] = is_question(said)
            return [self._say(officer, "…", "dim")]
        return self.offline(officer, low, ctx, run)

    @staticmethod
    def handover(text: str) -> str | None:
        """'take' when the captain gives an officer the bridge, 'release' when taking it back, else None."""
        low = text.lower()
        if BRIDGE_RELEASE.search(low):
            return "release"
        if BRIDGE_TAKE.search(low):
            return "take"
        return None

    def handover_lines(self, officer: OfficerProfile, taking: bool) -> list[Utterance]:
        if taking:
            return [self._line(officer, "bridge") or self._say(officer, "Aye, Captain. I have the bridge.")]
        return [self._line(officer, "bridge_released") or self._say(officer, "The bridge is yours, Captain.")]

    def cease(self, officer: OfficerProfile, low: str, run: RunCommand) -> list[Utterance]:
        """The captain tells an officer to cease fire: no language model, no delay. Every weapon ceases fire and
        the officers' objectives end; whoever is flying the ship keeps flying it."""
        self.drop_orders()
        err = run("cease fire", officer)
        if err:
            return [self._say(officer, err, "caution")]
        return [self._say(officer, "Ceasing fire, Captain.")]

    def stand_down(self, officer: OfficerProfile, ctx: HelpContext, run: RunCommand) -> list[Utterance]:
        """The captain tells an officer to stop: no language model, no delay. Every weapon ceases fire, the
        objectives end, and the officer hands back what they were running: their station, the bridge if they
        had it, and the helm's evasive manoeuvres if they were flying."""
        self.drop_orders()
        err = run("cease fire", officer)
        if err:
            return [self._say(officer, err, "caution")]
        return self.release(officer, ctx, run, standing_down=True)

    def release(self, officer: OfficerProfile, ctx: HelpContext, run: RunCommand,
                standing_down: bool = False, named: str = "") -> list[Utterance]:
        """The officer hands their station back to the captain (and the bridge, if they have it); `named`, a
        station the captain said they have ("spock, I have weapons"), instead of the officer's own."""
        station = next((k for k, words in HAVE_WORDS.items() if named in words and k != "all"), "") if named else ""
        if station and station != officer.station:
            err = run(f"assume {station}", officer)
            what = _STATION_HANDBACK.get(station, "the station is")
            return [self._say(officer, err, "caution") if err else
                    self._say(officer, f"Aye. {what[:1].upper() + what[1:]} yours, Captain.")]
        ship = ctx.ship
        had_bridge = ship is not None and ship.conn == officer.id
        if had_bridge:
            run("conn captain", officer)
        run(f"assume {officer.station}", officer)    # not delegated is fine: nothing else to hand back
        if officer.station == "helm" and ship is not None and ship.evasive:
            run("evasive off", officer)
        what = "the bridge is" if had_bridge else _STATION_HANDBACK.get(officer.station, "the station is")
        if standing_down:
            return [self._say(officer, f"Standing down. Weapons are cold, and {what} yours, Captain.")]
        return [self._line(officer, "released") or self._say(officer, f"Aye. {what[:1].upper() + what[1:]} yours, Captain.")]

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
        if not low or GREET.match(low):
            out.append(self._line(o, "greeting") or self._say(o, "Captain."))
        elif RUDE.search(low):
            out.append(self._line(o, "rude") or self._say(o, "Understood, Captain."))
        elif PRAISE.search(low) and not ADVICE.search(low):
            out.append(self._line(o, "thanks") or self._say(o, "Thank you, Captain."))
        elif TAKE.search(low):
            err = run(f"delegate {o.station}", o)
            out.append(self._say(o, err, "caution") if err else (self._line(o, "delegated") or self._say(o, "Aye.")))
        elif ADVICE.search(low) or low.endswith("?") and not STATUS.search(low):
            out.extend(self.advice(o, ctx))
        elif STATUS.search(low):
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
        text = plain(best.text)
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
            ("The captain has given you command of the bridge: you run every station and may use any command "
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
  delegate <helm|tactical|engineering|science> | assume <station>   (hand a station to its officer, or take it back)
  stand down   (cease fire, every objective ends, every station and the bridge back to the captain)"""


# ------------------------------------------------------------------ station reports (offline answers)


__all__ = ["Bridge", "COMMAND_SYNTAX"]
