"""Spoken officers' settings, kept in config/settings.json under "speech" [E].

On by default: the officers speak their readbacks, reports and proposals aloud through the computer's own speech
engine (the voices the Mac, Windows or Linux already has), each officer with a voice cast to suit them. Everything
here is also in Settings (S on the main menu, Speech) and in battle (Esc, then Bridge voices, or `speak`).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields

ENGINES = ("auto", "system", "piper", "off")
SPEAK = ("all", "orders", "urgent")     # every line said aloud · readbacks, proposals and warnings · warnings only
SPEAK_TITLES = {"all": "Everything", "orders": "Orders and warnings", "urgent": "Warnings only"}
RATE_MIN, RATE_MAX = 0.7, 1.4


@dataclass
class SpeechSettings:
    enabled: bool = True
    volume: float = 0.8                  # 0 to 1
    rate: float = 1.0                    # × each officer's own pace
    speak: str = "all"                   # see SPEAK
    engine: str = "auto"                 # auto: Piper if it is set up, else the system's voices
    captains: bool = True                # enemy captains speak their hails too
    cast: dict[str, str] = field(default_factory=dict)   # officer (or "computer", a race) -> a voice the player chose

    @staticmethod
    def from_dict(d: dict[str, object] | None) -> SpeechSettings:
        s = SpeechSettings()
        if not d:
            return s
        for f in fields(SpeechSettings):
            if f.name not in d:
                continue
            v = d[f.name]
            if f.name in ("volume", "rate") and isinstance(v, (int, float)) and not isinstance(v, bool):
                setattr(s, f.name, float(v))
            elif f.name == "cast" and isinstance(v, dict):
                s.cast = {str(k): str(x) for k, x in v.items() if x}
            elif isinstance(v, type(getattr(s, f.name))):
                setattr(s, f.name, v)
        s.volume = max(0.0, min(1.0, s.volume))
        s.rate = max(RATE_MIN, min(RATE_MAX, s.rate))
        if s.speak not in SPEAK:
            s.speak = "all"
        if s.engine not in ENGINES:
            s.engine = "auto"
        return s

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def wants(self, kind: str, urgent: bool) -> bool:
        """Whether a line of this kind ("readback", "proposal", "report", "chatter", "hail") is spoken."""
        if not self.enabled or self.engine == "off":
            return False
        if kind == "hail":                # an enemy captain: never when the captains are silenced
            return self.captains and (self.speak != "urgent" or urgent)
        if self.speak == "urgent":
            return urgent
        if self.speak == "orders":
            return urgent or kind in ("readback", "proposal")
        return True


__all__ = ["ENGINES", "RATE_MAX", "RATE_MIN", "SPEAK", "SPEAK_TITLES", "SpeechSettings"]
