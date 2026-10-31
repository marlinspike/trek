"""Debug logs for the language model: what was asked, what came back, and what it cost in tokens.

Both are off unless switched on in `settings.json` (or the environment):

    "llm": {"provider": "ollama", "model": "lfm3", "log_prompts": true, "log_tokens": true}
    begin --llm log_prompts=on log_tokens=on
    BEGIN_LLM_LOG_PROMPTS=on BEGIN_LLM_LOG_TOKENS=on

They live in the project's `config/logs/` folder, never in the home folder:

    llm-prompts.log   every request in full (system prompt, conversation, reply) with tokens in/out,
                      who asked and how long it took; rolled over to llm-prompts.1.log at 20 MB
    llm-tokens.json   all-time totals and one entry per game: calls, tokens in/out, errors, and
                      a breakdown by who asked (each officer, the console, hails, the captain's log)

Token counts are the provider's own (Ollama's prompt_eval_count / eval_count, the
`usage` block of Anthropic and OpenAI-style APIs). When a reply carries none,
they are estimated at four characters a token and marked as estimates.

A "game" is one `make_provider` call: a battle, a tour's captain's log between
battles, or one `begin --llm-test`. `begin --llm-usage` prints the totals.
"""

from __future__ import annotations

import contextvars
import itertools
import json
import os
import threading
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from .providers.base import Completion, LLMConfig, LLMError, Message, Provider, Usage

PROMPT_LOG = "llm-prompts.log"
TOKEN_LOG = "llm-tokens.json"
PROMPT_LOG_LIMIT = 20 * 1024 * 1024
MAX_GAMES = 500           # the token log keeps this many recent games; the totals keep counting
CHARS_PER_TOKEN = 4

# who asked: LLMService sets this on its worker thread before each request (an officer id, "console", ...)
caller: contextvars.ContextVar[str] = contextvars.ContextVar("llm_caller", default="direct")

_lock = threading.Lock()                  # one lock for both files: requests run on several worker threads
_ledgers: dict[Path, TokenLedger] = {}
_game_ids = itertools.count(1)


def log_dir() -> Path:
    from ..paths import config_dir

    return config_dir() / "logs"


def estimate_tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def estimate_usage(system: str, messages: list[Message], reply: str) -> Usage:
    prompt = system + "".join(m.get("content", "") for m in messages)
    return Usage(estimate_tokens(prompt), estimate_tokens(reply), estimated=True)


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _blank() -> dict[str, int]:
    return {"calls": 0, "tokens_in": 0, "tokens_out": 0, "estimated_calls": 0, "errors": 0}


def _add(into: dict[str, Any], usage: Usage | None, error: bool) -> None:
    into["calls"] = into.get("calls", 0) + 1
    if usage is not None:
        into["tokens_in"] = into.get("tokens_in", 0) + usage.tokens_in
        into["tokens_out"] = into.get("tokens_out", 0) + usage.tokens_out
        if usage.estimated:
            into["estimated_calls"] = into.get("estimated_calls", 0) + 1
    if error:
        into["errors"] = into.get("errors", 0) + 1


class TokenLedger:
    """`llm-tokens.json`: the running totals and per-game counts, rewritten after every request."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.data: dict[str, Any] = {"total": _blank(), "games": []}
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(loaded, dict) and isinstance(loaded.get("games"), list):
                self.data = {"total": {**_blank(), **loaded.get("total", {})}, "games": loaded["games"]}
        except (OSError, ValueError):
            pass   # no log yet (or a damaged one): start afresh

    @classmethod
    def at(cls, path: Path) -> TokenLedger:
        """One ledger per file for the whole process, so every provider adds to the same totals."""
        with _lock:
            if path not in _ledgers:
                _ledgers[path] = cls(path)
            return _ledgers[path]

    def record(self, game: dict[str, Any], who: str, usage: Usage | None, error: bool) -> None:
        with _lock:
            games: list[dict[str, Any]] = self.data["games"]
            if not any(g is game for g in games):
                games.append(game)
                del games[:-MAX_GAMES]
            _add(self.data["total"], usage, error)
            _add(game, usage, error)
            _add(game.setdefault("by_caller", {}).setdefault(who, {}), usage, error)
            game["last_call"] = _now()
            self.data["total"]["updated"] = game["last_call"]
            self._save()

    def _save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(self.data, indent=2) + "\n", encoding="utf-8")
            os.replace(tmp, self.path)
        except OSError:
            pass   # a log that cannot be written must never stop the game


class PromptLog:
    """`llm-prompts.log`: every request and reply, in full, for reading by eye."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def write(self, *, game: str, who: str, model: str, system: str, messages: list[Message],
              reply: str | None, error: str | None, usage: Usage | None, seconds: float) -> None:
        if usage is None:
            tokens = "tokens unknown"
        else:
            tokens = f"in {usage.tokens_in} out {usage.tokens_out}" + (" (estimated)" if usage.estimated else "")
        lines = [f"=== {_now()}  game {game}  {who}  {model}  {tokens}  {seconds:.1f}s", "--- system", system]
        for m in messages:
            lines += [f"--- {m.get('role', '?')}", m.get("content", "")]
        lines += ["--- error" if error else "--- reply", error or reply or "", ""]
        with _lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                if self.path.exists() and self.path.stat().st_size > PROMPT_LOG_LIMIT:
                    os.replace(self.path, self.path.with_name(self.path.stem + ".1" + self.path.suffix))
                with self.path.open("a", encoding="utf-8") as f:
                    f.write("\n".join(lines) + "\n")
            except OSError:
                pass


@dataclass
class _Game:
    id: str
    record: dict[str, Any]


class MeteredProvider:
    """Wraps a provider: every request is logged and counted, then answered exactly as the provider would."""

    def __init__(self, inner: Provider, cfg: LLMConfig, folder: Path | None = None) -> None:
        self.inner = inner
        self.name = inner.name
        self.cfg = cfg
        folder = folder or log_dir()
        self.prompts = PromptLog(folder / PROMPT_LOG) if cfg.log_prompts else None
        self.ledger = TokenLedger.at(folder / TOKEN_LOG) if cfg.log_tokens else None
        started = _now()
        gid = f"{started} #{next(_game_ids)}"
        self.game = _Game(gid, {"game": gid, "started": started, "provider": cfg.provider, "model": cfg.model,
                                **_blank()})

    def complete(self, system: str, messages: list[Message]) -> str:
        return self.complete_full(system, messages).text

    def complete_full(self, system: str, messages: list[Message]) -> Completion:
        who = caller.get()
        t0 = time.perf_counter()
        try:
            full = getattr(self.inner, "complete_full", None)
            done: Completion = full(system, messages) if full else Completion(self.inner.complete(system, messages))
        except Exception as e:
            self._log(who, system, messages, None, str(e) or type(e).__name__, None, time.perf_counter() - t0)
            raise
        usage = done.usage or estimate_usage(system, messages, done.text)
        self._log(who, system, messages, done.text, None, usage, time.perf_counter() - t0)
        return Completion(done.text, usage)

    def _log(self, who: str, system: str, messages: list[Message], reply: str | None, error: str | None,
             usage: Usage | None, seconds: float) -> None:
        if self.prompts is not None:
            self.prompts.write(game=self.game.id, who=who, model=f"{self.cfg.provider}/{self.cfg.model}",
                               system=system, messages=messages, reply=reply, error=error, usage=usage,
                               seconds=seconds)
        if self.ledger is not None:
            self.ledger.record(self.game.record, who, usage, error is not None)


def summary(path: Path | None = None, last: int = 10) -> str:
    """The token log as text: all-time totals, then the most recent games."""
    path = path or log_dir() / TOKEN_LOG
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return f"No token log at {path}. Turn it on with: begin --llm log_tokens=on"
    t = data.get("total", {})

    def row(d: dict[str, Any]) -> str:
        est = f", {d.get('estimated_calls', 0)} estimated" if d.get("estimated_calls") else ""
        err = f", {d.get('errors', 0)} failed" if d.get("errors") else ""
        return (f"{d.get('calls', 0)} calls, {d.get('tokens_in', 0):,} tokens in, "
                f"{d.get('tokens_out', 0):,} out{est}{err}")

    out = [f"Token log: {path}", f"All time: {row(t)}"]
    games = data.get("games", [])[-last:]
    if games:
        out.append(f"\nLast {len(games)} game(s):")
    for g in games:
        out.append(f"  {g.get('started', '?')}  {g.get('provider', '?')}/{g.get('model', '?')}: {row(g)}")
        for who, d in sorted(g.get("by_caller", {}).items()):
            out.append(f"      {who}: {row(d)}")
    return "\n".join(out)


__all__ = ["MeteredProvider", "PromptLog", "TokenLedger", "caller", "estimate_tokens", "estimate_usage", "log_dir",
           "summary"]
