"""Who speaks with which voice [E].

Each officer is cast from the voices the computer already has, to suit the character as written: Spock calm and
exact, Worf deep and clipped, Geordi warm and quick, Seven cool and level, Sulu smooth and sure, Chekov young and
quick (Russian-accented where the computer has a Russian voice), the Doctor brisk and dry, the ship's computer
even and unhurried. Enemy captains are cast by race. These are castings, not impressions: no actor's voice is
copied, only the qualities of the part (accent, pitch, pace).

For each part the cast lists the voices it would like, best first, for each kind of speech engine: macOS (`say`),
Windows (SAPI), eSpeak NG on Linux, and Piper's neural voices. The first one the computer has is used; if it has
none of them, a voice of the right kind (a man's or a woman's, in English) stands in. Pitch and pace are set per
part on top, so two parts that land on the same voice still sound apart. The player can recast any part in
Settings; their choice is kept in settings.json ("speech": {"cast": ...}).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Cast:
    title: str                    # how Settings names the part
    manner: str                   # what the casting is going for, in a few words
    female: bool
    mac: tuple[str, ...]
    windows: tuple[str, ...]
    espeak: str
    piper: tuple[str, ...]
    rate: float = 1.0             # × normal pace
    pitch: float = 1.0            # × normal pitch (engines that can't change pitch rely on the voice)


CAST: dict[str, Cast] = {
    "spock": Cast("Spock", "calm, exact, unhurried", False,
                  ("Evan", "Tom", "Alex", "Nathan", "Aaron", "Reed (English (US))", "Fred"),
                  ("David", "Guy", "Mark"), "en-us+m3", ("ryan", "john", "joe", "norman"), 0.92, 0.9),
    "worf": Cast("Worf", "deep, slow, clipped", False,
                 ("Ralph", "Evan", "Fred", "Rocko (English (US))", "Alex"),
                 ("David", "Mark"), "en-us+m1", ("hfc_male", "joe", "bryce", "ryan"), 0.88, 0.72),
    "geordi": Cast("La Forge", "warm, quick, easy", False,
                   ("Aaron", "Nathan", "Tom", "Eddy (English (US))", "Alex"),
                   ("Mark", "Guy", "David"), "en-us+m2", ("bryce", "kusal", "joe", "ryan"), 1.06, 1.04),
    "seven": Cast("Seven of Nine", "cool, precise, level", True,
                  ("Allison", "Ava", "Susan", "Zoe", "Karen", "Tessa", "Samantha"),
                  ("Zira", "Aria", "Jenny"), "en-us+f3", ("amy", "kristin", "ljspeech", "hfc_female"), 0.94, 0.96),
    "sulu": Cast("Sulu", "smooth, sure, steady", False,
                 ("Nathan", "Evan", "Tom", "Alex", "Reed (English (US))"),
                 ("Guy", "David", "Mark"), "en-us+m4", ("john", "ryan", "joe"), 1.0, 0.95),
    "chekov": Cast("Chekov", "young, quick, eager, Russian-accented", False,
                   ("Yuri", "Daniel", "Aaron", "Alex"),
                   ("Pavel", "Mark"), "en-us+m5", ("kusal", "joe", "bryce"), 1.12, 1.14),
    "doctor": Cast("The Doctor", "brisk, dry, a little superior", False,
                   ("Daniel", "Oliver", "Arthur", "Alex"),
                   ("George", "Mark", "David"), "en-gb+m3", ("alan", "northern_english_male", "joe"), 1.08, 1.0),
    "computer": Cast("Ship's computer", "even, cool, unhurried", True,
                     ("Samantha", "Karen", "Moira", "Allison", "Ava"),
                     ("Zira", "Hazel", "Susan"), "en-us+f2", ("lessac", "amy", "kristin"), 0.97, 1.0),
    "klingon": Cast("Klingon captains", "harsh, low, proud", False,
                    ("Ralph", "Fred", "Rocko (English (US))", "Evan"),
                    ("David", "Mark"), "en-us+m1", ("hfc_male", "joe"), 0.9, 0.65),
    "romulan": Cast("Romulan captains", "cold, silky, careful", False,
                    ("Daniel", "Oliver", "Arthur"),
                    ("George", "David"), "en-gb+m2", ("alan", "northern_english_male"), 0.95, 0.92),
    "orion": Cast("Orion captains", "sly and fast", False,
                  ("Rishi", "Tom", "Eddy (English (US))"),
                  ("Mark", "Ravi"), "en-us+m6", ("kusal", "bryce"), 1.05, 1.0),
    "borg": Cast("The Borg", "many voices as one", False,
                 ("Fred", "Ralph", "Alex"),
                 ("David",), "en-us+m1", ("hfc_male", "joe"), 0.85, 0.55),
    "captain": Cast("Other captains", "a stranger's voice", False,
                    ("Fred", "Alex", "Tom"),
                    ("Mark", "David"), "en-us+m3", ("joe", "ryan"), 1.0, 0.9),
}
OFFICERS = ("spock", "worf", "geordi", "seven", "sulu", "chekov", "doctor", "computer")
RACES = ("klingon", "romulan", "orion", "borg")

FEMALE_NAMES = frozenset({
    "Samantha", "Karen", "Moira", "Tessa", "Allison", "Ava", "Susan", "Zoe", "Victoria", "Kathy", "Fiona", "Serena",
    "Kate", "Shelley", "Sandy", "Flo", "Grandma", "Milena", "Veena", "Zira", "Hazel", "Aria", "Jenny", "Catherine",
    "Nicky", "Joelle", "Princess",
})
NOVELTY = frozenset({
    "Albert", "Bad News", "Bahh", "Bells", "Boing", "Bubbles", "Cellos", "Good News", "Jester", "Organ", "Superstar",
    "Trinoids", "Whisper", "Wobble", "Zarvox", "Junior", "Deranged", "Hysterical", "Pipe Organ",
})


@dataclass(frozen=True, slots=True)
class VoiceInfo:
    """A voice an engine has: its name as the engine takes it, its language ("en_US", "en-GB", "ru"), and, when the
    engine says, whether it is a woman's voice."""
    name: str
    lang: str = ""
    female: bool | None = None

    @property
    def english(self) -> bool:
        return self.lang.lower().replace("-", "_").startswith("en")

    @property
    def base(self) -> str:
        """Its plain name: "Reed" for "Reed (English (US))", "David" for "Microsoft David Desktop"."""
        n = self.name.split(" (")[0]
        if n.startswith("Microsoft "):
            n = n[len("Microsoft "):]
        return n.removesuffix(" Desktop").removesuffix(" Online").strip()

    def is_female(self) -> bool:
        return self.female if self.female is not None else self.base in FEMALE_NAMES


def part_for(officer: str | None, faction: str | None = None) -> str:
    """The part a line is spoken in: the officer's own, a race's for an enemy captain, else the computer's."""
    if officer and officer in CAST:
        return officer
    if faction:
        return faction if faction in CAST else "captain"
    return "computer" if not officer else "captain"


def _wanted(cast: Cast, kind: str) -> tuple[str, ...]:
    return {"mac": cast.mac, "windows": cast.windows, "piper": cast.piper}.get(kind, (cast.espeak,))


def _matches(want: str, v: VoiceInfo, kind: str) -> bool:
    if kind == "piper":
        return want in v.name               # "en_GB-alan-medium" holds "alan"
    if kind == "windows":
        return v.base == want or f" {want} " in f" {v.name} "
    return v.name == want or v.base == want and v.english


def cast_voice(part: str, kind: str, voices: list[VoiceInfo], chosen: str | None = None,
               taken: frozenset[str] = frozenset()) -> str | None:
    """The voice for a part: the player's choice if the engine still has it, the cast's first preference it has, or
    a stand-in of the right kind, one not in `taken` if there is one. None leaves the engine's own default."""
    if chosen and any(v.name == chosen for v in voices):
        return chosen
    cast = CAST.get(part, CAST["captain"])
    if kind == "espeak":
        return cast.espeak
    for want in _wanted(cast, kind):
        hit = next((v for v in voices if _matches(want, v, kind)), None)
        if hit is not None:
            return hit.name
    fit = [v for v in voices if v.english and v.base not in NOVELTY]
    same = [v for v in fit if v.is_female() == cast.female]
    pick = [v for v in same if v.name not in taken] or same or [v for v in fit if v.name not in taken] or fit
    if not pick:
        return None
    return pick[sum(map(ord, part)) % len(pick)].name   # parts without a match spread over what there is


CAST_ORDER = ("computer", "spock", "worf", "seven", "geordi", "sulu", "chekov", "doctor")


def cast_all(kind: str, voices: list[VoiceInfo], chosen: dict[str, str]) -> dict[str, str | None]:
    """The whole cast at once, so that no two officers share a voice while there are enough to go round.

    The player's own choices stand first. Then each officer, in `CAST_ORDER` (the ship's computer first: it speaks
    most), takes the first voice they asked for that no officer has yet; failing that, a stand-in of the right kind
    that no officer has; failing that, their first choice, shared (pitch and pace still keep the two apart). Enemy
    captains may share with anyone."""
    out: dict[str, str | None] = {}
    for part in CAST_ORDER:
        want = chosen.get(part)
        if want and any(v.name == want for v in voices):
            out[part] = want
    hits: dict[str, list[str]] = {}
    for part in CAST_ORDER:           # first, every officer who can have a voice they asked for, not yet taken
        if part in out:
            continue
        if kind == "espeak":
            out[part] = cast_voice(part, kind, voices)
            continue
        hits[part] = [hit.name for w in _wanted(CAST[part], kind)
                      if (hit := next((v for v in voices if _matches(w, v, kind)), None)) is not None]
        free = [h for h in hits[part] if h not in out.values()]
        if free:
            out[part] = free[0]
    for part in CAST_ORDER:           # then stand-ins, kept apart from those already cast
        if part in out:
            continue
        taken = frozenset(v for v in out.values() if v)
        others = [v for v in voices if v.name not in hits[part]]
        stand_in = cast_voice(part, kind, others, None, taken)
        out[part] = stand_in if stand_in not in taken or not hits[part] else hits[part][0]
    for part in CAST:
        if part not in out:
            out[part] = cast_voice(part, kind, voices, chosen.get(part))
    return out


def choices(part: str, voices: list[VoiceInfo]) -> list[str]:
    """The voices Settings offers for a part: the English ones (and any the cast names, such as a Russian voice for
    Chekov), without the novelty voices."""
    cast = CAST.get(part, CAST["captain"])
    named = set(cast.mac) | set(cast.windows) | set(cast.piper)
    out = [v.name for v in voices if v.base not in NOVELTY and (v.english or v.base in named or v.name in named)]
    return sorted(dict.fromkeys(out), key=str.lower)


__all__ = ["CAST", "CAST_ORDER", "OFFICERS", "RACES", "Cast", "VoiceInfo", "cast_all", "cast_voice", "choices", "part_for"]
