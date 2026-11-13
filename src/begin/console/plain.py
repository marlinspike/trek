"""A captain's plain words turned into the console's own, and a line of several orders split into its parts."""

from __future__ import annotations

import re

from ..sim.away import SHUTTLE_NAMES
from .vocab import AIM_FIRST, VERBS, candidates, is_num, match_word, system_word


# plain-English stop orders said to the bridge at large [E]; "seize fire" is a cease fire, not a capture
STOP_FIRE = re.compile(
    r"(?:(?:seize|sieze|ceese|sease|ceaze|cese|ceace|ceas)\s+fir(?:e|ing)|hold\s+(?:your|our|all|the)\s+fire|"
    r"(?:don'?t|do\s+not)\s+(?:shoot|fire)|weapons\s+(?:cold|hold|tight|safe)|"
    r"stop\s+(?:attacking|engaging|disabling|targeting|shooting\s+at|firing\s+at|the\s+(?:attack|run))|"
    r"abort\s+(?:the\s+)?(?:attack|run|attack\s+run|objective)|(?:call|break)\s+(?:it\s+)?off|disengage|"
    r"(?:leave|let)\s+(?:them|her|him|it)\s+(?:alone|go|be)|spare\s+(?:them|her|him|it)\b|"
    r"forget\s+(?:the|their|her|its|it|that|about)\b|never\s*mind|"
    r"cancel(?:\s+(?:that|it|this|objective|the\s+(?:order|attack|disable|objective)))?\W*$)")
STOP_ALL = re.compile(r"(?:stand\s*down|standown|knock\s+it\s+off|that'?s\s+enough|enough)\W*$")

_THEIR_TYPOS = re.compile(r"\b(?:thier|theri|thir|ther|theyre|they're)\b")
_POSSESSIVE = re.compile(r"\b(their|her|its|his|them|enemy|enemies|all|both|every|each)\b|\w's\b|\ws'(?=\s|$)")
# "hit their shields", "bring down her shields", "get their shields down": a disable, when it names their systems
_SOFT_DISABLE = re.compile(r"^(?:hit|shoot(?:\s+at)?|go\s+after|bring\s+down|take\s+down|knock\s+down|get|"
                           r"blast|pound|hammer|concentrate\s+(?:fire\s+)?on)\s+(.+)$")
_WANT_DOWN = re.compile(r"^(?:i want|i need|we need|i'?d like)\s+((?:their|her|its|his)\b.*?)\s+(?:down|out|gone|offline)\W*$")
_PLASMA = r"(?:warp\s+|nacelle\s+)?(?:exhaust|plasma(?:\s+trails?)?|trails?|leaks?)"
_HIVE_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    # [E] the Borg and the hunt by plasma, in a captain's words
    (re.compile(r"^(" + "|".join(n.lower() for n in SHUTTLE_NAMES) + r")\b[\s,:]*(.*)$"), r"hail \1 \2"),   # "Galileo, come back"
    (re.compile(r"^(?:take|fly|grab|use|get\s+in(?:to)?)\s+(?:a|the|one\s+of\s+the)\s+shuttle(?:craft)?s?\b"
                r"\s*(?:over\s+|across\s+)?(?:to\s+)?(.*)$"), r"away \1"),
    (re.compile(r"^(?:go|beam)\s+(?:over|across|aboard)\b\s*(?:to\s+)?(.*)$"), r"away \1"),
    (re.compile(r"^(?:look|search|scan|sniff|watch|check|hunt)\s+(?:out\s+)?(?:around\s+)?for\s+(?:any\s+)?"
                + _PLASMA + r"\b.*$"), "sweep"),
    (re.compile(r"^(?:try\s+(?:to\s+)?)?(?:detect|find|look\s+for|search\s+for)\s+(?:any\s+)?"
                r"(?:ships?|anything|anyone|contacts?)\s+(?:nearby|around|close\s+by|out\s+there)\W*$"), "sweep"),
    (re.compile(r"^(?:try\s+(?:to\s+)?)?(?:find|follow|track|detect|trace)\s+(.+?)\s+(?:by|from|through|with)\s+"
                r"(?:her|its|his|their|the)\s+" + _PLASMA + r"\W*$"), r"sweep \1"),
    (re.compile(r"^(?:program|design|build|make|rig|prepare|modify)\s+(?:us\s+)?(?:a|the|some)?\s*"
                r"(?:torpedo(?:es)?|torps?|round)\s+(?:to\s+|that\s+will\s+|that\s+can\s+)?"
                r"(?:follow|track|chase|ride|home\s+on|seek|hunt)\b.*$"), "design seeker"),
    (re.compile(r"^(?:fire|launch|send)\s+(?:a\s+|the\s+|our\s+)?(?:plasma[-\s])?seekers?\b\s*(.*)$"), r"seeker \1"),
    (re.compile(r"^(?:scan|analy[sz]e|study|survey)\s+(?:.+?\s+)?(?:for\s+)?(?:(?:the|their|her|its)\s+)?"
                r"(?:shield\s+)?harmonics\W*$"), "duty harmonics"),
    (re.compile(r"^(?:find|get|crack|steal\s+their)\s+(?:the\s+|their\s+|her\s+|its\s+)?(?:shield\s+)?harmonics\W*$"),
     "duty harmonics"),
)
_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = _HIVE_REWRITES + (
    (re.compile(r"^all\s+stop\b"), "stop"),                           # "all stop": the engines, as on any bridge
    (re.compile(r"^i'?ll\s+take\s+(?:it\s+from\s+here|over|it)\b"), "i have it"),
    (re.compile(r"^i'?ll\s+(?:take|handle|run)\s+"), "i have "),         # "I'll take the helm"
    (re.compile(r"^i'?ll\s+fly(?:\s+(?:her|it|the\s+ship))?\b"), "i have nav"),
    # "give me all she's got", said to the bridge at large: engineering puts a team on the drives [E]
    (re.compile(r"^(?:give\s+me\s+)?(?:all|everything)\s+(?:she|you)(?:['’]?s|['’]?ve|\s+has|\s+have)?\s+got\W*$"), "boost"),
    (re.compile(r"^give\s+me\s+"), "i have "),                          # "give me the helm"
    (re.compile(r"^(?:the\s+)?(\w+)\s+(?:is|are)\s+mine\b"), r"i have \1"),
    (re.compile(r"^stop\s+evading\b|^no\s+more\s+evasive\b"), "evasive off"),
    (re.compile(r"^evasives\b"), "evasive"),
    (re.compile(r"^finish\s+off\s+"), "destroy "),                      # "finish off the Wraith"
    (re.compile(r"^finish\s+(.+?)(?:\s+off)?\W*$"), r"destroy \1"),     # "finish her off"
    (re.compile(r"^take\s+(.+?)\s+out\W*$"), r"take out \1"),          # "take their shields out", "take them all out"
)


def plain_order(text: str) -> str:
    """A captain's plain words in the console's own: typos of 'their', 'I'll take the helm', 'all stop',
    'hit their shields', 'finish her off'. Anything else is left as it was typed."""
    low = text.strip().lower()
    if not low or _SPOKEN.match(low):
        return text          # a message, a hail or a macro: the captain's own words, untouched
    low = _THEIR_TYPOS.sub("their", low)
    for pat, repl in _REWRITES:
        new = pat.sub(repl, low, count=1)
        if new != low:
            return new.strip()
    m = _WANT_DOWN.match(low)
    if m is not None and any(system_word(w) for w in m.group(1).split()):
        return f"disable {m.group(1)}"           # "I want their shields down"
    m = _SOFT_DISABLE.match(low)
    if m is not None and _POSSESSIVE.search(m.group(1)) and any(system_word(w) for w in m.group(1).split()):
        return f"disable {m.group(1)}"
    return low if low != text.strip().lower() else text


# a later order in the same line starts with a verb: "cease fire and take evasive action", "stand down, I have nav"
_SPLIT = re.compile(r"\s*(?:[,;]|\band\s+then\b|\bthen\b|\band\b)\s*")
_NO_SPLIT = ("tell", "order", "key", "address", "ask", "say", "text", "translate", "interpret", "english")
# words said over a channel to another captain are theirs to hear, never orders to our own bridge:
# "hail them, stand down and you will live"
_SPOKEN = re.compile(r"^(?:(?:" + "|".join(_NO_SPLIT) + r"|hail|hailing|channel)\b|"
                     r"open\s+(?:a\s+)?(?:channel|hailing|frequencies|comms|communications)\b)")


def _starts_order(piece: str) -> bool:
    first = (piece.split() or [""])[0].rstrip("!?.")
    if not first or is_num(first) or system_word(first) or first in AIM_FIRST:
        return False
    return first in ("i", "i've", "ive", "i'll", "ill", "stand", "take", "knock", "all", "give", "finish") or \
        match_word(first, VERBS) is not None or len(candidates(first, VERBS)) > 1 or bool(STOP_FIRE.match(piece) or STOP_ALL.match(piece))


def split_orders(text: str) -> list[str]:
    """The separate orders in a line, where each after the first plainly starts a new one; else the line."""
    low = text.strip()
    if not low or _SPOKEN.match(low.lower()):
        return [low]
    pieces: list[str] = []
    start = 0
    for m in _SPLIT.finditer(low):
        if m.start() == 0:
            continue
        after = low[m.end():].lower()
        if _starts_order(after):
            pieces.append(low[start:m.start()])
            start = m.end()
    pieces.append(low[start:])
    pieces = [p.strip(" ,;") for p in pieces if p.strip(" ,;")]
    if len(pieces) > 1 and not _starts_order(pieces[0].lower()):
        return [low]         # "7, stand down": the first part is no order of its own
    return [plain_order(p) for p in pieces] if len(pieces) > 1 else [low]


__all__ = ["STOP_ALL", "STOP_FIRE", "plain_order", "split_orders"]
