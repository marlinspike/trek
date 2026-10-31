"""Talking to enemy captains over a hail [E].

`Comms` sits between the console and the enemy ships, as `Bridge` does for the
officers. The captain types `hail <ship> <words>` (or `hail all ...`, or tells
an officer to open a channel). What happens is decided by the simulation
(`Hail` → sim/systems/disposition.py): the enemy captain's fear, anger and
resolve, their damage, their crew's morale and the odds. This module only
works out what the captain's words amount to, and puts the answer into words.

Without a language model, the words are sorted by keywords into a demand to
surrender, an order to withdraw, a threat, a taunt or plain talk (with any
threat, bluff or offer of fair terms noted), and the enemy answers with a line
from hails.toml for their race and mood. With a model, the model reads the
hail as the enemy captain would, judges how persuasive it is, and writes both
the yes and the no in character; the game still decides which one is said.

Captains also speak up on their own when what they watch changes their mind:
a taunt when enraged, a request for terms when shaken. The officers read each
answer for the captain ("They are close to breaking, Captain.").

Everything here is presentation: hails are ordinary commands and the replies
change nothing, so the simulation stays deterministic.
"""

from __future__ import annotations

import json
import random
import re
import time
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable

from ..content.loader import DATA_DIR
from ..llm.service import LLMService
from ..sim.commands import Command, Hail
from ..sim.events import CaptainMood, Event, HailAnswered, ShipStatusChanged
from ..sim.ship import Ship, ShipStatus
from ..sim.systems import disposition
from ..sim.world import World
from .characters import OfficerProfile
from .conversation import Utterance, first_object, spoken

Issue = Callable[[Command], "str | None"]

HAIL_TAG = "\0hail:"
VOICE_TAG = "\0hailvoice:"
VOICE_STALE = 10.0          # cycles after which a captain's own remark is no longer worth saying
SPEAK_GAP = 25.0            # cycles between one captain's own transmissions
ANY_GAP = 8.0               # cycles between any two unprompted transmissions
MAX_BROADCAST = 4           # 'hail all': at most this many captains answer through the model at once
CHANNEL_LINES = 4           # lines of the exchange the comms panel keeps

# what the captain's words ask for (checked in this order)
_SURRENDER = re.compile(r"\b(surrender|stand down|lower (your |all )?(the )?shields|drop (your |all )?(the )?shields|"
                        r"strike (your )?colou?rs|prepare to be boarded|yield|give up|power down (your )?weapons|"
                        r"lay down (your )?arms|heave to|capitulate)\b")
_WITHDRAW = re.compile(r"\b(withdraw|leave|retreat|go home|turn (back|around)|back off|break off|depart|get out|"
                       r"safe passage|let you go|clear off|disengage|pull back|go away|run along|leave this)\b")
_THREAT = re.compile(r"\b(or (be|you will|you'?ll|we will|we'?ll|else|die)|destroy (you|your)|wipe|annihilate|"
                     r"last chance|final warning|share (their|the same|the) fate|the fate of|end you|no mercy|blow you|"
                     r"obliterate|you will die|you'?re next|like the)\b")
_BLUFF = re.compile(r"\b((fleet|reinforcements|starfleet|squadron|armada|help|backup)\b.*\b(on (its|their|the) way|"
                    r"coming|arriving|inbound|minutes|en route)|new weapon|secret weapon|full strength|fully armed|"
                    r"undamaged|untouched|more ships|cloaked ships|we have (\w+ )?(more|dozens|hundreds)|"
                    r"our shields are (at )?(full|100))")
_TERMS = re.compile(r"\b(prisoners?|treated (well|fairly|honou?rably|with respect)|honou?r|mercy|spare|safe|"
                    r"returned|repatriat|terms|guarantee|you have my word|quarter|no one (else )?(needs|has) to die|"
                    r"your crew|lives|wounded|medical)\b")
_TAUNT = re.compile(r"\b(coward|cowards|fool|fools|pathetic|weak|worthless|scum|dogs?|toothless|afraid|"
                    r"run away|petty|joke|laughable|incompetent|idiots?|losers?)\b")
_EXCHANGE = re.compile(r"\b(prisoners?|your (people|crew|crewmen|officers) back|exchange|release (your|them)|"
                       r"return (your|them|the))\b")
_POLITE = re.compile(r"\b(please|captain|commander|respect|honou?red)\b")


@dataclass
class Judged:
    """What a hail amounts to: the demand, how it is backed, and how persuasive it is (0..1.5)."""

    intent: str = "talk"
    threat: bool = False
    bluff: bool = False
    persuasion: float = 1.0
    accept: str = ""          # the model's lines, if a model read it
    refuse: str = ""
    release: bool = False     # the hail offers back the prisoners we hold


def classify(text: str) -> Judged:
    """The offline reading of a hail: keywords, nothing cleverer."""
    low = " " + text.lower().strip() + " "
    j = Judged()
    if _SURRENDER.search(low):
        j.intent = "surrender"
    elif _WITHDRAW.search(low):
        j.intent = "withdraw"
    elif _THREAT.search(low):
        j.intent = "threat"
    elif _TAUNT.search(low):
        j.intent = "taunt"
    j.threat = j.intent in ("surrender", "withdraw") and bool(_THREAT.search(low))
    j.bluff = bool(_BLUFF.search(low))
    if _TERMS.search(low):
        j.persuasion += 0.2
    if _POLITE.search(low):
        j.persuasion += 0.05
    if j.intent in ("surrender", "withdraw") and _TAUNT.search(low):
        j.persuasion -= 0.35
    j.persuasion = max(0.0, min(1.5, j.persuasion))
    return j


# ------------------------------------------------------------------ lines

def load_lines(data_dir: Path = DATA_DIR, override: Path | None = None) -> dict[str, dict[str, Any]]:
    """hails.toml by race, with the player's own config/hails.toml read over it."""
    raw: dict[str, dict[str, Any]] = tomllib.loads((data_dir / "hails.toml").read_text(encoding="utf-8"))
    if override is not None and override.is_file():
        try:
            mine = tomllib.loads(override.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            mine = {}
        for race, table in mine.items():
            if isinstance(table, dict):
                raw.setdefault(race, {}).update(table)
    return raw


RACE_STYLE = {
    "klingon": "proud, blunt and honour-bound; scornful of weakness and of talk, respectful of courage; would rather "
               "die than be shamed, but may withdraw to save ships if it can be done with honour",
    "romulan": "cold, formal and calculating; suspicious of every offer; never admits weakness; thinks of the Empire's "
               "advantage first",
    "orion": "a mercenary pirate: cocky, practical and profit-minded; quick to bargain and quicker to run when a fight "
             "stops paying",
    "federation": "principled and measured; speaks plainly and keeps their word",
}


def _level(x: float, words: tuple[str, str, str, str]) -> str:
    return words[0] if x < 0.2 else words[1] if x < 0.45 else words[2] if x < 0.7 else words[3]


# ------------------------------------------------------------------ the comms panel's picture

@dataclass
class Channel:
    """One enemy captain we are talking to (or who spoke to us), for the comms panel and the map."""

    ship_id: int
    captain: str
    title: str
    ship: str
    faction: str
    cls_name: str
    status: str = "hailing"          # hailing | open | closed
    mood: str = "unknown"            # calm | shaken | enraged | wavering | broken | surrendered | withdrawing | unknown
    outcome: str = ""
    lines: list[tuple[str, str]] = field(default_factory=list)   # (who, text): "us" | "them" | "note"
    tick: int = 0                    # when it last changed

    def add(self, who: str, text: str, tick: int) -> None:
        self.lines.append((who, text))
        del self.lines[:-CHANNEL_LINES]
        self.tick = tick


class Comms:
    def __init__(self, world: World, side: int, llm: LLMService | None = None, seed: int = 0,
                 lines: dict[str, dict[str, Any]] | None = None, officers: Callable[[str], OfficerProfile | None] | None = None) -> None:
        self.world = world
        self.side = side
        self.llm = llm
        self.rng = random.Random(seed ^ 0x4A11)
        self.lines = lines if lines is not None else load_lines()
        self.officer = officers or (lambda station: None)     # the officer at a station, to read the answers
        self.channels: dict[int, Channel] = {}
        self.focus: int | None = None       # the channel the panel shows
        self.pinned = False                 # the captain picked it: keep it up even when quiet
        self.opened_at = -1e9               # wall-clock time the last channel opened (the map's rings)
        self._pending: dict[int, tuple[int, str, Judged]] = {}    # request -> (target, words, offline reading)
        self._voicing: dict[int, tuple[int, int, str]] = {}      # request -> (ship, tick asked, canned line)
        self._spoke_any = -10**9
        self._spoke: dict[int, int] = {}                           # ship -> tick of their last own transmission

    # ------------------------------------------------------------ who

    def channel(self, s: Ship) -> Channel:
        ch = self.channels.get(s.id)
        if ch is None:
            title = str(self._table(s.faction).get("title", "Captain"))
            ch = Channel(s.id, s.captain or "unknown", title, s.name, s.faction, s.cls.name, tick=self.world.tick)
            self.channels[s.id] = ch
        return ch

    def speaker(self, s: Ship) -> str:
        ch = self.channel(s)
        who = f"{ch.title} {ch.captain}" if ch.captain and ch.captain != "unknown" else ch.title
        return f"{who} ({s.name})"

    def _table(self, faction: str) -> dict[str, Any]:
        return {**self.lines.get("default", {}), **self.lines.get(faction, {})}

    def line(self, s: Ship, key: str, us: str) -> str:
        options = self._table(s.faction).get(key) or self.lines.get("default", {}).get(key) or []
        if not options:
            return ""
        lost = disposition._names(s.mood.seen_lost[-2:]) if s.mood.seen_lost else "our ships"
        text = str(self.rng.choice(list(options)))
        try:
            return text.format(captain=s.captain or "the captain", ship=s.name, us=us, lost=lost,
                               title=self._table(s.faction).get("title", "Captain"))
        except (KeyError, IndexError, ValueError):
            return text

    # ------------------------------------------------------------ the captain hails

    def hail(self, player: Ship, target: int | None, words: str, issue: Issue) -> list[Utterance]:
        """`hail <ship>|all <words>`. Returns what is said now; a model's answer arrives through `poll`."""
        w = self.world
        if target is None:
            targets = [s for s in w.ships.values() if s.alive and s.side != player.side
                       and w.apparent_position(player.side, s.id) is not None]
            if not targets:
                return [self._note("No enemy ship on sensors to hail.")]
        else:
            t = w.ships.get(target)
            if t is None:
                return [self._note("No such ship.")]
            targets = [t]
        out: list[Utterance] = []
        offline = classify(words)
        held = prisoners_held(w, player.side)
        exchange = bool(held and _EXCHANGE.search(words.lower()))
        if exchange:
            # we hold their people: an offer to send them back carries weight [E]
            offline.persuasion = min(1.5, offline.persuasion + 0.3)
            offline.release = True
            if offline.intent == "talk":
                offline.intent = "withdraw"
        sent = 0
        for t in targets:
            probe = Hail(ship_id=player.id, target=t.id, intent=offline.intent, text=words)
            err = probe.validate_now(w, player)
            if err:
                out.append(self._note(err if len(targets) == 1 else f"{t.name}: {err}"))
                continue
            ch = self.channel(t)
            ch.status = "hailing"
            ch.add("us", words or "(hailing frequencies open)", w.tick)
            self.focus = t.id
            self.opened_at = time.monotonic()
            if self.llm is not None and sent < MAX_BROADCAST:
                rid = self.llm.submit(f"{HAIL_TAG}{t.id}", self.system_prompt(player, t), [
                    {"role": "user", "content": words or "(The enemy captain opens a channel and waits.)"}])
                self._pending[rid] = (t.id, words, offline)
                sent += 1
                continue
            out.extend(self._send(player, t, words, offline, issue))
        if sent:
            out.append(self._note("Hailing frequencies open… waiting for a reply."))
        return out

    def _send(self, player: Ship, t: Ship, words: str, j: Judged, issue: Issue) -> list[Utterance]:
        """Issue the hail and put the answer into words."""
        w = self.world
        cmd = Hail(ship_id=player.id, target=t.id, intent=j.intent, persuasion=j.persuasion, threat=j.threat,
                   bluff=j.bluff, text=words, release=j.release)
        err = issue(cmd)
        ch = self.channel(t)
        if err:
            ch.status = "closed"
            return [self._note(f"{t.name}: {err}")]
        ev = cmd.answered
        if not isinstance(ev, HailAnswered):
            return []
        return self.answered(player, t, ev, j)

    def answered(self, player: Ship, t: Ship, ev: HailAnswered, j: Judged) -> list[Utterance]:
        ch = self.channel(t)
        ch.outcome = ev.outcome
        ch.mood = "surrendered" if ev.outcome == "surrender" else "withdrawing" if ev.outcome == "withdraw" else ev.mood
        if ev.outcome == "silence":
            ch.status = "closed"
            text = self.line(t, "silence", player.name)
            ch.add("note", text, self.world.tick)
            return [Utterance("", self.speaker(t), text, "enemy")] + self.read(player, t, ev)
        ch.status = "open"
        if ev.outcome in ("surrender", "withdraw"):
            text = j.accept or self.line(t, ev.outcome, player.name)
        elif j.refuse:
            text = j.refuse
        elif ev.outcome == "talk":
            text = self.line(t, f"talk_{ev.mood}", player.name) or self.line(t, "talk_calm", player.name)
        else:
            text = self.line(t, ev.outcome, player.name)
        ch.add("them", text, self.world.tick)
        return [Utterance("", self.speaker(t), text, "enemy")] + self.read(player, t, ev)

    # ------------------------------------------------------------ the officers' read

    def read(self, player: Ship, t: Ship, ev: HailAnswered) -> list[Utterance]:
        """An officer says what they make of the answer."""
        tac = self.officer("tactical")
        sci = self.officer("science") or tac
        if ev.outcome == "surrender" and tac is not None:
            return [Utterance(tac.id, tac.title, f"Their shields are down, Captain. Beam six or more across to take "
                              f"the {t.name}, her crew as prisoners, or fire straight into her hull.")]
        if ev.outcome == "withdraw" and tac is not None:
            back = next((p for p in ev.reason.split("; ") if "prisoners beamed back" in p), "")
            return [Utterance(tac.id, tac.title, f"The {t.name} is powering down weapons and breaking off, Captain. "
                              + (f"{back[0].upper()}{back[1:]}. " if back else "")
                              + "If we fire on her now, the agreement is void.")]
        o = sci
        if o is None:
            return []
        r = disposition.reading(self.world, player, t)
        if "scans don't back up" in ev.reason:
            say = "They have scanned us, Captain. They know our true condition, and they did not believe you."
        elif ev.outcome == "silence":
            say = "They are too angry to listen, Captain. Words will not reach them while that lasts."
        elif ev.outcome == "waver":
            say = "They are close to giving way, Captain. Pressed again, they may accept."
        elif ev.intent == "surrender" and t.faction == "klingon" and tac is not None and tac.id == "worf" \
                and self.rng.random() < 0.6:
            o = tac
            say = ("A Klingon captain will not surrender to a demand, Captain. Offer them a way to withdraw "
                   "with their honour intact, and they may take it.")
        elif ev.mood == "enraged":
            say = "Their captain is furious, Captain. Reasoning with them will not work while that anger lasts."
        elif ev.mood in ("shaken", "broken"):
            say = "They are frightened, Captain, but not yet beaten. A little more pressure may be enough."
        elif ev.mood == "wavering":
            say = "Their resolve is wearing thin, Captain."
        elif ev.intent in disposition.DEMANDS and r.odds < 0.45:
            say = "They believe they are winning, Captain. Words alone will not change that."
        elif ev.intent in disposition.DEMANDS:
            say = "They are not ready to yield, Captain. They have not yet lost enough to consider it."
        else:
            return []
        return [Utterance(o.id, o.title, say)]

    # ------------------------------------------------------------ the model

    def system_prompt(self, player: Ship, t: Ship) -> str:
        w = self.world
        m = t.mood
        r = disposition.reading(w, player, t)
        fac = w.content.factions[t.faction]
        us = w.content.factions[player.faction]
        title = self._table(t.faction).get("title", "Captain")
        intel = w.intel.get(t.side)
        c = intel.contacts.get(player.id) if intel is not None else None
        seen = (f"Your scans of {player.name} show hull {c.scan.structure_frac * 100:.0f}%."
                if c is not None and c.scan is not None else f"You have not scanned {player.name}.")
        allies = [s for s in w.ships.values() if s.alive and s.side == t.side and s.id != t.id]
        theirs = [s for s in w.ships.values() if s.alive and s.side == player.side and s.id != player.id]
        truth = (f"(For judging bluffs only, the truth about {player.name}: hull "
                 f"{max(0.0, player.structure) / max(1.0, player.structure_max) * 100:.0f}%, "
                 f"{player.torps_remaining} torpedoes left, {len(theirs)} allied ships with them, "
                 f"{sum(1 for a in w.arrivals if a.side == player.side)} more on the way.)")
        held = prisoners_held(w, player.side)
        return (
            f"You are {title} {t.captain or 'the captain'}, commanding the {t.name} ({t.cls.name}) of the "
            f"{fac.long_name}, in a space battle against the {us.long_name} starship {player.name}. "
            f"Play your race as Star Trek portrays it: {RACE_STYLE.get(t.faction, 'a capable starship captain')}.\n"
            f"Your temper: {_level(m.temper, ('cool and easily cowed', 'steady', 'quick to anger', 'hot-blooded'))}. "
            f"Your will: {_level(r.resolve, ('nearly broken', 'shaken', 'firm', 'unbending'))}. "
            f"Right now you are {_level(r.fear, ('unafraid', 'uneasy', 'afraid', 'terrified'))} and "
            f"{_level(r.anger, ('calm', 'irritated', 'angry', 'furious'))}"
            + (f"; you no longer trust their word" if m.distrust > 0.2 else "") + ".\n"
            f"Your ship: hull {max(0.0, t.structure) / max(1.0, t.structure_max) * 100:.0f}%, "
            f"{disposition.weapons_left(t) * 100:.0f}% of weapons working, crew morale {t.morale:.0f}/100. "
            f"Your side has {len(allies)} other ship{'s' if len(allies) != 1 else ''} still fighting"
            + (f"; you have watched {disposition._names(m.seen_lost)} lost" if m.seen_lost else "") + ". "
            f"As you judge it, the enemy holds {r.odds * 100:.0f}% of the strength on the field. {seen}\n"
            + (f"They hold {held} prisoners of war taken from your side's ships; an offer to return them is worth "
               "a lot to you. " if held else "")
            + f"{truth}\n\n"
            "The enemy captain hails you; their words are the user's message. Judge what they ask and how well "
            "they put it, then answer in character. Reply only with JSON:\n"
            '{"intent": "surrender|withdraw|threat|taunt|talk", "threat": true|false, "bluff": true|false, '
            '"persuasion": <0 to 1.5>, "accept": "<your words if you agree>", "refuse": "<your words if you refuse, '
            'or your answer when they ask nothing>"}\n'
            "intent: surrender = they demand you surrender, stand down or lower your shields; withdraw = they tell you "
            "to leave or break off, or offer to let you go; threat = they threaten without a demand; taunt = they "
            "insult or mock you; talk = anything else. threat: their demand is backed by a threat. bluff: they claim "
            "strength or help they do not have (check the truth above). persuasion: 1 is an ordinary hail; higher "
            "for fair terms (decent treatment of prisoners, safe passage, a way out with honour) or words that reach "
            "you; lower for rudeness, confusion or empty bluster.\n"
            "accept and refuse are one or two short sentences each, spoken by you over the channel. If you surrender "
            "you say you are lowering your shields. Use ordinary Star Trek language. You do not decide the outcome; "
            "the battle does.")

    def poll(self, player: Ship | None, issue: Issue) -> list[Utterance]:
        """Model answers that have arrived since the last frame."""
        if self.llm is None:
            return []
        out: list[Utterance] = []
        for r in self.llm.poll():
            if r.request_id in self._voicing:
                out.extend(self._voiced(r.request_id, r.text))
                continue
            pending = self._pending.pop(r.request_id, None)
            if pending is None or player is None:
                continue
            tid, words, offline = pending
            t = self.world.ships.get(tid)
            if t is None:
                continue
            j = offline
            if r.text is None:
                out.append(self._note(f"(LLM unavailable: {r.error}. The reply is from the script.)"))
            else:
                j = self.judged(r.text, offline)
            out.extend(self._send(player, t, words, j, issue))
        return out

    @staticmethod
    def judged(text: str, offline: Judged) -> Judged:
        data = first_object(text)
        if data is None:
            return Judged(offline.intent, offline.threat, offline.bluff, offline.persuasion, refuse=spoken(text)[:300],
                          release=offline.release)
        intent = str(data.get("intent", offline.intent)).lower().strip()
        if intent not in disposition.INTENTS:
            intent = offline.intent
        try:
            persuasion = max(0.0, min(1.5, float(data.get("persuasion", 1.0))))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            persuasion = offline.persuasion
        return Judged(intent, bool(data.get("threat", offline.threat)), bool(data.get("bluff", offline.bluff)),
                      persuasion, str(data.get("accept", "")).strip()[:300], str(data.get("refuse", "")).strip()[:300],
                      offline.release)

    # ------------------------------------------------------------ the enemy speaks up

    def react(self, events: Iterable[Event], player: Ship | None) -> list[Utterance]:
        """Captains whose state of mind has changed may hail us; ships that surrender or leave update the panel."""
        if player is None:
            return []
        w = self.world
        tpc = w.rules.ticks_per_cycle
        out: list[Utterance] = []
        for ev in events:
            if isinstance(ev, ShipStatusChanged) and ev.ship_id in self.channels:
                ch = self.channels[ev.ship_id]
                ch.mood = {"surrendered": "surrendered", "captured": "captured", "destroyed": "destroyed",
                           "escaped": "gone", "derelict": "adrift"}.get(ev.status, ch.mood)
                ch.status = "closed" if ev.status != "surrendered" else ch.status
                ch.tick = w.tick
                continue
            if not isinstance(ev, CaptainMood):
                continue
            s = w.ships.get(ev.ship_id)
            if s is None or not s.alive or s.side == player.side or w.apparent_position(player.side, s.id) is None:
                continue
            if ev.ship_id in self.channels or ev.mood == "betrayed":
                ch = self.channel(s)
                ch.mood = "enraged" if ev.mood == "betrayed" else ev.mood
                ch.tick = w.tick
            if (w.tick - self._spoke.get(s.id, -10**9) < SPEAK_GAP * tpc or w.tick - self._spoke_any < ANY_GAP * tpc) \
                    and ev.mood != "betrayed":
                continue
            chance = {"enraged": 0.5, "shaken": 0.55, "wavering": 0.6, "betrayed": 1.0}.get(ev.mood, 0.0)
            if self.rng.random() >= chance:
                continue
            self._spoke[s.id] = w.tick
            self._spoke_any = w.tick
            canned = self.line(s, ev.mood, player.name)
            if not canned:
                continue
            ch = self.channel(s)
            ch.mood = "enraged" if ev.mood == "betrayed" else ev.mood
            ch.status = "open"
            self.focus = s.id
            self.opened_at = time.monotonic()
            if self.llm is not None:
                rid = self.llm.submit(f"{VOICE_TAG}{s.id}", self.system_prompt(player, s) + VOICE_NOTE.format(
                    mood=ev.mood, cause=ev.cause or "what you have seen"), [{"role": "user", "content": canned}])
                self._voicing[rid] = (s.id, w.tick, canned)
                continue
            ch.add("them", canned, w.tick)
            out.append(Utterance("", self.speaker(s), canned, "enemy"))
        return out

    def _voiced(self, rid: int, text: str | None) -> list[Utterance]:
        sid, asked, canned = self._voicing.pop(rid)
        s = self.world.ships.get(sid)
        if s is None or self.world.tick - asked > VOICE_STALE * self.world.rules.ticks_per_cycle:
            return []
        said = ""
        if text:
            data = first_object(text)
            said = str(data.get("say", "")) if data is not None else spoken(text)
            said = said.strip()
        if not said or len(said) > 280:
            said = canned
        self.channel(s).add("them", said, self.world.tick)
        return [Utterance("", self.speaker(s), said, "enemy")]

    def dismiss(self) -> None:
        self.focus = None
        self.pinned = False

    def show(self, sid: int) -> None:
        self.focus = sid
        self.pinned = True

    def _note(self, text: str) -> Utterance:
        return Utterance("", "Comms", text, "dim")

    def visible(self) -> list[Channel]:
        """Channels worth showing, newest first."""
        return sorted(self.channels.values(), key=lambda c: -c.tick)

    def close(self) -> None:
        if self.llm is not None:
            self.llm.close()


VOICE_NOTE = ("\n\nThis time nobody hailed you: you open a channel yourself because you are {mood} by {cause}. "
              "The user's message is roughly what you mean to say; say it in your own words, in one or two short "
              'sentences. Reply only with JSON: {{"say": "<your words>"}}')


def mood_label(mood: str) -> str:
    return {"calm": "Composed", "shaken": "Shaken", "enraged": "Enraged", "wavering": "Wavering", "broken": "Broken",
            "surrendered": "Surrendered", "withdrawing": "Withdrawing", "captured": "Captured", "destroyed": "Destroyed",
            "gone": "Left the field", "adrift": "Adrift", "unknown": "Unknown"}.get(mood, mood.capitalize())


def prisoners_held(world: World, side: int) -> int:
    return sum(s.prisoners for s in world.ships.values() if s.side == side and s.alive)


def prisoners_lines(world: World, side: int) -> list[str]:
    ships = [s for s in world.ships.values() if s.side == side and s.prisoners > 0 and s.exists]
    if not ships:
        return ["We hold no prisoners. A ship that surrenders lowers her shields: beam six or more across to take her "
                "and her crew."]
    total = sum(s.prisoners for s in ships)
    return [f"Prisoners of war held: {total}."] + [f"  {s.name}: {s.prisoners} of her former crew, under guard."
                                                   for s in ships]


__all__ = ["Channel", "Comms", "Judged", "classify", "load_lines", "mood_label", "prisoners_lines"]
