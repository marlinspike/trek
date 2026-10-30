"""Synthesised sound: every effect is generated at start-up, no sound files [E].

Sounds follow what the player can see: a beam, a launch, a blast, a shield
taking a hit, a ship breaking up, a cloak engaging. Each is panned to where it
happened on the map and quieter the farther it is from the middle of the view.
They are kept soft and short, a little under the battle rather than over it,
and the same kind of sound never stacks more than a few deep.

Volume comes from `volume` in config/settings.json (0 to 1); M mutes. Without
an audio device (a server, the tests) everything here quietly does nothing.
"""

from __future__ import annotations

import array
import math
import random
from collections.abc import Callable

import pygame

from ..sim.events import Detonation, Event, PhaserFired, ShieldHit, TorpedoLaunched

RATE = 22050
MIN_GAP = {"phaser": 0.07, "pulse": 0.07, "launch": 0.09, "blast": 0.08, "fizzle": 0.08, "shield": 0.06,
           "breakup": 0.3, "cloak": 0.3, "alert": 2.0}
CHANNELS = 16


def _env(i: int, n: int, attack: float, release: float) -> float:
    """A simple attack-release envelope over n samples (attack and release as fractions)."""
    t = i / n
    if t < attack:
        return t / attack
    return max(0.0, 1.0 - (t - attack) / max(1e-6, 1.0 - attack)) ** (1.0 / max(1e-6, release))


def _render(seconds: float, sample: Callable[[int, int, random.Random], float], peak: float = 0.6,
            seed: int = 1) -> array.array:
    """Mono 16-bit samples from a function of (index, count, rng), scaled so the loudest is `peak` (no clipping)."""
    n = int(RATE * seconds)
    rng = random.Random(seed)
    raw = [sample(i, n, rng) for i in range(n)]
    top = max((abs(v) for v in raw), default=0.0) or 1.0
    k = peak * 32767 / top
    return array.array("h", (int(v * k) for v in raw))


def phaser() -> array.array:
    """A clean, falling tone with a little shimmer: a beam weapon."""
    def s(i: int, n: int, _: random.Random) -> float:
        t = i / RATE
        f = 1250 - 500 * (i / n)
        return (math.sin(math.tau * f * t) * 0.7 + math.sin(math.tau * f * 1.5 * t) * 0.2) * _env(i, n, 0.04, 1.8)
    return _render(0.32, s, 0.34)


def pulse() -> array.array:
    """Three quick buzzing bolts: a disruptor."""
    def s(i: int, n: int, _: random.Random) -> float:
        t = i / RATE
        bolt = (i * 3 // n)
        local = (i - bolt * n / 3) / (n / 3)
        tone = math.copysign(1.0, math.sin(math.tau * (520 - 60 * bolt) * t)) * 0.35 + math.sin(math.tau * 260 * t) * 0.4
        return tone * max(0.0, 1 - local) ** 2 * (1 - 0.25 * bolt)
    return _render(0.3, s, 0.3, seed=2)


def launch() -> array.array:
    """A soft low thump with a breath of air: a torpedo leaving its tube."""
    state = [0.0]

    def s(i: int, n: int, rng: random.Random) -> float:
        t = i / RATE
        f = 140 - 80 * (i / n)
        state[0] = state[0] * 0.92 + rng.uniform(-1, 1) * 0.08      # low-passed noise
        return (math.sin(math.tau * f * t) * 0.8 + state[0] * 1.6) * _env(i, n, 0.02, 1.4)
    return _render(0.4, s, 0.45, seed=3)


def blast(seconds: float = 0.9, depth: float = 0.97, seed: int = 4, peak: float = 0.55) -> array.array:
    """Rumbling noise that dies away: a warhead going off. Longer and deeper for a ship."""
    state = [0.0, 0.0]

    def s(i: int, n: int, rng: random.Random) -> float:
        state[0] = state[0] * depth + rng.uniform(-1, 1) * (1 - depth)
        state[1] = state[1] * depth + state[0] * (1 - depth)
        crack = rng.uniform(-1, 1) * max(0.0, 1 - i / (n * 0.04)) * 0.4
        return (state[0] * 9 + state[1] * 30 + crack) * _env(i, n, 0.01, 2.2)
    return _render(seconds, s, peak, seed=seed)


def fizzle() -> array.array:
    """A short dull pop: a round shot down."""
    state = [0.0]

    def s(i: int, n: int, rng: random.Random) -> float:
        state[0] = state[0] * 0.8 + rng.uniform(-1, 1) * 0.2
        return state[0] * 2.2 * _env(i, n, 0.01, 2.5)
    return _render(0.18, s, 0.28, seed=5)


def shield() -> array.array:
    """A bright, wavering ring: a shield turning a blow."""
    def s(i: int, n: int, _: random.Random) -> float:
        t = i / RATE
        wob = 1 + 0.02 * math.sin(math.tau * 30 * t)
        return (math.sin(math.tau * 880 * wob * t) * 0.5 + math.sin(math.tau * 1320 * wob * t) * 0.3) * _env(i, n, 0.02, 1.6)
    return _render(0.25, s, 0.22, seed=6)


def cloak() -> array.array:
    """A rising, airy sweep: a cloak engaging or dropping."""
    state = [0.0]

    def s(i: int, n: int, rng: random.Random) -> float:
        t = i / RATE
        state[0] = state[0] * 0.6 + rng.uniform(-1, 1) * 0.4
        f = 300 + 900 * (i / n)
        return (math.sin(math.tau * f * t) * 0.3 + state[0] * 0.25) * math.sin(math.pi * i / n)
    return _render(0.7, s, 0.26, seed=7)


def alert() -> array.array:
    """Two soft falling notes: the ship has gone to red alert."""
    def s(i: int, n: int, _: random.Random) -> float:
        t = i / RATE
        half = i < n // 2
        f = 660 if half else 495
        k = (i if half else i - n // 2) / (n / 2)
        return math.sin(math.tau * f * t) * max(0.0, 1 - k) ** 1.5 * min(1.0, k * 40)
    return _render(0.7, s, 0.3, seed=8)


SOUNDS: dict[str, Callable[[], array.array]] = {
    "phaser": phaser, "pulse": pulse, "launch": launch, "blast": blast, "fizzle": fizzle, "shield": shield,
    "breakup": lambda: blast(1.8, 0.985, seed=9, peak=0.75), "cloak": cloak, "alert": alert,
}


_made: dict[tuple[str, bool], bytes] = {}


def _samples(name: str, stereo: bool) -> bytes:
    """A sound's samples, made once per run (a fraction of a second each)."""
    key = (name, stereo)
    if key not in _made:
        mono = SOUNDS[name]()
        if stereo:
            both = array.array("h", bytes(4 * len(mono)))
            both[0::2] = mono
            both[1::2] = mono
            mono = both
        _made[key] = mono.tobytes()
    return _made[key]


class Audio:
    """The battle's sound. Does nothing at all when there is no audio device."""

    def __init__(self, volume: float = 0.6, muted: bool = False) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))
        self.muted = muted
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._last: dict[str, float] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 512)
            pygame.mixer.set_num_channels(CHANNELS)
            stereo = pygame.mixer.get_init()[2] == 2
            for name in SOUNDS:
                self.sounds[name] = pygame.mixer.Sound(buffer=_samples(name, stereo))
        except (pygame.error, OSError, TypeError):
            self.sounds = {}       # no device: a silent battle

    @property
    def available(self) -> bool:
        return bool(self.sounds)

    def toggle_mute(self) -> bool:
        self.muted = not self.muted
        if self.muted and self.available:
            pygame.mixer.stop()
        return self.muted

    def play(self, name: str, now: float, pan: float = 0.0, level: float = 1.0) -> None:
        """pan -1 (left) .. 1 (right); level 0..1 before the master volume."""
        snd = self.sounds.get(name)
        if snd is None or self.muted or self.volume <= 0 or level <= 0.02:
            return
        if now - self._last.get(name, -99.0) < MIN_GAP.get(name, 0.05):
            return
        ch = pygame.mixer.find_channel()
        if ch is None:
            return
        self._last[name] = now
        v = self.volume * level
        ch.set_volume(v * min(1.0, 1 - pan), v * min(1.0, 1 + pan))
        ch.play(snd)

    def events(self, events: list[Event], now: float, place: Callable[[float, float], tuple[float, float] | None],
               visible: set[int], styles: Callable[[int], str], where: Callable[[int], tuple[float, float] | None]) -> None:
        """Play what the player can see happen. `place` gives (pan, level) for a map point, None if far off."""
        if not self.available or self.muted:
            return
        for ev in events:
            spot: tuple[float, float] | None = None
            name = ""
            if isinstance(ev, PhaserFired) and ev.ship_id in visible:
                name, spot = ("pulse" if styles(ev.ship_id) == "pulse" else "phaser"), ev.origin
            elif isinstance(ev, TorpedoLaunched) and ev.ship_id in visible:
                name, spot = "launch", where(ev.ship_id)
            elif isinstance(ev, Detonation):
                name = "fizzle" if ev.cause == "intercepted" else "breakup" if ev.source in ("ship", "destruct") else "blast"
                spot = (ev.x, ev.y)
            elif isinstance(ev, ShieldHit) and ev.ship_id in visible:
                name, spot = "shield", where(ev.ship_id)
            if not name or spot is None:
                continue
            heard = place(*spot)
            if heard is not None:
                self.play(name, now, *heard)


__all__ = ["Audio", "SOUNDS"]
