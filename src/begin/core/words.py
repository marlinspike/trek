"""Small helpers for the English the crew speaks."""

from __future__ import annotations


def the(name: str, cap: bool = False) -> str:
    """A ship's name as a sentence carries it: "the Hornet", but "Cube 228" or "#12" as they stand, since a
    designation with a number takes no article."""
    bare = name[:1] == "#" or any(w.isdigit() for w in name.split())
    if bare:
        return name
    return ("The " if cap else "the ") + name


__all__ = ["the"]
