"""Ollama: a local model server (default http://localhost:11434), no API key.

`think` in the config switches a reasoning model's thinking on or off (or picks
a named level). The reasoning comes back in a separate field and is dropped;
only the answer reaches the officer.
"""

from __future__ import annotations

import re
from typing import Any

from .base import Completion, LLMConfig, LLMError, Message, Usage, post_json

_THINK_TAGS = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)


class OllamaProvider:
    name = "ollama"

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.url = (cfg.base_url or "http://localhost:11434").rstrip("/") + "/api/chat"

    def body(self, system: str, messages: list[Message]) -> dict[str, Any]:
        body: dict[str, Any] = {"model": self.cfg.model, "stream": False,
                                "messages": [{"role": "system", "content": system}, *messages],
                                "options": {"num_predict": self.cfg.max_tokens}}
        if self.cfg.think is not None:
            body["think"] = self.cfg.think
        return body

    def complete(self, system: str, messages: list[Message]) -> str:
        return self.complete_full(system, messages).text

    def complete_full(self, system: str, messages: list[Message]) -> Completion:
        try:
            data = post_json(self.url, self.body(system, messages), {}, self.cfg.timeout)
        except LLMError as e:
            if self.cfg.think and "think" in str(e).lower():
                raise LLMError(f"{e} Set \"think\": false (or remove it) for this model.") from e
            raise
        text = (data.get("message") or {}).get("content") if isinstance(data, dict) else None
        if isinstance(text, str):
            text = _THINK_TAGS.sub("", text).strip()  # models that think inline rather than in the separate field
        if not isinstance(text, str) or not text:
            raise LLMError("Ollama returned no text.")
        return Completion(text, usage_of(data))


def usage_of(data: dict[str, Any]) -> Usage | None:
    """Ollama's own counts: prompt_eval_count (in) and eval_count (out, thinking included).

    Ollama leaves prompt_eval_count out when it reuses a cached prompt, so a
    missing count is None and the caller estimates it."""
    tin, tout = data.get("prompt_eval_count"), data.get("eval_count")
    if not isinstance(tin, int) or not isinstance(tout, int):
        return None
    return Usage(tin, tout)
