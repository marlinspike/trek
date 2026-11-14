"""Playing a voice Piper made, through the game's own sound (the speech engine itself never touches pygame)."""

from __future__ import annotations

import io
import threading
import time

import pygame

_playing: list[pygame.mixer.Channel] = []
_lock = threading.Lock()


def play_wav(data: bytes, volume: float) -> None:
    """Play a WAV at `volume` (0 to 1) and return when it has finished or been stopped."""
    if not pygame.mixer.get_init():
        return
    try:
        snd = pygame.mixer.Sound(file=io.BytesIO(data))
    except pygame.error:
        return
    snd.set_volume(max(0.0, min(1.0, volume)))
    ch = snd.play()
    if ch is None:
        return
    with _lock:
        _playing.append(ch)
    try:
        while ch.get_busy() and ch.get_sound() is snd:
            time.sleep(0.03)
    finally:
        with _lock:
            if ch in _playing:
                _playing.remove(ch)


def stop_wav() -> None:
    with _lock:
        for ch in _playing:
            ch.stop()


__all__ = ["play_wav", "stop_wav"]
