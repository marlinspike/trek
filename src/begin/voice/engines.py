"""Speech engines: from a recording of the captain's words to text [E].

Four engines, one interface (`Engine.transcribe(wav, hints)`), chosen on the voice page or with
`voice engine mac|local|server|cloud`:

- mac: the Mac's own recogniser, on the Mac (no network). A small helper program
  (`mac_transcribe.swift`) is built into config/voice/ the first time, with the
  permission text macOS needs; Xcode's command line tools (`xcode-select --install`)
  provide the compiler. With pyobjc's Speech package installed it is used instead.
- whisper-local: whisper.cpp on this computer. Begin runs its `whisper-cli` program
  (Homebrew: `brew install whisper-cpp`) with a model kept in config/voice/models/,
  which the voice page can download.
- whisper-server: a whisper.cpp server (`whisper-server -m <model>`) on this computer or
  another on the network; Begin posts the recording to its /inference endpoint.
- cloud: an OpenAI-style /v1/audio/transcriptions service; the key is read from an
  environment variable (OPENAI_API_KEY by default), never stored.

Hints are the names on the battle's sensors and the bridge, so "Gr'oth" and "Worf" are heard as names.
Every engine only hears; understanding is the console's (and the language model's) job.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

from ..paths import config_dir
from .settings import VoiceSettings

MODEL_URL = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-{name}.bin"
TIMEOUT = 30.0
HELPER = "begin-transcribe"
INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleIdentifier</key><string>local.begin.transcribe</string>
<key>CFBundleName</key><string>Begin speech</string>
<key>NSSpeechRecognitionUsageDescription</key><string>Begin hears the orders you speak on the bridge.</string>
<key>NSMicrophoneUsageDescription</key><string>Begin hears the orders you speak on the bridge.</string>
</dict></plist>
"""


class VoiceError(Exception):
    """Why an engine couldn't hear: shown to the captain as it is."""


class Engine(Protocol):
    name: str

    def ready(self) -> str | None:
        """None when the engine can be used now, else what is missing (in words for the captain)."""
        ...

    def transcribe(self, wav: bytes, hints: list[str]) -> str: ...


def voice_dir() -> Path:
    return config_dir() / "voice"


def models_dir() -> Path:
    return voice_dir() / "models"


# ------------------------------------------------------------ HTTP


def multipart(fields: dict[str, str], wav: bytes, filename: str = "order.wav") -> tuple[bytes, str]:
    """A multipart/form-data body with the fields and the recording as `file`; returns (body, content type)."""
    boundary = f"begin-{uuid.uuid4().hex}"
    out = bytearray()
    for k, v in fields.items():
        out += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
    out += (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"{filename}\"\r\n"
            "Content-Type: audio/wav\r\n\r\n").encode()
    out += wav + b"\r\n" + f"--{boundary}--\r\n".encode()
    return bytes(out), f"multipart/form-data; boundary={boundary}"


def _post(url: str, body: bytes, ctype: str, headers: dict[str, str] | None = None) -> dict[str, object]:
    req = urllib.request.Request(url, data=body, method="POST", headers={"Content-Type": ctype, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r:     # noqa: S310 - the captain's own URL
            raw = r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:200]
        raise VoiceError(f"{url} answered {e.code}: {detail}") from e
    except (urllib.error.URLError, OSError) as e:
        raise VoiceError(f"Couldn't reach {url}: {getattr(e, 'reason', e)}") from e
    try:
        data = json.loads(raw)
    except ValueError:
        return {"text": raw}
    return data if isinstance(data, dict) else {"text": str(data)}


def clean(text: str) -> str:
    """Whisper's text as a console line: one line, no trailing full stop, no [BLANK_AUDIO]-style tags."""
    t = " ".join(text.replace("[BLANK_AUDIO]", " ").split())
    while t and t[-1] in ".!?":
        t = t[:-1]
    return t.strip()


# ------------------------------------------------------------ engines


@dataclass
class WhisperServer:
    url: str
    name: str = "whisper-server"

    def ready(self) -> str | None:
        return None if self.url.startswith(("http://", "https://")) else "Set the server's address: voice server <url>"

    def transcribe(self, wav: bytes, hints: list[str]) -> str:
        body, ctype = multipart({"temperature": "0.0", "response_format": "json"}, wav)
        data = _post(self.url.rstrip("/") + "/inference", body, ctype)
        return clean(str(data.get("text", "")))


@dataclass
class CloudWhisper:
    url: str
    model: str
    key_env: str
    language: str = "en"
    name: str = "cloud"

    def ready(self) -> str | None:
        return None if os.environ.get(self.key_env) else f"Set {self.key_env} in the environment before starting Begin"

    def transcribe(self, wav: bytes, hints: list[str]) -> str:
        key = os.environ.get(self.key_env, "")
        if not key:
            raise VoiceError(f"No key: set {self.key_env}.")
        fields = {"model": self.model, "language": self.language, "response_format": "json"}
        if hints:
            fields["prompt"] = "Starship bridge orders. Names: " + ", ".join(hints[:40])
        body, ctype = multipart(fields, wav)
        data = _post(self.url, body, ctype, {"Authorization": f"Bearer {key}"})
        return clean(str(data.get("text", "")))


@dataclass
class WhisperLocal:
    model: str
    program: str = "whisper-cli"
    language: str = "en"
    name: str = "whisper-local"

    def model_path(self) -> Path:
        return models_dir() / f"ggml-{self.model}.bin"

    def _program(self) -> str | None:
        p = Path(self.program)
        if p.is_file():
            return str(p)
        for name in (self.program, "whisper-cli", "whisper-cpp", "main"):
            found = shutil.which(name)
            if found:
                return found
        return None

    def ready(self) -> str | None:
        if not self.model_path().is_file():
            return f"Download the {self.model} model (voice download)"
        if self._program() is None:
            return "Install whisper.cpp (on a Mac: brew install whisper-cpp)"
        return None

    def transcribe(self, wav: bytes, hints: list[str]) -> str:
        prog = self._program()
        if prog is None or not self.model_path().is_file():
            raise VoiceError(self.ready() or "whisper.cpp isn't ready")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "order.wav"
            path.write_bytes(wav)
            cmd = [prog, "-m", str(self.model_path()), "-f", str(path), "-l", self.language, "-nt", "-np"]
            if hints:
                cmd += ["--prompt", "Starship bridge orders. Names: " + ", ".join(hints[:40])]
            try:
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise VoiceError(f"whisper.cpp failed: {e}") from e
        if out.returncode != 0:
            raise VoiceError(f"whisper.cpp failed: {out.stderr.strip()[-200:]}")
        return clean(out.stdout)


@dataclass
class MacSpeech:
    name: str = "mac"

    def helper(self) -> Path:
        return voice_dir() / HELPER

    def ready(self) -> str | None:
        if sys.platform != "darwin":
            return "Mac speech works on a Mac"
        if self.helper().is_file() or _pyobjc_speech() or shutil.which("swiftc"):
            return None
        return "Install Xcode's command line tools (xcode-select --install) or pip install pyobjc-framework-Speech"

    def build(self) -> None:
        """Compile the helper into config/voice/, with the Info.plist macOS needs to ask permission."""
        swiftc = shutil.which("swiftc")
        if swiftc is None:
            raise VoiceError("No Swift compiler: run xcode-select --install")
        src = Path(__file__).with_name("mac_transcribe.swift")
        voice_dir().mkdir(parents=True, exist_ok=True)
        plist = voice_dir() / "Info.plist"
        plist.write_text(INFO_PLIST, encoding="utf-8")
        cmd = [swiftc, "-O", "-o", str(self.helper()), str(src),
               "-Xlinker", "-sectcreate", "-Xlinker", "__TEXT", "-Xlinker", "__info_plist", "-Xlinker", str(plist)]
        out = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        if out.returncode != 0:
            raise VoiceError(f"Couldn't build the speech helper: {out.stderr.strip()[-300:]}")

    def transcribe(self, wav: bytes, hints: list[str]) -> str:
        if sys.platform != "darwin":
            raise VoiceError("Mac speech works on a Mac.")
        if not self.helper().is_file() and _pyobjc_speech():
            return _pyobjc_transcribe(wav, hints)
        if not self.helper().is_file():
            self.build()
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "order.wav"
            path.write_bytes(wav)
            try:
                out = subprocess.run([str(self.helper()), str(path), *hints[:40]], capture_output=True, text=True,
                                     timeout=TIMEOUT)
            except (OSError, subprocess.TimeoutExpired) as e:
                raise VoiceError(f"Mac speech failed: {e}") from e
        if out.returncode == 2:
            raise VoiceError("Allow Speech Recognition for Begin: System Settings > Privacy & Security.")
        if out.returncode not in (0, 1):
            raise VoiceError(out.stderr.strip()[-200:] or f"Mac speech failed ({out.returncode})")
        return clean(out.stdout)


def _pyobjc_speech() -> bool:
    try:
        import Speech  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False
    return True


def _pyobjc_transcribe(wav: bytes, hints: list[str]) -> str:   # pragma: no cover - macOS only
    import Foundation  # type: ignore[import-not-found]
    import Speech  # type: ignore[import-not-found]

    with tempfile.TemporaryDirectory() as d:
        path = Path(d) / "order.wav"
        path.write_bytes(wav)
        state: dict[str, object] = {}
        Speech.SFSpeechRecognizer.requestAuthorization_(lambda s: state.__setitem__("auth", s))
        _spin(lambda: "auth" in state, 60)
        if state.get("auth") != Speech.SFSpeechRecognizerAuthorizationStatusAuthorized:
            raise VoiceError("Allow Speech Recognition for Begin: System Settings > Privacy & Security.")
        rec = Speech.SFSpeechRecognizer.alloc().initWithLocale_(Foundation.NSLocale.localeWithLocaleIdentifier_("en-US"))
        req = Speech.SFSpeechURLRecognitionRequest.alloc().initWithURL_(Foundation.NSURL.fileURLWithPath_(str(path)))
        if rec.supportsOnDeviceRecognition():
            req.setRequiresOnDeviceRecognition_(True)
        req.setContextualStrings_(hints[:40])
        req.setShouldReportPartialResults_(False)

        def done(result: object, error: object) -> None:
            if result is not None and result.isFinal():  # type: ignore[attr-defined]
                state["text"] = str(result.bestTranscription().formattedString())  # type: ignore[attr-defined]
            elif error is not None:
                state["text"] = ""

        rec.recognitionTaskWithRequest_resultHandler_(req, done)
        _spin(lambda: "text" in state, TIMEOUT)
        return clean(str(state.get("text", "")))


def _spin(done: Callable[[], bool], seconds: float) -> None:   # pragma: no cover - macOS only
    import Foundation  # type: ignore[import-not-found]

    end = time.monotonic() + seconds
    while not done() and time.monotonic() < end:
        Foundation.NSRunLoop.mainRunLoop().runUntilDate_(Foundation.NSDate.dateWithTimeIntervalSinceNow_(0.02))


def make_engine(v: VoiceSettings) -> Engine:
    if v.engine == "mac":
        return MacSpeech()
    if v.engine == "whisper-local":
        return WhisperLocal(v.model, v.whisper_cli, v.language)
    if v.engine == "cloud":
        return CloudWhisper(v.cloud_url, v.cloud_model, v.cloud_key_env, v.language)
    return WhisperServer(v.server_url)


def download_model(name: str, progress: Callable[[float], None] | None = None) -> Path:
    """Fetch a whisper.cpp model into config/voice/models/ (a part file until it's complete)."""
    models_dir().mkdir(parents=True, exist_ok=True)
    dest = models_dir() / f"ggml-{name}.bin"
    part = dest.with_suffix(".part")
    req = urllib.request.Request(MODEL_URL.format(name=name), headers={"User-Agent": "begin-remake"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as r, part.open("wb") as f:   # noqa: S310
            total = int(r.headers.get("Content-Length") or 0)
            got = 0
            while True:
                chunk = r.read(1 << 16)
                if not chunk:
                    break
                f.write(chunk)
                got += len(chunk)
                if progress is not None and total:
                    progress(got / total)
    except (urllib.error.URLError, OSError) as e:
        part.unlink(missing_ok=True)
        raise VoiceError(f"Couldn't download the {name} model: {getattr(e, 'reason', e)}") from e
    part.replace(dest)
    return dest


__all__ = ["CloudWhisper", "Engine", "MacSpeech", "VoiceError", "WhisperLocal", "WhisperServer", "clean",
           "download_model", "make_engine", "models_dir", "multipart", "voice_dir"]
