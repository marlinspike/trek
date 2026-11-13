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
# "can you get the warp drive back?", "bring the shields back online": our own systems, repaired first
_BACK_UP = re.compile(r"^(?:can\s+you\s+|could\s+you\s+|i\s+need\s+you\s+to\s+)?(?:get|bring)\s+(?:the\s+|our\s+)?(.+?)\s+"
                      r"(?:back(?:\s+(?:online|up|on\s*line))?|online|working)(?:\s+(?:soon|now|fast|quickly))?\W*$")
_PLASMA = r"(?:warp\s+|nacelle\s+)?(?:exhaust|plasma(?:\s+trails?)?|trails?|leaks?)"
_HIT = (r"(?:strike|hit|kill|attack|destroy|take\s+out|knock\s+out|cripple|disable|target|blast|nail|"
        r"fire\s+(?:on|at|into)|lock\s+(?:on(?:\s+to)?|onto))")
# [E] sweep and strike, in a captain's words: "sweep and strike the Talon's shields", "seeker strike talon warp",
# "track her exhaust and hit her shields", "fire a seeker at the Talon and take out her engines"
STRIKE_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^(?:sweep|seeker)\s*,?\s+(?:(?:and|&|n|then)\s+)*" + _HIT + r"\b\s*(.*)$"), r"strike \1"),
    (re.compile(r"^(?:sweep\s+for|follow|track|trace|hunt(?:\s+down)?|find|ride|sniff\s+out)\s+(.*?)\b" + _PLASMA
                + r"\s*,?\s*(?:(?:and|then)\s+)+" + _HIT + r"\b\s*(.*)$"), r"strike \1 \2"),
    (re.compile(r"^(?:fire|launch|send)\s+(?:a\s+|the\s+|our\s+)?(?:plasma[-\s])?seekers?\b\s*(.*?)\s*,?\s*"
                r"(?:(?:and|then)\s+)+" + _HIT + r"\b\s*(.*)$"), r"strike \1 \2"),
    (re.compile(r"^(?:run\s+(?:the|a)\s+)?kill\s*chain\b\s*(?:on\s+)?(.*)$"), r"strike \1"),
)
_HIVE_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = STRIKE_REWRITES + (
    # [E] the Borg and the hunt by plasma, in a captain's words
    (re.compile(r"^(" + "|".join(n.lower() for n in SHUTTLE_NAMES) + r")\b[\s,:]*(.*)$"), r"hail \1 \2"),   # "Galileo, come back"
    (re.compile(r"^(?:take|fly|grab|use|get\s+in(?:to)?)\s+(?:a|the|one\s+of\s+the)\s+shuttle(?:craft)?s?\b"
                r"\s*(?:over\s+|across\s+)?(?:to\s+)?(.*)$"), r"away \1"),
    (re.compile(r"^(?:go|beam)\s+(?:over|across|aboard)\b\s*(?:to\s+)?(.*)$"), r"away \1"),
    (re.compile(r"^(?:send|assemble|launch)\s+(?:an?\s+|the\s+)?away\s+team\b\s*(?:over\s+|across\s+)?(?:to\s+)?(.*)$"),
     r"away \1"),
    (re.compile(r"^(?:send|beam)\s+(?:a\s+|the\s+)?boarding\s+party\b\s*(?:over\s+|across\s+)?(?:to\s+)?(.*)$"),
     r"board \1"),
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
    (re.compile(r"^(?:give\s+(?:me|us)|bring\s+us\s+(?:up\s+)?to)\s+warp\s+(?:factor\s+)?(\d+(?:\.\d+)?)\W*$"), r"warp \1"),
    (re.compile(r"^give\s+me\s+"), "i have "),                          # "give me the helm"
    (re.compile(r"^(?:the\s+)?(\w+)\s+(?:is|are)\s+mine\b"), r"i have \1"),
    (re.compile(r"^stop\s+evading\b|^no\s+more\s+evasive\b"), "evasive off"),
    (re.compile(r"^evasives\b"), "evasive"),
    (re.compile(r"^finish\s+off\s+"), "destroy "),                      # "finish off the Wraith"
    (re.compile(r"^finish\s+(.+?)(?:\s+off)?\W*$"), r"destroy \1"),     # "finish her off"
    (re.compile(r"^take\s+(.+?)\s+out\W*$"), r"take out \1"),          # "take their shields out", "take them all out"
) + (
    # [E] the bridge's everyday words, understood with no language model connected
    (re.compile(r"^(red|yellow|green)\s+alert\W*$"), r"alert \1"),
    (re.compile(r"^(?:launch|send|drop)\s+(?:a\s+|an\s+|the\s+|our\s+)?(probes?|torpedo(?:es|s)?|torps?)\b"), r"fire \1"),
    (re.compile(r"^(?:fire\s+(?:everything|all\s+weapons|all\s+we(?:'ve|\s+have)\s+got|all)|let\s+(?:them|her)\s+have\s+it|"
                r"full\s+spread|alpha\s+strike)\W*$"), "fire all phasers and fire all torpedoes"),
    (re.compile(r"^(?:fire|torpedoes|phasers|weapons|shoot)\s+(?:at\s+will|free)\W*$|^weapons\s+free\W*$"), "open fire"),
    (re.compile(r"^(?:go\s+to|engage\s+at|ahead|ahead\s+at|increase\s+to|reduce\s+to|bring\s+us\s+to|make)\s+"
                r"(?:warp|speed)\s*(?:factor\s+)?(\d+(?:\.\d+)?)\W*$"), r"warp \1"),
    (re.compile(r"^(?:warp\s+factor|warp\s+speed)\s+(\d+(?:\.\d+)?)\W*$"), r"warp \1"),
    (re.compile(r"^(?:ahead\s+full|full\s+ahead|full\s+speed(?:\s+ahead)?|maximum\s+(?:warp|speed)|max\s+(?:warp|speed)|punch\s+it|"
                r"(?:engage\s+)?(?:at\s+)?flank\s+speed)\W*$"), "warp max"),
    (re.compile(r"^(?:full\s+stop|come\s+to\s+(?:a\s+)?(?:full\s+)?stop|stop\s+(?:the\s+)?(?:ship|engines)|"
                r"cut\s+(?:the\s+)?engines)\W*$"), "stop"),
    (re.compile(r"^(?:slow\s+(?:down|us\s+down|it\s+down)|reduce\s+speed|ease\s+off)\W*$"), "warp down"),
    (re.compile(r"^(?:speed\s+(?:us\s+)?up|increase\s+speed|more\s+speed|faster)\W*$"), "warp up"),
    (re.compile(r"^(?:set\s+(?:a\s+)?course(?:\s+for)?|(?:new\s+)?heading|bearing|steer|come\s+to(?:\s+(?:course|heading))?|"
                r"turn\s+to(?:\s+(?:course|heading))?|change\s+course\s+to)\s+(\d+(?:\.\d+)?)\b(.*)$"), r"helm \1\2"),
    (re.compile(r"^(?:come|bring\s+(?:us|her|the\s+ship)|turn\s+(?:us\s+|her\s+)?)\s*(?:about|around)\W*$|"
                r"^(?:reverse\s+course|about\s+face)\W*$"), "helm about"),
    (re.compile(r"^(?:turn|hard|bank|veer|come|steer|bear|go)\s+(?:a\s+)?(?:hard\s+)?(?:to\s+)?(?:the\s+)?"
                r"(port|left|starboard|right)\b\s*(\d+)?(?:\s*degrees)?\W*$"), r"helm \1 \2"),
    # running and closing: 'retreat', 'get us out of here', 'keep our distance', 'take us in', 'close to 3000'
    (re.compile(r"^(?:retreat|withdraw|fall\s+back|run(?:\s+away|\s+for\s+it)?|bug\s+out|get\s+us\s+out(?:\s+of\s+here)?|"
                r"take\s+us\s+out(?:\s+of\s+(?:here|there))?|back\s+off|open\s+the\s+range|keep\s+(?:our|your|a\s+safe)\s+distance|break\s+away|"
                r"get\s+(?:us\s+)?(?:clear|away))\W*$"), "elude target"),
    (re.compile(r"^(?:close\s+(?:to|in\s+to)|close\s+the\s+range\s+to|get\s+within)\s+(\d+)\W*$"), r"pursue target \1"),
    (re.compile(r"^(?:take\s+us\s+in|close\s+(?:in|with\s+(?:them|her)|the\s+range|the\s+distance)|get\s+(?:us\s+)?closer|"
                r"move\s+in|go\s+in)\W*$"), "pursue target"),
    (re.compile(r"^(?:attack|engage|go\s+after|charge|intercept)\s*(?:the\s+)?(?:pattern\s+\w+)?\W*$"),
     "target nearest and pursue target and open fire"),
    (re.compile(r"^(?:attack|engage|go\s+after|charge)\s+(?!pattern\b)(.+?)\W*$"), r"target \1 and pursue \1 and open fire"),
    (re.compile(r"^(?:keep|continue)\s+(?:firing|shooting|it\s+up)\W*$"), "open fire"),
    # reports and questions the computer can answer on its own
    (re.compile(r"^(?:damage\s+report|how\s+bad(?:\s+is\s+it)?|what'?s\s+(?:the\s+)?damage)\W*$"), "damage"),
    (re.compile(r"^(?:status\s+report|sit\s*rep|what'?s\s+our\s+status|what\s+is\s+our\s+status|how\s+are\s+we\s+doing)\W*$"), "status"),
    (re.compile(r"^(?:how\s+are|status\s+of|check)\s+(?:the\s+|our\s+)?shields\W*$|^shield\s+status\W*$"), "status shields"),
    (re.compile(r"^(?:where\s+(?:is|are)\s+(?:the\s+)?(?:enemy|enemies|they|them|hostiles)|which\s+(?:ship\s+)?is\s+closest|"
                r"what'?s\s+out\s+there|what\s+do\s+we\s+(?:have|see)|contacts|show\s+(?:me\s+)?(?:the\s+)?contacts)\W*$"),
     "chart by distance"),
    (re.compile(r"^(?:what\s+do\s+you\s+(?:recommend|suggest|think)|what\s+(?:should|do)\s+we\s+do(?:\s+now)?|"
                r"(?:any\s+)?(?:suggestions|recommendations|ideas)|options|what\s+are\s+(?:my|our)\s+options)\W*$"), "counsel"),
    (re.compile(r"^(?:manage|handle|run|take\s+care\s+of|direct)\s+(?:the\s+)?repairs\W*$"), "repair auto"),
    (re.compile(r"^point[\s-]+defen[cs]es?\b"), "pd"),
    (re.compile(r"^(?:repair|fix|patch\s+up)\s+(?:the\s+|our\s+)?(.+?)\s+(?:first|now|immediately|right\s+away|asap|"
                r"before\s+anything\s+else)\W*$"), r"repair \1"),
    (re.compile(r"^(?:lay\s+in|plot|set)\s+(?:a\s+)?(?:course|heading)\s+(?:for|to|toward|towards)\s+(?!\d)(?:the\s+)?(.+?)\W*$"),
     r"pursue \1"),
    (re.compile(r"^(?:lock\s+on(?:to)?|target)\s+(?:the\s+)?(?:nearest|closest)(?:\s+(?:enemy|ship|one|hostile))?\W*$"),
     "target nearest"),
    # [E] the engineer's power, in a captain's words: "more power to the engines", "divert power to the forward shields"
    (re.compile(r"^(?:give\s+(?:me|us)\s+|(?:i\s+need|we\s+need)\s+)?(?:more|all|full|maximum|max|extra|emergency)?\s*"
                r"power\s+to\s+(?:the\s+)?(?:engines?|warp(?:\s+drive)?|drives?|propulsion|impulse|nacelles?)\W*$"), "boost"),
    (re.compile(r"^(?:divert|reroute|re-route|route|transfer|shunt|channel|put|send|give)\s+(?:all\s+|more\s+|auxiliary\s+|"
                r"emergency\s+|(?:all\s+)?(?:available|spare|reserve)\s+)?power\s+(?:to|into)\s+(?:the\s+)?"
                r"(?:engines?|warp(?:\s+drive)?|drives?|propulsion|impulse|nacelles?)\W*$"), "boost"),
    (re.compile(r"^(?:(?:give\s+(?:me|us)\s+|(?:i\s+need|we\s+need)\s+)?(?:more|all|full|maximum|max|extra|emergency)\s+power|"
                r"(?:divert|reroute|re-route|route|transfer|shunt|channel|put|send|give)\s+(?:all\s+|more\s+|auxiliary\s+|"
                r"emergency\s+|(?:all\s+)?(?:available|spare|reserve)\s+)?power)\s+(?:to|into)\s+(?:the\s+|our\s+)?"
                r"(forward|front|fore|bow|aft|rear|stern|port|left|starboard|right)?\s*shields?\W*$"), r"reinforce \1"),
    (re.compile(r"^(?:reinforce|strengthen|boost|bolster)\s+(?:the\s+|our\s+)?"
                r"(forward|front|fore|bow|aft|rear|stern|port|left|starboard|right)\s+shields?\W*$"), r"reinforce \1"),
    (re.compile(r"^(?:reinforce|strengthen|bolster)\s+(?:the\s+|our\s+)?shields?\W*$"), "reinforce"),
)

# [E] fleet orders, said to every ship of ours at once ("all ships, attack the Bismark", "fleet, fall back"); the order
# must follow, so Begin's own `fleet` display still works, and "everyone" stays the bridge crew
_FLEET = re.compile(r"^(?:all\s+(?:ships|hands|units|vessels)|(?:the\s+)?(?:fleet|squadron|wingmen|wing|task\s+force|flotilla)|"
                    r"every\s+ship)\b[\s,:;-]*(.+)$")
# the same order to the whole squadron, with no one named: "form up on me", "regroup"
_FORM_UP = re.compile(r"^(?:form\s+up(?:\s+on\s+(?:me|us|the\s+flagship))?|regroup|rally(?:\s+on\s+(?:me|us))?|"
                      r"fall\s+in|on\s+me|stay\s+(?:with\s+(?:me|us)|close)|follow\s+(?:me|us)|cover\s+(?:me|us)|"
                      r"escort\s+(?:me|us)|guard\s+(?:me|us)|protect\s+(?:me|us))\W*$")
# one ally's order in a captain's words -> the `tell` order it means
_ALLY_WORDS: tuple[tuple[re.Pattern[str], str], ...] = (
    (_FORM_UP, "escort me"),
    (re.compile(r"^(?:attack|engage|go\s+after|hit|fire\s+(?:on|at)|take\s+out)\s+(?:my|our|the)\s+target\W*$"), "attack target"),
    (re.compile(r"^(?:attack|engage|go\s+after|hit|fire\s+(?:on|at)|take\s+out|destroy|kill|charge|"
                r"(?:concentrate|focus)\s+(?:fire\s+)?on)\s+(?:the\s+)?(.+?)\W*$"), r"attack \1"),
    (re.compile(r"^(?:attack|engage|charge|go\s+get\s+(?:them|her)|weapons\s+free\s+and\s+attack)\W*$"), "attack target"),
    (re.compile(r"^(?:fall\s+back|retreat|run(?:\s+for\s+it)?|bug\s+out|pull\s+back|pull\s+out|break\s+off|"
                r"get\s+(?:out(?:\s+of\s+there|\s+of\s+here)?|clear))\W*$"), "run"),
    (re.compile(r"^(?:hold|cease|stop|check)\s+(?:your\s+|their\s+)?fir(?:e|ing)\W*$|^weapons\s+(?:hold|cold|tight)\W*$"),
     "hold fire"),
    (re.compile(r"^(?:open\s+fire|fire\s+at\s+will|weapons\s+free)\W*$"), "open fire"),
    (re.compile(r"^(?:defend|protect|guard|cover|shield)\s+(?:the\s+)?(.+?)\W*$"), r"defend \1"),
    (re.compile(r"^(?:report(?:\s+in)?|status(?:\s+report)?|sit\s*rep|check\s+in)\W*$"), "report"),
    (re.compile(r"^(?:all\s+)?(?:stop|halt|hold\s+(?:your\s+)?position|hold\s+station)\W*$"), "stop"),
)


def ally_words(text: str) -> str:
    """What an ally (or the whole squadron) is told, in the words `tell` reads: 'fall back' is 'run', 'form up on me'
    is 'escort me', 'take out the Wraith' is 'attack wraith'. Anything else is passed on as it was said."""
    low = re.sub(r"^(?:to|please)\s+", "", text.strip().lower())     # "tell the Yorktown to fall back"
    for pat, repl in _ALLY_WORDS:
        new = pat.sub(repl, low, count=1)
        if new != low:
            return new.strip()
    return low or "attack target"


def fleet_order(text: str) -> str | None:
    """'tell all ...' for an order given to every ship of ours at once, else None."""
    low = text.strip().lower()
    m = _FLEET.match(low)
    if m is not None:
        return "tell all " + ally_words(m.group(1))
    if _FORM_UP.match(low):
        return "tell all escort me"
    return None


def plain_order(text: str) -> str:
    """A captain's plain words in the console's own: typos of 'their', 'I'll take the helm', 'all stop',
    'hit their shields', 'finish her off'. Anything else is left as it was typed."""
    low = text.strip().lower()
    if not low or _SPOKEN.match(low):
        return text          # a message, a hail or a macro: the captain's own words, untouched
    low = _THEIR_TYPOS.sub("their", low)
    fleet = fleet_order(low)
    if fleet is not None:
        return fleet
    for pat, repl in _REWRITES:
        new = pat.sub(repl, low, count=1)
        if new != low:
            return new.strip()
    m = _BACK_UP.match(low)
    if m is not None and (named := next((w for w in m.group(1).split() if system_word(w)), None)) is not None:
        return f"repair {named}"                 # "can you get the warp drive back?"
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


def is_strike(text: str) -> bool:
    """[E] 'Sweep and strike the Talon's shields': one order (the whole kill chain), however many verbs it has."""
    low = _THEIR_TYPOS.sub("their", text.strip().lower())
    return low.startswith(("strike ", "sweep strike")) or any(p.match(low) for p, _ in STRIKE_REWRITES)


def _starts_order(piece: str) -> bool:
    first = (piece.split() or [""])[0].rstrip("!?.")
    if not first or is_num(first) or system_word(first) or first in AIM_FIRST:
        return False
    return first in ("i", "i've", "ive", "i'll", "ill", "stand", "take", "knock", "all", "give", "finish") or \
        match_word(first, VERBS) is not None or len(candidates(first, VERBS)) > 1 or bool(STOP_FIRE.match(piece) or STOP_ALL.match(piece))


def split_orders(text: str) -> list[str]:
    """The separate orders in a line, where each after the first plainly starts a new one; else the line."""
    low = text.strip()
    if not low or _SPOKEN.match(low.lower()) or is_strike(low):
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


__all__ = ["STOP_ALL", "STOP_FIRE", "STRIKE_REWRITES", "ally_words", "fleet_order", "is_strike", "plain_order", "split_orders"]
