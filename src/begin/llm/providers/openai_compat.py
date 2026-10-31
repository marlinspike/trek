"""OpenAI and OpenRouter: the chat-completions HTTP API, with the standard library."""

from __future__ import annotations

from typing import Any

from .base import Completion, LLMConfig, LLMError, Message, Usage, post_json


class OpenAICompatProvider:
    def __init__(self, cfg: LLMConfig, name: str, base_url: str, api_key: str | None) -> None:
        if not api_key:
            raise LLMError(f"Set {'OPENROUTER_API_KEY' if name == 'openrouter' else 'OPENAI_API_KEY'} to use {name}.")
        self.name = name
        self.cfg = cfg
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.headers = {"Authorization": f"Bearer {api_key}"}
        if name == "openrouter":
            self.headers["X-Title"] = "Begin remake"

    def complete(self, system: str, messages: list[Message]) -> str:
        return self.complete_full(system, messages).text

    def complete_full(self, system: str, messages: list[Message]) -> Completion:
        body: dict[str, Any] = {"model": self.cfg.model, "messages": [{"role": "system", "content": system}, *messages]}
        data = post_json(self.url, body, self.headers, self.cfg.timeout)
        try:
            text = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMError(f"Unexpected reply from {self.name}.") from e
        if not isinstance(text, str) or not text.strip():
            raise LLMError("The model returned no text.")
        usage = data.get("usage") if isinstance(data, dict) else None
        tin = usage.get("prompt_tokens") if isinstance(usage, dict) else None
        tout = usage.get("completion_tokens") if isinstance(usage, dict) else None
        return Completion(text, Usage(tin, tout) if isinstance(tin, int) and isinstance(tout, int) else None)
