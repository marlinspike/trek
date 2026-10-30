"""Plain-English console input, through the configured language model [E].

The exact parser always gets the first look, so a line written in console
syntax runs at once. When it rejects a line (or, in "always" mode, for every
line) the line goes to the model with the full command reference and what the
ship knows. The model answers with console commands, a short answer, or a
clarifying question. Every command it proposes is checked with the real parser
before anything runs; if one is wrong the model gets one chance to fix it, with
the parser's complaint. The scene echoes each translated command, so the
captain learns the syntax by watching.

Requests run on the LLM service's background thread, so the battle never waits.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field

from ..llm.providers.base import Message
from ..llm.service import LLMService
from .parser import HELP

MODES = ("off", "fallback", "always")
TAG = "console"
MAX_COMMANDS = 6
HISTORY = 12          # messages kept, so "the closer one" can answer a clarifying question
# commands a misunderstanding must never trigger: these are only suggested
GUARDED = re.compile(r"^\s*(quit|exit|self\b|selfdestruct|sd\b|destruct|surrender|transport|beam)\b", re.I)

def normalize_mode(raw: object) -> str:
    word = str(raw or "").strip().lower()
    if word in ("", "on", "true", "yes", "fallback", "auto"):
        return "fallback"
    if word in ("off", "false", "no", "never"):
        return "off"
    if word in ("always", "all", "every"):
        return "always"
    return "fallback"


@dataclass
class Translation:
    """What the model made of a line: commands to run, something to say, or a question back."""

    text: str                                       # what the captain typed
    commands: list[str] = field(default_factory=list)
    say: str = ""
    clarify: str = ""
    held: list[str] = field(default_factory=list)   # guarded commands: shown, never run
    error: str | None = None                        # the model failed or could not be understood


Validate = Callable[[str], "str | None"]   # a console line -> why it would not run, or None


class Translator:
    def __init__(self, llm: LLMService, mode: object = "fallback") -> None:
        self.llm = llm
        self.mode = normalize_mode(mode)
        self.awaiting = False                        # the last answer was a clarifying question
        self.history: list[Message] = []
        self._pending: dict[int, _Request] = {}

    # ------------------------------------------------------------ routing

    def wants(self, parsed_ok: bool, exact_verb: bool) -> bool:
        """Should this line go to the model? `exact_verb`: its first word is a console verb spelled in full."""
        if self.mode == "off":
            return False
        if self.mode == "always":
            return True
        if self.awaiting and not (parsed_ok and exact_verb):
            return True   # probably the answer to our question, even if it happens to parse ("2")
        return not parsed_ok

    def busy(self) -> bool:
        return bool(self._pending)

    # ------------------------------------------------------------ requests

    def submit(self, text: str, brief: str, parser_error: str | None = None) -> None:
        note = f"\n(The console parser said: {parser_error})" if parser_error else ""
        self.history.append({"role": "user", "content": text + note})
        del self.history[:-HISTORY]
        self._send(_Request(text, brief, retried=False))

    def _send(self, req: _Request) -> None:
        rid = self.llm.submit(TAG, system_prompt(req.brief), list(self.history))
        self._pending[rid] = req

    def poll(self, validate: Validate) -> list[Translation]:
        """Translations that have arrived since the last frame; never blocks."""
        out: list[Translation] = []
        for r in self.llm.poll():
            req = self._pending.pop(r.request_id, None)
            if req is None:
                continue
            if r.text is None:
                self._drop_last_user()
                out.append(Translation(req.text, error=r.error or "no answer"))
                continue
            t = self._read(req, r.text, validate)
            if t is not None:
                out.append(t)
        return out

    def _read(self, req: _Request, raw: str, validate: Validate) -> Translation | None:
        say, commands, clarify = parse_answer(raw)
        self.history.append({"role": "assistant", "content": json.dumps(
            {"commands": commands, "say": say, "clarify": clarify})})
        bad = [(c, err) for c in commands if not GUARDED.match(c) and (err := validate(c)) is not None]
        if bad and not req.retried:
            # one chance to correct itself, with the parser's own words
            self.history.append({"role": "user", "content": "These commands were rejected by the console: "
                                 + "; ".join(f"'{c}': {e}" for c, e in bad)
                                 + ". Answer again with corrected commands, or ask me a question."})
            del self.history[:-HISTORY]
            self._send(_Request(req.text, req.brief, retried=True))
            return None
        del self.history[:-HISTORY]
        if bad:
            return Translation(req.text, say=say, error="; ".join(f"'{c}': {e}" for c, e in bad))
        held = [c for c in commands if GUARDED.match(c)]
        run = [c for c in commands if not GUARDED.match(c)]
        self.awaiting = bool(clarify) and not run
        if not run and not say and not clarify and not held:
            return Translation(req.text, error="the model gave no command")
        return Translation(req.text, run, say, clarify if not run else "", held)

    def _drop_last_user(self) -> None:
        if self.history and self.history[-1]["role"] == "user":
            self.history.pop()

    def close(self) -> None:
        self.llm.close()


@dataclass(frozen=True)
class _Request:
    text: str
    brief: str
    retried: bool


def system_prompt(brief: str) -> str:
    return "\n".join([
        "You translate a starship captain's plain-English orders into commands for the ship's console, in a "
        "real-time 2D tactical starship game. Courses are compass bearings (0 = up the map, 90 = right); "
        "distances are in units; warp 1 = 100 units per second.",
        "Answer with ONE JSON object and nothing else:",
        '{"commands": ["<console command>", ...], "say": "<optional short answer>", "clarify": "<a question, or empty>"}',
        "Rules:",
        "- Write each command exactly in the console syntax below, one command per string, using ship names "
        "from the situation. <...> is a value to fill in, [...] is optional, a|b means one of them; never type "
        "brackets.",
        "- If the meaning is clear, give the commands and leave clarify empty.",
        "- If it could mean different things that matter (which ship, which weapons, what course), give no "
        "commands and ask one short question in clarify. Do not guess at targets.",
        "- If the captain asks how to do something or a question about the ship, answer in say (one or two "
        "sentences) and give no commands unless they also asked you to act. Quote console syntax in say when "
        "it helps them learn it.",
        "- To put a question or an order to a bridge officer, the command is: ask <officer> <their words>.",
        "- If they typed a console command that is simply wrong (a tube the ship lacks, a ship that is not on "
        "sensors), give no commands and say what is wrong.",
        "- Never end the battle, self-destruct, surrender or change ships unless told to in so many words.",
        "",
        "Console commands:",
        *HELP,
        "",
        "Examples:",
        'turn right and go fast -> {"commands": ["helm 90 warp 8"], "say": "", "clarify": ""}',
        'shields up and hit their engines -> {"commands": ["raise all", "target <ship> propulsion", '
        '"fire all phasers"], "say": "", "clarify": ""} (with a ship name from the situation)',
        'attack him -> {"commands": [], "say": "", "clarify": "Which ship: <name> or <name>?"} when two enemies '
        "are in range",
        "",
        "What the ship knows right now:",
        brief,
    ])


def parse_answer(text: str) -> tuple[str, list[str], str]:
    """The model's JSON → (say, commands, clarifying question). Plain text is taken as speech."""
    from ..crew.conversation import clean_command, first_object, spoken

    data = first_object(text)
    if data is None:
        return spoken(text), [], ""
    cmds = data.get("commands") or []
    if not isinstance(cmds, list):
        cmds = [cmds]
    commands: list[str] = []
    for c in cmds:
        # a model sometimes packs several commands into one string
        for part in str(c).split(";"):
            part = clean_command(part)
            if part:
                commands.append(part)
    return str(data.get("say") or "").strip(), commands[:MAX_COMMANDS], str(data.get("clarify") or "").strip()


__all__ = ["MODES", "Translation", "Translator", "normalize_mode", "parse_answer", "system_prompt"]
