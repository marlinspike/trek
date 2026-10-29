"""Deterministic random streams.

The simulation owns one stream; every AI brain and every subsystem that
needs randomness derives its own named sub-stream so that adding a consumer
never perturbs the others. Streams are reproducible from the battle seed.
"""

from __future__ import annotations

import hashlib
import random


class Rng:
    __slots__ = ("_r", "seed")

    def __init__(self, seed: int) -> None:
        self.seed = seed
        self._r = random.Random(seed)

    def derive(self, name: str) -> Rng:
        h = hashlib.blake2b(f"{self.seed}:{name}".encode(), digest_size=8).digest()
        return Rng(int.from_bytes(h, "little"))

    def unit(self) -> float:
        return self._r.random()

    def uniform(self, lo: float, hi: float) -> float:
        return lo + (hi - lo) * self._r.random()

    def irange(self, lo: int, hi: int) -> int:
        """Inclusive integer range; returns lo when hi < lo."""
        if hi <= lo:
            return lo
        return self._r.randint(lo, hi)

    def chance(self, p: float) -> bool:
        return self._r.random() < p

    def gauss(self, mu: float, sigma: float) -> float:
        return self._r.gauss(mu, sigma)

    def choice(self, seq: list):  # type: ignore[no-untyped-def]
        return seq[self._r.randrange(len(seq))]

    def shuffle(self, seq: list) -> None:  # type: ignore[type-arg]
        self._r.shuffle(seq)

    def getstate(self) -> object:
        return self._r.getstate()

    def setstate(self, state: object) -> None:
        self._r.setstate(state)  # type: ignore[arg-type]
