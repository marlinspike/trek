"""Synthesised sound: every effect is generated at start-up from original synthesis [E].

Sounds follow what the player can see: a beam, a launch, a blast, a shield
taking a hit, a ship breaking up, a cloak engaging. Each is panned to where it
happened on the map and quieter the farther it is from the middle of the view.
They are kept soft and short, a little under the battle rather than over it,
and the same kind of sound never stacks more than a few deep.

Volume comes from `volume` in config/settings.json (0 to 1); M mutes. The phaser
and the torpedo launch come in four versions each (`sounds` in settings.json
picks one), and a WAV of the player's own in config/sounds/ replaces any sound. Without
an audio device (a server, the tests) everything here quietly does nothing.
"""

from __future__ import annotations

import array
import math
import random
import wave
from collections.abc import Callable
from pathlib import Path

import pygame

from ..sim.events import Detonation, Event, PhaserFired, ShieldHit, TorpedoLaunched

RATE = 22050
MIN_GAP = {"phaser": 0.12, "pulse": 0.07, "launch": 0.12, "blast": 0.08, "fizzle": 0.08, "shield": 0.06,
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


def _flange(x: list[float], rate: float = 0.9, lo: float = 0.0006, hi: float = 0.003, mix: float = 0.7,
            feedback: float = 0.35) -> list[float]:
    """A swept short delay mixed back in: the shimmering, jet-like comb that makes a beam sound alive."""
    buf = [0.0] * len(x)
    out = [0.0] * len(x)
    for i, v in enumerate(x):
        d = (lo + (hi - lo) * 0.5 * (1 - math.cos(math.tau * rate * i / RATE))) * RATE
        j = i - d
        k = int(j)
        late = 0.0
        if k >= 0:
            f = j - k
            late = buf[k] * (1 - f) + buf[min(k + 1, i)] * f
        buf[i] = v + feedback * late
        out[i] = v + mix * late
    return out


def _saw(phase: float, f: float, top: int = 0) -> float:
    """A band-limited sawtooth (harmonics only up to the Nyquist limit, so it doesn't alias into hiss)."""
    n = top or max(1, int(RATE / 2 / f))
    return sum(math.sin(k * phase) / k for k in range(1, n + 1))


def _square(phase: float, f: float) -> float:
    n = max(1, int(RATE / 2 / f))
    return sum(math.sin(k * phase) / k for k in range(1, n + 1, 2))


def _beam(tone: Callable[[float, random.Random], float], seconds: float = 0.7, peak: float = 0.32,
          seed: int = 1, flange: float = 0.9) -> array.array:
    """A held beam: steady pitch, a fast attack, held flat while it fires, and a quick cut-off."""
    n = int(RATE * seconds)
    rng = random.Random(seed)
    raw = []
    for i in range(n):
        t = i / RATE
        gate = min(1.0, t / 0.008) * min(1.0, (n - i) / (RATE * 0.025))
        raw.append(math.tanh(1.8 * tone(t, rng)) * gate)      # driven a little: harsh, and loud for its peak
    shimmer = _flange(raw, rate=flange)
    return _render(seconds, lambda i, _n, _r: shimmer[i], peak, seed)


def phaser_buzz() -> array.array:
    """A harsh square tone chopped seventy times a second: a hard electric buzz."""
    def tone(t: float, rng: random.Random) -> float:
        sq = _square(math.tau * 1250 * t, 1250)
        chop = 0.55 + 0.45 * math.copysign(1.0, math.sin(math.tau * 70 * t)) * min(1.0, abs(math.sin(math.tau * 70 * t)) * 6)
        return sq * chop + 0.4 * math.sin(math.tau * 625 * t) * chop + rng.uniform(-0.04, 0.04)
    return _beam(tone, seed=12, flange=1.3)


def _resonate(x: list[float], pitch: Callable[[float], float], g: float = 0.985, damp: float = 0.35) -> list[float]:
    """Feed a signal round a short, tuned delay loop: noise in, a ringing pitched tone out, like feedback."""
    y = [0.0] * len(x)
    for i, v in enumerate(x):
        d = RATE / pitch(i / RATE)
        j = i - d
        k = int(j)
        back = 0.0
        if k >= 1:
            f = j - k
            a = y[k] * (1 - f) + y[min(k + 1, i - 1)] * f
            back = (1 - damp) * a + damp * y[k - 1]       # a touch of damping in the loop: warm, not shrill
        y[i] = v + g * back
    return y


def _pink(rng: random.Random, n: int) -> list[float]:
    """Soft-edged noise (most of its energy low), the excitation for the rays."""
    b0 = b1 = b2 = 0.0
    out = []
    for _ in range(n):
        w = rng.uniform(-1, 1)
        b0 = 0.997 * b0 + 0.029 * w
        b1 = 0.985 * b1 + 0.032 * w
        b2 = 0.950 * b2 + 0.048 * w
        out.append(b0 + b1 + b2 + 0.05 * w)
    return out


def _highpass(x: list[float], f: float) -> list[float]:
    """A one-pole high-pass at f Hz."""
    k = 1 / (1 + math.tau * f / RATE)
    out = [0.0] * len(x)
    prev = y = 0.0
    for i, v in enumerate(x):
        y = k * (y + v - prev)
        prev = v
        out[i] = y
    return out


def _ray(pitches: tuple[float, ...], seconds: float = 0.9, seed: int = 31, wobble: float = 0.004,
         under: Callable[[], array.array] | None = None, peak: float = 0.34) -> array.array:
    """A ray: noise fed round tuned feedback loops so it sings at a steady pitch and sizzles, held, then cut."""
    n = int(RATE * seconds)
    rng = random.Random(seed)
    src = _highpass(_highpass(_pink(rng, n), 400), 400)      # nothing low to feed the loop: it sings, not booms
    mix = [0.0] * n
    for k, f0 in enumerate(pitches):
        rate = 5.5 + 1.3 * k
        def pitch(t: float, f0: float = f0, rate: float = rate) -> float:
            return f0 * (1 + wobble * math.sin(math.tau * rate * t))      # the faint waver of a live beam
        loop = _resonate(src, pitch)
        for i in range(n):
            mix[i] += loop[i]
    mix = _highpass(mix, 300)
    top = max(abs(v) for v in mix) or 1.0
    hp = prev = 0.0
    out = []
    bed = list(under()) if under is not None else []
    bed_top = max((abs(v) for v in bed), default=1) or 1
    for i in range(n):
        t = i / RATE
        v = math.tanh(2.2 * mix[i] / top)                    # driven: the edge of a beam cutting the air
        hp = 0.97 * (hp + v - prev)                          # take out the rumble, keep the sizzle
        prev = v
        gate = min(1.0, t / 0.01) * min(1.0, (n - i) / (RATE * 0.04))
        sizzle = rng.uniform(-1, 1) * 0.06 * (0.6 + 0.4 * math.sin(math.tau * 37 * t))
        bedv = 0.45 * bed[i] / bed_top if i < len(bed) else 0.0
        out.append((hp + sizzle + bedv) * gate)
    return _render(seconds, lambda i, _n, _r: out[i], peak, seed)


def phaser_a() -> array.array:
    """A singing ray: one tuned feedback loop, steady and piercing, with a fine sizzle."""
    return _ray((1180.0,), seed=31)


def phaser_b() -> array.array:
    """A brighter ray: two loops a hair apart, so it shimmers as it beats, higher and thinner."""
    return _ray((1480.0, 1491.0), seed=32, wobble=0.003)


def phaser_c() -> array.array:
    """The ray over the buzz you liked: the singing loop on top, version d's buzz underneath."""
    return _ray((990.0, 1485.0), seed=33, under=phaser_buzz)


def _comb_tail(x: list[float], wet: float = 0.5) -> list[float]:
    """A short, airy room: three feedback combs (29, 37 and 43 ms) blended under the dry sound."""
    out = list(x)
    for ms, fb in ((0.029, 0.6), (0.037, 0.57), (0.043, 0.54)):
        d = int(ms * RATE)
        y = [0.0] * len(x)
        for i, v in enumerate(x):
            y[i] = v + (fb * y[i - d] if i >= d else 0.0)
            out[i] += wet / 3 * (y[i] - v)
    return out


def _torpedo(seconds: float, thump: tuple[float, float, float], sweep: tuple[float, float, float],
             damp: float, seed: int, drop: tuple[float, float, float] | None = None, peak: float = 0.5) -> array.array:
    """A launch: a low thump, a noise whoosh through a resonant filter whose pitch falls away, and a short tail.

    thump = (start Hz, end Hz, decay), sweep = (start Hz, end Hz, seconds), drop = an optional falling tone like thump.
    """
    n = int(RATE * seconds)
    rng = random.Random(seed)
    low = band = hiss = 0.0
    ph = ph2 = 0.0
    raw = []
    for i in range(n):
        t = i / RATE
        f0 = thump[0] * (thump[1] / thump[0]) ** min(1.0, t / 0.25)
        ph += math.tau * f0 / RATE
        out = math.sin(ph) * math.exp(-t * thump[2]) * min(1.0, t / 0.003) * 1.4
        u = min(1.0, t / sweep[2])
        fc = sweep[0] * (sweep[1] / sweep[0]) ** u
        k = 2 * math.sin(math.pi * min(fc, RATE / 6) / RATE)
        hiss = 0.55 * hiss + 0.45 * rng.uniform(-1, 1)          # take the fizz off the noise: air, not static
        high = hiss * 1.6 - low - damp * band
        band += k * high
        low += k * band
        whoosh = min(1.0, t / 0.012) * math.exp(-t * 3.2) * (1.0 if t < sweep[2] else math.exp(-(t - sweep[2]) * 12))
        out += band * whoosh * 1.1
        if drop is not None:
            f2 = drop[0] * (drop[1] / drop[0]) ** min(1.0, t / 0.35)
            ph2 += math.tau * f2 / RATE
            out += (math.sin(ph2) + 0.3 * math.sin(2 * ph2)) * math.exp(-t * drop[2]) * min(1.0, t / 0.005) * 0.7
        raw.append(out)
    room = _comb_tail(raw)
    return _render(seconds, lambda i, _n, _r: room[i], peak, seed)


def launch_thoom() -> array.array:
    """"Thoom": a deep thump under a whoosh that falls from bright to dull."""
    return _torpedo(0.9, (90, 45, 9), (2500, 400, 0.45), 0.5, seed=21)


def _pulse(seconds: float, f0: float, f1: float, fall: float, seed: int, thoom: float = 0.0,
           charge: float = 0.0, peak: float = 0.5) -> array.array:
    """An energy pulse: a bright pitched burst that drops away fast (f0 to f1 over `fall` seconds), rung through a
    tuned loop so it sings, with a short room behind it. `thoom` lays the launch thump underneath; `charge`
    gives it a quick rising wind-up first."""
    n = int(RATE * seconds)
    rng = random.Random(seed)
    ph = 0.0
    burst = []
    pitch_at: list[float] = []
    for i in range(n):
        t = i / RATE
        if t < charge:
            f = f1 * (f0 / f1) ** (t / charge)              # winding up to the release
            amp = 0.35 * t / charge
        else:
            u = t - charge
            f = f0 * (f1 / f0) ** min(1.0, u / fall)
            amp = min(1.0, u / 0.003) * math.exp(-u * 7.5)
        pitch_at.append(f)
        ph += math.tau * f / RATE
        tone = _saw(ph, f) * 0.6 + math.sin(ph) * 0.6
        burst.append((math.tanh(1.6 * tone) + rng.uniform(-0.5, 0.5) * math.exp(-t * 30)) * amp)
    rung = _resonate([v * 0.2 for v in burst], lambda t: pitch_at[min(n - 1, int(t * RATE))], g=0.9, damp=0.4)
    top = max(abs(v) for v in rung) or 1.0
    btop = max(abs(v) for v in burst) or 1.0
    raw = [0.6 * burst[i] / btop + 0.7 * rung[i] / top for i in range(n)]
    if thoom:
        base = list(launch_thoom())
        bt = max(abs(v) for v in base) or 1
        for i in range(min(n, len(base))):
            raw[i] += thoom * base[i] / bt
    room = _comb_tail(raw, wet=0.6)
    return _render(seconds, lambda i, _n, _r: room[i], peak, seed)


def launch_a() -> array.array:
    """A pulse: a bright burst that drops from high to low in a quarter second and rings away."""
    return _pulse(0.75, 1900, 260, 0.25, seed=41)


def launch_b() -> array.array:
    """A heavier pulse: a quick wind-up, then the release, deeper, with the thump you liked under it."""
    return _pulse(0.85, 1400, 180, 0.3, seed=42, thoom=0.55, charge=0.07)


def launch_c() -> array.array:
    """A short, sharp pulse: higher and quicker, more of a crack."""
    return _pulse(0.6, 2600, 420, 0.16, seed=43)


VARIANTS: dict[str, dict[str, Callable[[], array.array]]] = {
    "phaser": {"a": phaser_a, "b": phaser_b, "c": phaser_c, "d": phaser_buzz},
    "launch": {"a": launch_a, "b": launch_b, "c": launch_c, "d": launch_thoom},
}
ALIASES = {"torpedo": "launch"}       # config/sounds/torpedo.wav is the launch sound


def phaser() -> array.array:
    return phaser_buzz()          # the captain's pick so far (version d)


def launch() -> array.array:
    return launch_thoom()         # the captain's pick so far (version d)


def pulse() -> array.array:
    """Three quick buzzing bolts: a disruptor."""
    def s(i: int, n: int, _: random.Random) -> float:
        t = i / RATE
        bolt = (i * 3 // n)
        local = (i - bolt * n / 3) / (n / 3)
        tone = math.copysign(1.0, math.sin(math.tau * (520 - 60 * bolt) * t)) * 0.35 + math.sin(math.tau * 260 * t) * 0.4
        return tone * max(0.0, 1 - local) ** 2 * (1 - 0.25 * bolt)
    return _render(0.3, s, 0.3, seed=2)


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


_made: dict[tuple[str, str, bool], bytes] = {}


def _samples(name: str, stereo: bool, variant: str = "") -> bytes:
    """A sound's samples, made once per run (a fraction of a second each). `variant` picks a, b or c where there are versions."""
    key = (name, variant, stereo)
    if key not in _made:
        make = VARIANTS.get(name, {}).get(variant, SOUNDS[name])
        mono = make()
        if stereo:
            both = array.array("h", bytes(4 * len(mono)))
            both[0::2] = mono
            both[1::2] = mono
            mono = both
        _made[key] = mono.tobytes()
    return _made[key]


def own_sounds(folder: Path | None) -> dict[str, Path]:
    """The player's own WAV files in config/sounds/, by sound name (torpedo.wav counts as the launch)."""
    out: dict[str, Path] = {}
    if folder is None or not folder.is_dir():
        return out
    for f in sorted(folder.iterdir()):
        if f.suffix.lower() in (".wav", ".ogg"):
            name = ALIASES.get(f.stem.lower(), f.stem.lower())
            if name in SOUNDS:
                out[name] = f
    return out


def write_wav(path: Path, samples: array.array) -> None:
    """Save mono 16-bit samples as a WAV file (to listen to the versions outside the game)."""
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(samples.tobytes())


class Audio:
    """The battle's sound. Does nothing at all when there is no audio device.

    `choice` picks a version of a sound that has several ({"phaser": "b"}); a WAV of the player's own in
    `folder` (config/sounds/phaser.wav, torpedo.wav, ...) replaces the made one outright.
    """

    def __init__(self, volume: float = 0.6, muted: bool = False, choice: dict[str, str] | None = None,
                 folder: Path | None = None) -> None:
        self.volume = max(0.0, min(1.0, float(volume)))
        self.muted = muted
        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._last: dict[str, float] = {}
        self.problems: list[str] = []
        picks = {ALIASES.get(k, k): str(v).strip().lower() for k, v in (choice or {}).items()}
        self.choice = {k: v for k, v in picks.items() if v in VARIANTS.get(k, {})}
        self._stereo = False
        self.own: dict[str, Path] = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(RATE, -16, 2, 512)
            pygame.mixer.set_num_channels(CHANNELS)
            self._stereo = stereo = pygame.mixer.get_init()[2] == 2
            for name in SOUNDS:
                self.sounds[name] = pygame.mixer.Sound(buffer=_samples(name, stereo, self.choice.get(name, "")))
        except (pygame.error, OSError, TypeError):
            self.sounds = {}       # no device: a silent battle
            return
        for name, path in own_sounds(folder).items():
            try:
                self.sounds[name] = pygame.mixer.Sound(str(path))
                self.own[name] = path
            except (pygame.error, OSError) as e:
                self.problems.append(f"{path.name}: {e}")

    def choose(self, name: str, variant: str) -> None:
        """Switch to another version of a sound (phaser or launch: a, b or c). A WAV of the player's own still wins."""
        name = ALIASES.get(name, name)
        if variant not in VARIANTS.get(name, {}):
            return
        self.choice[name] = variant
        if self.available and name not in self.own:
            self.sounds[name] = pygame.mixer.Sound(buffer=_samples(name, self._stereo, variant))

    def settings(self) -> dict[str, str]:
        """The versions chosen, as settings.json keeps them ("torpedo" for the launch)."""
        back = {v: k for k, v in ALIASES.items()}
        return {back.get(k, k): v for k, v in sorted(self.choice.items())}

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


__all__ = ["ALIASES", "Audio", "SOUNDS", "VARIANTS", "own_sounds", "write_wav"]
