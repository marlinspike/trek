"""Run LLM requests on a background thread and hand the answers back to the game loop."""

from __future__ import annotations

import itertools
from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass

from .providers.base import LLMError, Message, Provider


@dataclass(frozen=True)
class Reply:
    request_id: int
    tag: str                # who asked (an officer id)
    text: str | None
    error: str | None = None


class LLMService:
    def __init__(self, provider: Provider, workers: int = 2) -> None:
        self.provider = provider
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="llm")
        self._pending: dict[int, tuple[str, Future[str]]] = {}
        self._ids = itertools.count(1)

    def submit(self, tag: str, system: str, messages: list[Message]) -> int:
        rid = next(self._ids)
        self._pending[rid] = (tag, self._pool.submit(self._complete, tag, system, list(messages)))
        return rid

    def _complete(self, tag: str, system: str, messages: list[Message]) -> str:
        from .usage import caller

        caller.set(tag)         # on this worker thread: names who asked in the debug logs
        return self.provider.complete(system, messages)

    def busy(self, tag: str) -> bool:
        return any(t == tag for t, _ in self._pending.values())

    def poll(self) -> list[Reply]:
        """Finished requests since the last poll; never blocks."""
        out: list[Reply] = []
        for rid in [r for r, (_, f) in self._pending.items() if f.done()]:
            tag, fut = self._pending.pop(rid)
            try:
                out.append(Reply(rid, tag, fut.result()))
            except LLMError as e:
                out.append(Reply(rid, tag, None, str(e)))
            except Exception as e:  # noqa: BLE001 - a provider bug must not crash the battle
                out.append(Reply(rid, tag, None, f"{type(e).__name__}: {e}"))
        return out

    def close(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)


__all__ = ["LLMService", "Reply"]
