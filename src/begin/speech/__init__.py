"""Officers' voices: the bridge speaks aloud through the computer's own speech engine (or Piper's) [E].

No pygame here: the screen hands lines to a `Speaker` and, for Piper, plays the sound it is given."""

from .casting import CAST, OFFICERS, RACES, Cast, VoiceInfo, cast_voice, choices, part_for
from .engines import Engine, Spoken, make_engine
from .settings import SPEAK, SPEAK_TITLES, SpeechSettings
from .speaker import SAMPLES, Speaker, speakable

__all__ = ["CAST", "OFFICERS", "RACES", "SAMPLES", "SPEAK", "SPEAK_TITLES", "Cast", "Engine", "Speaker",
           "SpeechSettings", "Spoken", "VoiceInfo", "cast_voice", "choices", "make_engine", "part_for", "speakable"]
