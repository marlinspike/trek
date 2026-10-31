"""What the captain's words mean to the bridge: the patterns that recognise orders, handovers, praise and questions."""

from __future__ import annotations

import re

from ..console.vocab import VERBS

PRAISE = re.compile(r"\b(thanks?|thank you|well done|good (job|work|shooting)|nice|great|excellent|bravo)\b")

RUDE = re.compile(r"\b(stupid|idiot|useless|incompetent|shut up|moron|fool)\b")

GREET = re.compile(r"^(hello|hi|hey|greetings|report in)\b")

TAKE = re.compile(r"\b(take over|take (the |your )?(helm|station|tactical|weapons|engineering|science|sensors)"
                   r"|you have the (helm|station)|your station|take charge|you'?re in charge|handle it)\b")

# the whole bridge, not one station [E]
BRIDGE_TAKE = re.compile(r"\b(take (the )?(bridge|conn|ship)|you have the (bridge|conn|ship)|take command|"
                          r"you'?re in command|you have command|command the ship|fight the ship)\b")

BRIDGE_RELEASE = re.compile(r"\b(i have the (bridge|conn|ship)|i'?ll take (the bridge|the conn|command)|"
                             r"i'?m taking (the bridge|the conn|command)|i have command|i relieve you|"
                             r"(the )?captain'?s? on the bridge|give me (the bridge|the conn|command))\b")

# "spock, I have the helm" / "I relieve you": the officer's station comes back to the captain, nothing else stops [E]
HAVE_STATION = r"(helm|nav|navigation|steering|weapons|tactical|fire|phasers|torps|torpedoes|guns|station|science|sensors|engineering|shields)"

RELEASE = re.compile(r"\b(i(?: have|'ve got| got) (the )?" + HAVE_STATION + r"|"
                      r"i have it( from here)?|i relieve you|i'?ll (take|handle) it from here|"
                      r"i'?ll take (the )?" + HAVE_STATION + r")\b")

# "seven, cease fire" / "hold fire" / "stop firing": every weapon stops and the objectives end [E]
CEASE = re.compile(r"\b(cease ?fire|hold (your )?fire|stop (firing|shooting)|weapons (cold|hold))\b")

# "spock, stop" / "stand down" / "belay that" / "stop disabling their shields" / "forget the shields": all that, and
# the officer stops whatever they are doing: their station (and the bridge, if they have it) come back to the captain [E]
STAND_DOWN = re.compile(r"\b(stand down|belay|cancel (that|it|this|your|the)|abort|break (it )?off|call (it )?off|"
                         r"knock it off|never ?mind|stop (the attack|that|it|this|everything|now|there)|"
                         r"(stop|quit|cease) \w+ing|forget (it|that|the|about)|leave (it|them|her|him) alone|"
                         r"that'?s enough|(don'?t|do not) (?!stop\b))\b|^\s*(stop|halt|enough)\W*$")

# "mr worf, ...", "lieutenant worf, ..."
HONORIFIC_WORDS = r"(?:(?:mister|mr|ms|miss|lieutenant|lt|commander|cmdr|ensign|chief|doctor|dr)\.?\s+)?"

HONORIFIC = re.compile(r"^\s*" + HONORIFIC_WORDS, re.I)

WEAPONS_STATE = re.compile(r"^\s*weapons\s+(?:cold|hold|tight|safe|free|(?:is|are) mine)\b", re.I)

# "can you target their shields?", "please take out their engines", "I want you to cease fire"
POLITE = re.compile(r"^(?:(?:please|can you|could you|would you|will you|go ahead and|i want you to|i need you to|"
                     r"i'?d like you to|now)\s+)+|\s+(?:please|now|immediately|at once)\W*$")

SOFT_ORDER = re.compile(r"^(?:(?:i want|i need|we need|i'?d like)\s+(?:their|her|its|his)\b.*\b(?:down|out|gone|offline)\b|(?:hit|shoot(?: at)?|go after|bring down|take down|knock down|get|blast|pound|hammer|"
                         r"fire (?:at|on))\s+.*\b(?:their|her|its|his)\b|finish\b|take\s+\S.*\s+out\W*$)")

# "disable the Klingons' shields", "knock out Gorkon's torpedoes", "cancel that objective"
DISABLE_ORDER = re.compile(r"\b(disable|disarm|cripple|knock out|take out|neutrali[sz]e|shut down|destroy|eliminate|"
                      r"finish off|kill|sink|blow up)\b")

# "worf, target their shields", "focus fire on their engines", "target all their torps", "target their hull" [E]
TARGET_ORDER = re.compile(r"^\s*(?:target|focus (?:your )?(?:fire )?on|aim (?:at|for))\s+(.+?)\W*$")

# "worf, capture the Votek" / "seize her" / "take her intact" / "take her as a prize"
CAPTURE = re.compile(r"\b(capture|seize|take (her|it|them|the [\w'-]+) (intact|alive|as (a )?prize))\b")

KILL_VERBS = ("take out", "destroy", "eliminate", "finish off", "kill", "sink", "blow up", "knock out")

FIRING = re.compile(r"^\s*(fire\b|tachyon\s+\S)")  # an order to fire the round, not to design one

# "spock, manage repairs" / "repairs are yours"; "I'll handle repairs" takes them back [E]
REPAIRS_TAKE = re.compile(r"\b(manage|handle|run|direct|see to|take (care of|over)|look after|oversee|in charge of|"
                           r"prioriti[sz]e)\b[^.]*\brepairs?\b|\brepairs? (are|is) (yours|up to you)\b")

REPAIRS_RELEASE = re.compile(r"\b(i'?ll|i will|let me) (manage|handle|direct|run|do) (the )?repairs?\b|"
                              r"\brepairs? (are|is) mine\b|\b(stop|quit) (managing|directing) (the )?repairs?\b")

STATUS = re.compile(r"\b(status|report|sitrep|situation|how are|how's|condition)\b")

ADVICE = re.compile(r"\b(advice|advise|recommend|suggest|what (should|do you|now|next)|ideas?|options?|thoughts?|opinion)\b")

# "everyone stop", "all hands, stand down", "officers, belay that", "bridge, knock it off": the whole bridge stands down [E]
WHOLE_BRIDGE = re.compile(r"^\s*(all (stations|hands|officers|of you)|every ?(one|body)|officers|bridge( crew)?|"
                           r"crew|people|you all|y'?all)\W*(,\s*)?(please )?(stop|stand down|belay( that)?|"
                           r"knock it off|cease fire|hold fire|that'?s enough|enough)\b.*$|"
                           r"^\s*(stop|belay) (everyone|everybody|everything|all)\W*$")

def whole_bridge_stand_down(text: str) -> bool:
    """The captain tells every officer at once to stop what they are doing."""
    return WHOLE_BRIDGE.match(text.lower()) is not None

def could_be_officer(word: str) -> bool:
    """A lone first word names an officer only if it can't also be a console command ('sc' is scan, not a name starting sc)."""
    if len(word) < 3:
        return False
    return not any(sp.startswith(word) for spellings in VERBS.values() for sp in spellings)

def is_question(low: str) -> bool:
    """Asking for advice or information, rather than giving an order."""
    low = low.strip()
    return low.endswith("?") or bool(ADVICE.search(low)) or bool(re.match(
        r"(what|why|how|which|where|when|who|should|can|could|would|is|are|do|does|did)\b", low))


__all__ = ["ADVICE", "BRIDGE_RELEASE", "BRIDGE_TAKE", "CAPTURE", "CEASE", "DISABLE_ORDER", "FIRING", "GREET", "HAVE_STATION", "HONORIFIC", "HONORIFIC_WORDS", "KILL_VERBS", "POLITE", "PRAISE", "RELEASE", "REPAIRS_RELEASE", "REPAIRS_TAKE", "RUDE", "SOFT_ORDER", "STAND_DOWN", "STATUS", "TAKE", "TARGET_ORDER", "WEAPONS_STATE", "WHOLE_BRIDGE", "could_be_officer", "is_question", "whole_bridge_stand_down"]
