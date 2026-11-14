"""Orders as plain data: every `Command` to JSON-ready dicts and back [E].

The simulation is deterministic: the same orders at the same ticks give the same battle. So two machines can
play one battle by exchanging orders alone (lockstep), and a battle can be replayed from its command log. Both
need orders that travel: this turns a `Command` into a dict of plain values (`encode`) and back (`decode`),
for every command type, driven by the dataclass fields and their type hints, so a new command needs no code
here. Fields typed `object` are results filled in when an order is carried out (a hail's answer), not part of
the order, and are left out.

    >>> data = encode(SetHelm(ship_id=3, course=90.0, warp=6.0))
    >>> data["type"], data["course"]
    ('SetHelm', 90.0)
    >>> decode(data) == SetHelm(ship_id=3, course=90.0, warp=6.0)
    True
"""

from __future__ import annotations

import dataclasses
import json
import types
import typing
from enum import Enum
from functools import lru_cache
from typing import Any, Literal, Union

from ..sim.commands import Command

JSON = dict[str, Any]


class WireError(ValueError):
    """The data isn't an order this game knows."""


@lru_cache(maxsize=1)
def command_types() -> dict[str, type[Command]]:
    """Every concrete command type, by class name."""
    out: dict[str, type[Command]] = {}

    def walk(cls: type[Command]) -> None:
        for sub in cls.__subclasses__():
            out[sub.__name__] = sub
            walk(sub)

    walk(Command)
    return out


_FIELDS: dict[type[Command], tuple[tuple[str, Any], ...]] = {}


def _fields(cls: type[Command]) -> tuple[tuple[str, Any], ...]:
    """(name, type hint) of the fields that make up an order of this type."""
    got = _FIELDS.get(cls)
    if got is None:
        hints = typing.get_type_hints(cls)   # each class's own module resolves its hints
        got = _FIELDS[cls] = tuple((f.name, hints[f.name]) for f in dataclasses.fields(cls)
                                   if f.init and hints[f.name] is not object)
    return got


def _plain(v: Any) -> Any:
    if isinstance(v, Enum):
        return v.value
    if isinstance(v, (tuple, list)):
        return [_plain(x) for x in v]
    return v


def encode(cmd: Command) -> JSON:
    """A command as a dict of JSON values, with its type under "type"."""
    out: JSON = {"type": type(cmd).__name__}
    for name, _hint in _fields(type(cmd)):
        out[name] = _plain(getattr(cmd, name))
    return out


def _value(hint: Any, v: Any) -> Any:
    if v is None:
        return None
    origin = typing.get_origin(hint)
    if origin in (Union, types.UnionType):
        last: Exception | None = None
        for arm in typing.get_args(hint):
            if arm is type(None):
                continue
            try:
                return _value(arm, v)
            except (ValueError, TypeError, WireError) as e:
                last = e
        raise WireError(f"{v!r} fits none of {hint}") from last
    if origin is Literal:
        if v in typing.get_args(hint):
            return v
        raise WireError(f"{v!r} is not one of {typing.get_args(hint)}")
    if origin is tuple:
        args = typing.get_args(hint)
        inner = args[0] if args else Any
        return tuple(_value(inner, x) for x in v)
    if isinstance(hint, type) and issubclass(hint, Enum):
        return hint(v)
    if hint is float:
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            raise WireError(f"{v!r} is not a number")
        return float(v)
    if hint is int:
        if isinstance(v, bool) or not isinstance(v, int):
            raise WireError(f"{v!r} is not a whole number")
        return v
    if hint is bool:
        if not isinstance(v, bool):
            raise WireError(f"{v!r} is not true or false")
        return v
    if hint is str:
        if not isinstance(v, str):
            raise WireError(f"{v!r} is not text")
        return v
    return v


def decode(data: JSON) -> Command:
    """The command a dict from `encode` describes. Raises `WireError` for anything else."""
    if not isinstance(data, dict):
        raise WireError("An order must be an object.")
    cls = command_types().get(str(data.get("type")))
    if cls is None:
        raise WireError(f"No order called {data.get('type')!r}.")
    kwargs: dict[str, Any] = {}
    for name, hint in _fields(cls):
        if name in data:
            kwargs[name] = _value(hint, data[name])
    unknown = set(data) - {"type"} - {n for n, _ in _fields(cls)}
    if unknown:
        raise WireError(f"{cls.__name__} has no {', '.join(sorted(unknown))}.")
    try:
        return cls(**kwargs)
    except TypeError as e:
        raise WireError(f"{cls.__name__}: {e}") from e


def dumps(cmd: Command) -> str:
    return json.dumps(encode(cmd), separators=(",", ":"))


def loads(text: str) -> Command:
    try:
        return decode(json.loads(text))
    except json.JSONDecodeError as e:
        raise WireError(f"Not JSON: {e}") from e


__all__ = ["JSON", "WireError", "command_types", "decode", "dumps", "encode", "loads"]
