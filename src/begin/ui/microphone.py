"""The microphone: push to talk, a level meter while it listens, and the recording as a WAV [E].

Uses SDL's capture device through pygame-ce, so no extra package is needed. The recording is 16 kHz mono
16-bit, which is what every speech engine here wants. The first time, the operating system asks the captain
whether Begin (or the terminal running it) may use the microphone.
"""

from __future__ import annotations

import array
import io
import math
import threading
import wave
from typing import Any

RATE = 16000
MAX_SECONDS = 15.0          # a held key never records more than this
MIN_SECONDS = 0.35          # shorter than this was a slip of the finger


def to_wav(pcm: bytes, rate: int = RATE) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(pcm)
    return buf.getvalue()


def level(pcm: bytes) -> float:
    """0..1 loudness of a chunk, for the meter."""
    if len(pcm) < 2:
        return 0.0
    a = array.array("h")
    a.frombytes(pcm[: len(pcm) // 2 * 2])
    rms = math.sqrt(sum(x * x for x in a[::4]) / max(1, len(a[::4])))
    return min(1.0, rms / 6000.0)


class Recorder:
    """Opens the capture device on `start()`, keeps what it hears until `stop()` returns it as a WAV."""

    def __init__(self) -> None:
        self._dev: Any = None
        self._chunks: list[bytes] = []
        self._lock = threading.Lock()
        self.level = 0.0
        self.error: str | None = None

    @property
    def listening(self) -> bool:
        return self._dev is not None

    def seconds(self) -> float:
        with self._lock:
            return sum(len(c) for c in self._chunks) / 2 / RATE

    def _hear(self, _dev: object, mem: memoryview) -> None:
        data = bytes(mem)
        with self._lock:
            if sum(len(c) for c in self._chunks) / 2 / RATE < MAX_SECONDS:
                self._chunks.append(data)
        self.level = 0.7 * self.level + 0.3 * level(data)

    def start(self) -> bool:
        if self._dev is not None:
            return True
        self._chunks = []
        self.error = None
        try:
            from pygame._sdl2.audio import AUDIO_S16, AudioDevice, get_audio_device_names

            names = get_audio_device_names(True)
            if not names:
                self.error = "No microphone found."
                return False
            self._dev = AudioDevice(devicename=names[0], iscapture=True, frequency=RATE, audioformat=AUDIO_S16,
                                    numchannels=1, chunksize=512, allowed_changes=0, callback=self._hear)
            self._dev.pause(0)
        except Exception as e:  # noqa: BLE001 - no microphone must never stop a battle
            self._dev = None
            self.error = f"Couldn't open the microphone: {e}"
            return False
        return True

    def stop(self) -> bytes | None:
        """The recording as a WAV, or None if it was too short to be an order."""
        dev, self._dev = self._dev, None
        if dev is not None:
            try:
                dev.pause(1)
                dev.close()
            except Exception:  # noqa: BLE001
                pass
        with self._lock:
            pcm = b"".join(self._chunks)
            self._chunks = []
        self.level = 0.0
        if len(pcm) / 2 / RATE < MIN_SECONDS:
            return None
        return to_wav(pcm)


__all__ = ["MAX_SECONDS", "MIN_SECONDS", "RATE", "Recorder", "level", "to_wav"]
