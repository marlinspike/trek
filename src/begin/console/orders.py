"""Named tactical orders: a list of console lines the captain runs by name.

The player writes them in `config/orders.toml`:

    [beta-1]
    note = "Turn away, fan the torpedoes, let Spock fight while Seven goes for their shields"
    steps = [
        "helm 180 warp 5",
        "fire all torpedoes spread 10",
        "wait 2",
        "spock, you have the conn",
        "seven, disable their shields",
    ]

`execute order beta-1` (or just `beta-1`) runs the steps in turn, exactly as if
typed at the console. `wait N` holds the plan for N cycles of battle time.
"their" and "the target" mean whatever the ship has targeted when the step runs.

A step the console does not understand is translated once by the language
model, when the battle starts, checked with the real parser, and kept in
`config/orders.cache.json` so later battles need no model for it. A step that
cannot be made to work is reported then, not in the middle of a fight.
"""

from __future__ import annotations

import json
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from ..llm.service import LLMService
from .translator import parse_answer, system_prompt

TAG = "orders"
TARGET_MARK = "#T"            # stands for the current target in a translated step
MAX_WAIT = 600.0              # cycles
_NAME = re.compile(r"^[a-z0-9][a-z0-9_\-]*$")
_WAIT = re.compile(r"^\s*(?:wait|pause for|hold for)\s+(\d+(?:\.\d+)?)\s*(?:cycles?|c)?\s*$", re.I)
_TARGET = re.compile(r"\b(?:the\s+target|their|them|the\s+enemy)\b", re.I)
_EXECUTE = re.compile(r"^\s*(?:execute|exec)\b", re.I)


@dataclass(frozen=True)
class Step:
    text: str                     # the line as written
    wait: float = 0.0             # a `wait N` step: cycles to hold, nothing to run

    @property
    def is_wait(self) -> bool:
        return self.wait > 0


@dataclass(frozen=True)
class TacticalOrder:
    name: str
    steps: tuple[Step, ...]
    note: str = ""

    def summary(self) -> str:
        return " · ".join(s.text for s in self.steps)


Validate = Callable[[str], "str | None"]     # a console line -> why it would not run, or None


def mentions_target(line: str) -> bool:
    return bool(_TARGET.search(line))


def aim(line: str, target: int | None) -> str:
    """Put the current target into a step: "their", "the target" and #T become #<id>."""
    if target is None:
        return line
    line = line.replace(TARGET_MARK, f"#{target}")
    if _is_officer_line(line):
        return line       # an officer reads "their shields" well enough, and it reads better to the player
    return _TARGET.sub(f"#{target}", line)


def _is_officer_line(line: str) -> bool:
    head = line.split(None, 1)[0] if line.split() else ""
    return head.endswith(",") or head.lower() == "ask"


def read_orders(path: Path) -> tuple[dict[str, TacticalOrder], list[str]]:
    """The orders in one TOML file, and what was wrong with any of them."""
    problems: list[str] = []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as e:
        return {}, [f"{path.name}: {e}"]
    out: dict[str, TacticalOrder] = {}
    for raw, body in data.items():
        name = str(raw).strip().lower()
        if not _NAME.match(name):
            problems.append(f"'{raw}': a name is letters, digits, '-' and '_' (like beta-1).")
            continue
        note = ""
        if isinstance(body, dict):
            note = str(body.get("note", "")).strip()
            body = body.get("steps", [])
        if isinstance(body, str):
            body = [p for p in body.split(";")]
        if not isinstance(body, list):
            problems.append(f"{name}: steps should be a list of console lines.")
            continue
        steps: list[Step] = []
        for line in (str(x).strip() for x in body):
            if not line:
                continue
            m = _WAIT.match(line)
            if m:
                steps.append(Step(line, min(MAX_WAIT, max(0.1, float(m.group(1))))))
            elif _EXECUTE.match(line):
                problems.append(f"{name}: '{line}': an order cannot run another order.")
            else:
                steps.append(Step(line))
        if not steps:
            problems.append(f"{name}: no steps.")
            continue
        out[name] = TacticalOrder(name, tuple(steps), note)
    return out, problems


@dataclass
class _Line:
    commands: list[str] | None = None     # translated console lines, when the step needed the model
    error: str | None = None
    pending: bool = False


@dataclass
class OrderBook:
    """The captain's named orders, checked and (where needed) translated at the start of a battle."""

    orders: dict[str, TacticalOrder] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)
    source: Path | None = None
    cache_path: Path | None = None
    llm: LLMService | None = None
    lines: dict[str, _Line] = field(default_factory=dict)
    _cache: dict[str, list[str]] = field(default_factory=dict)
    _pending: dict[int, str] = field(default_factory=dict)

    @classmethod
    def load(cls, folder: Path) -> OrderBook:
        """config/orders.toml, or the committed example until the player writes their own."""
        path = folder / "orders.toml"
        if not path.is_file():
            path = folder / "orders.example.toml"
        if not path.is_file():
            return cls(cache_path=folder / "orders.cache.json")
        orders, problems = read_orders(path)
        book = cls(orders, problems, path, folder / "orders.cache.json")
        try:
            raw = json.loads(book.cache_path.read_text(encoding="utf-8"))   # type: ignore[union-attr]
            if isinstance(raw, dict):
                book._cache = {str(k): [str(c) for c in v] for k, v in raw.items() if isinstance(v, list)}
        except (OSError, ValueError):
            pass
        return book

    def find(self, name: str) -> TacticalOrder | None:
        key = name.strip().lower()
        for lead in ("order ", "plan "):
            key = key.removeprefix(lead)
        return self.orders.get(key.strip())

    # ------------------------------------------------------------ checking

    def prepare(self, validate: Validate, brief: str, target: int | None) -> list[str]:
        """Check every step now. Steps the parser rejects go to the model (if any); returns problems to show."""
        bad: list[str] = list(self.problems)
        for order in self.orders.values():
            for step in order.steps:
                if step.is_wait or step.text in self.lines:
                    continue
                line = self.lines[step.text] = _Line()
                err = validate(aim(step.text, target)) if _checkable(step.text, target) else None
                if err is None:
                    continue
                cached = self._cache.get(step.text)
                if cached is not None and all(_ok(validate, c, target) for c in cached):
                    line.commands = cached
                elif self.llm is not None:
                    line.pending = True
                    rid = self.llm.submit(TAG, system_prompt(_brief(brief)), [{"role": "user", "content": step.text}])
                    self._pending[rid] = step.text
                else:
                    line.error = err
                    bad.append(f"{order.name}: '{step.text}': {err}")
        return bad

    def busy(self) -> bool:
        return bool(self._pending)

    def poll(self, validate: Validate, target: int | None) -> list[str]:
        """Translations that have come back; returns problems to show."""
        bad: list[str] = []
        if self.llm is None or not self._pending:
            return bad
        for r in self.llm.poll():
            text = self._pending.pop(r.request_id, None)
            if text is None:
                continue
            line = self.lines.setdefault(text, _Line())
            line.pending = False
            if r.text is None:
                line.error = r.error or "the model did not answer"
            else:
                say, commands, clarify = parse_answer(r.text)
                wrong = [c for c in commands if not _ok(validate, c, target)]
                if not commands or wrong or clarify:
                    line.error = clarify or say or ("couldn't turn it into console commands" if not commands
                                                    else f"'{wrong[0]}' is not a console command")
                else:
                    line.commands = commands
                    self._cache[text] = commands
                    self._save()
            if line.error:
                bad.append(f"'{text}': {line.error}")
        return bad

    def _save(self) -> None:
        if self.cache_path is None:
            return
        try:
            self.cache_path.parent.mkdir(parents=True, exist_ok=True)
            self.cache_path.write_text(json.dumps(self._cache, indent=1, sort_keys=True), encoding="utf-8")
        except OSError:
            pass   # the cache only saves the model a little work next time

    def close(self) -> None:
        if self.llm is not None:
            self.llm.close()

    # ------------------------------------------------------------ the listing

    def listing(self) -> list[str]:
        if not self.orders:
            return ["No named orders yet. Copy config/orders.example.toml to config/orders.toml and write your own.",
                    "Then 'execute order <name>' (or just the name) runs one. See 'help orders'."]
        out = ["Named orders" + (" (the examples: write your own in config/orders.toml)"
                                 if self.source is not None and self.source.name == "orders.example.toml" else "")]
        for o in self.orders.values():
            out.append(f"  {o.name:<12} {o.note or o.summary()}")
            if o.note:
                out.append(f"  {'':<12} {o.summary()}")
        out.append("execute order <name> (or just the name) · belay (stop the one running)")
        return out


@dataclass
class OrderRun:
    """An order being carried out: which step comes next, and when."""

    order: TacticalOrder
    index: int = 0
    resume_tick: int = 0
    held_since: float | None = None     # wall-clock time a step started waiting on its translation

    @property
    def done(self) -> bool:
        return self.index >= len(self.order.steps)


def _checkable(text: str, target: int | None) -> bool:
    """A step aimed at the target can only be checked when something is targeted, or nothing names it."""
    return target is not None or not mentions_target(text) or _is_officer_line(text)


def _ok(validate: Validate, command: str, target: int | None) -> bool:
    if TARGET_MARK in command and target is None:
        return True       # can't check a target-aimed line with nothing targeted; it is checked again when run
    return validate(aim(command, target)) is None


def _brief(situation: str) -> str:
    return "\n".join([
        situation,
        "",
        "This line is one step of a named order the captain wrote before the battle; it will run later, "
        f"when the situation may have changed. Where it means the ship then targeted ('their', 'the target', "
        f"'the enemy'), write {TARGET_MARK} in place of the ship name, e.g. 'lock all banks on {TARGET_MARK}'. "
        "Do not ask questions: give the commands, or none if it cannot be done.",
    ])


__all__ = ["OrderBook", "OrderRun", "Step", "TacticalOrder", "aim", "mentions_target", "read_orders"]
