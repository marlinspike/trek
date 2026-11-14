"""The speech engines: the computer's own voices, or Piper's [E].

- `MacSay`: macOS's speech synthesizer through `say` (the same system voices AVSpeechSynthesizer uses; add more
  in System Settings, Accessibility, Spoken Content, System voice, Manage Voices).
- `WindowsSapi`: Windows' SAPI voices (System.Speech) through one PowerShell process kept open for the battle.
- `Espeak`: eSpeak NG (or eSpeak) on Linux, or `spd-say` if that is all there is.
- `Piper`: Piper's neural voices, when the `piper` program and a voice (`.onnx` with its `.onnx.json`) are in
  config/speech/piper/. Clearer and more natural than most system voices; the game plays what it makes.
- `Silent`: nothing to speak with. The game says so in Settings and carries on with subtitles.

Every engine speaks one line at a time and blocks until it is done (it runs on the speaker's own thread), and can be
stopped part way. None of them touch pygame: the Piper engine hands its WAV to a player the screen provides.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Protocol
from xml.sax.saxutils import escape

from ..paths import config_dir
from .casting import VoiceInfo

BASE_WPM = 185.0          # words a minute at rate 1 (`say` and eSpeak)
_POPEN_KW: dict[str, object] = {"creationflags": 0x08000000} if sys.platform == "win32" else {}   # no console window


@dataclass(frozen=True, slots=True)
class Spoken:
    """One line to speak, as the speaker has cast it."""
    text: str
    voice: str | None
    rate: float = 1.0
    pitch: float = 1.0
    volume: float = 0.8


class Engine(Protocol):
    kind: str             # "mac", "windows", "espeak", "piper", "none": which of a cast's voices to look for
    title: str

    def problem(self) -> str | None:
        """Why it can't speak, or None when it can."""

    def voices(self) -> list[VoiceInfo]: ...

    def speak(self, line: Spoken) -> None:
        """Say a line; returns when it is done or stopped."""

    def stop(self) -> None: ...

    def close(self) -> None: ...


class _Process:
    """A speaking child process that can be stopped from another thread."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen[bytes] | None = None
        self._lock = threading.Lock()

    def run(self, args: list[str], stdin: bytes | None = None) -> None:
        try:
            with self._lock:
                self._proc = subprocess.Popen(args, stdin=subprocess.PIPE if stdin is not None else subprocess.DEVNULL,
                                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **_POPEN_KW)  # type: ignore[call-overload]
            p = self._proc
            if stdin is not None and p.stdin is not None:
                try:
                    p.stdin.write(stdin)
                    p.stdin.close()
                except OSError:
                    pass
            p.wait(timeout=60)
        except (OSError, subprocess.SubprocessError):
            pass
        finally:
            with self._lock:
                self._proc = None

    def stop(self) -> None:
        with self._lock:
            if self._proc is not None and self._proc.poll() is None:
                self._proc.terminate()


def _list(args: list[str]) -> str:
    try:
        return subprocess.run(args, capture_output=True, text=True, timeout=8, **_POPEN_KW).stdout  # type: ignore[call-overload,no-any-return]
    except (OSError, subprocess.SubprocessError):
        return ""


# ------------------------------------------------------------------ macOS

_SAY_LINE = re.compile(r"^(.+?)\s+([a-z]{2,3}[_-][A-Za-z0-9]{2,4})\s+#")


def parse_say_voices(out: str) -> list[VoiceInfo]:
    """`say -v ?`: "Daniel              en_GB    # Hello! My name is Daniel." per line."""
    found = []
    for line in out.splitlines():
        m = _SAY_LINE.match(line)
        if m:
            found.append(VoiceInfo(m.group(1).strip(), m.group(2)))
    return found


@dataclass
class MacSay:
    kind: str = "mac"
    title: str = "macOS voices"
    program: str = "say"
    _voices: list[VoiceInfo] | None = None
    _proc: _Process = field(default_factory=_Process)

    def problem(self) -> str | None:
        return None if shutil.which(self.program) else "macOS's say command wasn't found"

    def voices(self) -> list[VoiceInfo]:
        if self._voices is None:
            self._voices = parse_say_voices(_list([self.program, "-v", "?"]))
        return self._voices

    def speak(self, line: Spoken) -> None:
        # embedded commands set the loudness and the pitch (the voices that honour them do; the rest keep their own)
        pbas = round(48 * line.pitch)
        text = f"[[volm {line.volume:.2f}]] [[pbas {pbas}]] {line.text}"
        args = [self.program, "-r", str(round(BASE_WPM * line.rate))]
        if line.voice:
            args += ["-v", line.voice]
        self._proc.run(args + [text])

    def stop(self) -> None:
        self._proc.stop()

    def close(self) -> None:
        self.stop()


# ------------------------------------------------------------------ Windows

SAPI_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'
Add-Type -AssemblyName System.Speech
$s = New-Object System.Speech.Synthesis.SpeechSynthesizer
[Console]::Out.WriteLine('ready'); [Console]::Out.Flush()
while (($l = [Console]::In.ReadLine()) -ne $null) {
  if ($l -eq 'voices') {
    foreach ($v in $s.GetInstalledVoices()) { if ($v.Enabled) { $i = $v.VoiceInfo
      [Console]::Out.WriteLine("$($i.Name)|$($i.Culture.Name)|$($i.Gender)") } }
    [Console]::Out.WriteLine('.'); [Console]::Out.Flush(); continue
  }
  $j = $l | ConvertFrom-Json
  if ($j.voice) { try { $s.SelectVoice($j.voice) } catch {} }
  $s.Rate = [int]$j.rate; $s.Volume = [int]$j.volume
  try { $s.SpeakSsml($j.ssml) } catch { $s.Speak($j.text) }
  [Console]::Out.WriteLine('done'); [Console]::Out.Flush()
}
"""


def sapi_rate(rate: float) -> int:
    """SAPI's -10..10 pace from a multiplier (each step is about 10% at the middle of the scale)."""
    return max(-10, min(10, round((rate - 1.0) * 10)))


def sapi_ssml(text: str, pitch: float, lang: str = "en-US") -> str:
    pct = round((pitch - 1.0) * 100)
    return (f'<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="{lang}">'
            f'<prosody pitch="{pct:+d}%">{escape(text)}</prosody></speak>')


@dataclass
class WindowsSapi:
    kind: str = "windows"
    title: str = "Windows voices"
    _proc: subprocess.Popen[str] | None = None
    _voices: list[VoiceInfo] | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock)

    def problem(self) -> str | None:
        return None if self._shell() else "PowerShell wasn't found"

    @staticmethod
    def _shell() -> str | None:
        return shutil.which("powershell") or shutil.which("pwsh")

    def _start(self) -> subprocess.Popen[str] | None:
        if self._proc is not None and self._proc.poll() is None:
            return self._proc
        shell = self._shell()
        if shell is None:
            return None
        try:
            self._proc = subprocess.Popen([shell, "-NoProfile", "-NonInteractive", "-Command", "-"],
                                          stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                          text=True, encoding="utf-8", **_POPEN_KW)  # type: ignore[call-overload]
            assert self._proc.stdin is not None and self._proc.stdout is not None
            self._proc.stdin.write(SAPI_SCRIPT.replace("\n", "\r\n") + "\r\n")
            self._proc.stdin.flush()
            while (ln := self._proc.stdout.readline()) and ln.strip() != "ready":
                pass
        except (OSError, AssertionError):
            self._proc = None
        return self._proc

    def voices(self) -> list[VoiceInfo]:
        if self._voices is None:
            self._voices = []
            with self._lock:
                p = self._start()
                if p is not None and p.stdin is not None and p.stdout is not None:
                    try:
                        p.stdin.write("voices\n")
                        p.stdin.flush()
                        while (ln := p.stdout.readline().strip()) not in (".", ""):
                            name, _, rest = ln.partition("|")
                            lang, _, gender = rest.partition("|")
                            self._voices.append(VoiceInfo(name, lang, gender.lower() == "female"))
                    except OSError:
                        pass
        return self._voices

    def speak(self, line: Spoken) -> None:
        with self._lock:
            p = self._start()
        if p is None or p.stdin is None or p.stdout is None:
            return
        msg = {"voice": line.voice or "", "rate": sapi_rate(line.rate), "volume": round(line.volume * 100),
               "ssml": sapi_ssml(line.text, line.pitch), "text": line.text}
        try:
            p.stdin.write(json.dumps(msg) + "\n")
            p.stdin.flush()
            while (ln := p.stdout.readline()) and ln.strip() != "done":
                pass
        except (OSError, ValueError):
            pass

    def stop(self) -> None:
        # SAPI can't be interrupted from outside a blocking Speak: end the process; the next line starts another
        with self._lock:
            if self._proc is not None:
                try:
                    self._proc.kill()
                except OSError:
                    pass
                self._proc = None

    def close(self) -> None:
        self.stop()


# ------------------------------------------------------------------ Linux

ESPEAK_VOICES = ("en-us", "en-gb", "en-gb-scotland", "en-us+f1", "en-us+f2", "en-us+f3", "en-us+f4", "en-us+m1",
                 "en-us+m2", "en-us+m3", "en-us+m4", "en-us+m5", "en-us+m6", "en-us+m7", "en-gb+m2", "en-gb+m3")


@dataclass
class Espeak:
    kind: str = "espeak"
    title: str = "eSpeak NG"
    _proc: _Process = field(default_factory=_Process)

    @staticmethod
    def program() -> str | None:
        return shutil.which("espeak-ng") or shutil.which("espeak")

    def problem(self) -> str | None:
        if self.program() or shutil.which("spd-say"):
            return None
        return "no speech engine found: install espeak-ng (or set up Piper)"

    def voices(self) -> list[VoiceInfo]:
        return [VoiceInfo(v, "en") for v in ESPEAK_VOICES]

    def speak(self, line: Spoken) -> None:
        prog = self.program()
        if prog is None:
            spd = shutil.which("spd-say")
            if spd:
                self._proc.run([spd, "-w", "-r", str(round((line.rate - 1) * 100)), "-p", str(round((line.pitch - 1) * 100)),
                                "-i", str(round(line.volume * 200 - 100)), line.text])
            return
        args = [prog, "-s", str(round(BASE_WPM * line.rate)), "-p", str(max(0, min(99, round(50 * line.pitch)))),
                "-a", str(round(line.volume * 150))]
        if line.voice:
            args += ["-v", line.voice]
        self._proc.run(args + ["--", line.text])

    def stop(self) -> None:
        self._proc.stop()

    def close(self) -> None:
        self.stop()


# ------------------------------------------------------------------ Piper

def piper_dir() -> Path:
    return config_dir() / "speech" / "piper"


@dataclass
class Piper:
    """Piper's neural voices: `piper` on the PATH (or in config/speech/piper/) and its voices beside it."""
    play: Callable[[bytes, float], None] | None = None     # the screen's player: (WAV bytes, volume); blocks
    stop_play: Callable[[], None] | None = None
    kind: str = "piper"
    title: str = "Piper voices"
    _proc: _Process = field(default_factory=_Process)
    _stopped: bool = False

    @staticmethod
    def program() -> str | None:
        here = piper_dir() / ("piper.exe" if sys.platform == "win32" else "piper")
        return str(here) if here.is_file() else shutil.which("piper")

    def problem(self) -> str | None:
        if self.program() is None:
            return "Piper isn't installed (pip install piper-tts, or put piper in config/speech/piper/)"
        if not self.voices():
            return "no Piper voices in config/speech/piper/ (each is an .onnx file and its .onnx.json)"
        if self.play is None:
            return "no sound device to play Piper's voices"
        return None

    def voices(self) -> list[VoiceInfo]:
        d = piper_dir()
        if not d.is_dir():
            return []
        out = []
        for f in sorted(d.glob("*.onnx")):
            if f.with_suffix(".onnx.json").is_file():
                lang = f.stem.split("-")[0]           # en_GB-alan-medium
                out.append(VoiceInfo(f.stem, lang))
        return out

    def speak(self, line: Spoken) -> None:
        prog = self.program()
        voices = self.voices()
        if prog is None or not voices or self.play is None:
            return
        name = line.voice if any(v.name == line.voice for v in voices) else voices[0].name
        self._stopped = False
        with tempfile.TemporaryDirectory() as tmp:
            wav = Path(tmp) / "line.wav"
            self._proc.run([prog, "--model", str(piper_dir() / f"{name}.onnx"), "--output_file", str(wav),
                            "--length_scale", f"{1.0 / max(0.5, line.rate):.2f}"], (line.text + "\n").encode())
            if self._stopped or not wav.is_file():
                return
            self.play(wav.read_bytes(), line.volume)

    def stop(self) -> None:
        self._stopped = True
        self._proc.stop()
        if self.stop_play is not None:
            self.stop_play()

    def close(self) -> None:
        self.stop()


@dataclass
class Silent:
    reason: str = "speech is off"
    kind: str = "none"
    title: str = "No voices"

    def problem(self) -> str | None:
        return self.reason

    def voices(self) -> list[VoiceInfo]:
        return []

    def speak(self, line: Spoken) -> None:
        return None

    def stop(self) -> None:
        return None

    def close(self) -> None:
        return None


def system_engine(platform: str = sys.platform) -> Engine:
    if platform == "darwin":
        return MacSay()
    if platform == "win32":
        return WindowsSapi()
    return Espeak()


def make_engine(choice: str, play: Callable[[bytes, float], None] | None = None,
                stop_play: Callable[[], None] | None = None) -> Engine:
    """The engine for the "engine" setting: auto (Piper if it is ready, else the system's), system, piper or off."""
    if choice == "off" or os.environ.get("BEGIN_SPEECH") == "off":
        return Silent()
    if choice in ("auto", "piper"):
        p = Piper(play, stop_play)
        if p.problem() is None or choice == "piper":
            return p
    return system_engine()


__all__ = ["BASE_WPM", "Engine", "Espeak", "MacSay", "Piper", "Silent", "Spoken", "WindowsSapi", "make_engine",
           "parse_say_voices", "piper_dir", "sapi_rate", "sapi_ssml", "system_engine"]
