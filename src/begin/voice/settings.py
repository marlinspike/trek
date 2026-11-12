"""Voice settings, kept in config/settings.json under "voice" [E]."""

from __future__ import annotations

import sys
from dataclasses import asdict, dataclass, fields

ENGINES = ("mac", "whisper-local", "whisper-server", "cloud")
ENGINE_WORDS = {"mac": "mac", "apple": "mac", "macos": "mac", "local": "whisper-local", "whisper": "whisper-local",
                "whisper-local": "whisper-local", "server": "whisper-server", "lan": "whisper-server",
                "whisper-server": "whisper-server", "cloud": "cloud", "openai": "cloud", "online": "cloud"}
MODELS = ("tiny.en", "base.en", "small.en", "medium.en")
PTT_KEYS = ("right alt", "right ctrl", "right shift", "caps lock", "f13", "backslash")


@dataclass
class VoiceSettings:
    enabled: bool = True
    engine: str = "mac" if sys.platform == "darwin" else "whisper-server"
    key: str = "right alt"                                    # hold to talk (Option on a Mac)
    language: str = "en"
    server_url: str = "http://127.0.0.1:8080"                 # a whisper.cpp server (its /inference endpoint)
    cloud_url: str = "https://api.openai.com/v1/audio/transcriptions"
    cloud_model: str = "whisper-1"
    cloud_key_env: str = "OPENAI_API_KEY"                     # the key is read from this environment variable
    model: str = "base.en"                                    # whisper.cpp model for whisper-local
    whisper_cli: str = "whisper-cli"                          # the whisper.cpp program, if not on the PATH

    @staticmethod
    def from_dict(d: dict[str, object] | None) -> VoiceSettings:
        v = VoiceSettings()
        if not d:
            return v
        for f in fields(VoiceSettings):
            if f.name in d and isinstance(d[f.name], type(getattr(v, f.name))):
                setattr(v, f.name, d[f.name])
        if v.engine not in ENGINES:
            v.engine = VoiceSettings().engine
        return v

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


__all__ = ["ENGINES", "ENGINE_WORDS", "MODELS", "PTT_KEYS", "VoiceSettings"]
