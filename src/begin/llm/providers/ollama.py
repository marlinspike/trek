"""Ollama: a local model server (default http://localhost:11434), no API key."""

from __future__ import annotations

from .base import LLMConfig, LLMError, Message, post_json


class OllamaProvider:
    name = "ollama"

    def __init__(self, cfg: LLMConfig) -> None:
        self.cfg = cfg
        self.url = (cfg.base_url or "http://localhost:11434").rstrip("/") + "/api/chat"

    def complete(self, system: str, messages: list[Message]) -> str:
        body = {"model": self.cfg.model, "stream": False,
                "messages": [{"role": "system", "content": system}, *messages]}
        data = post_json(self.url, body, {}, self.cfg.timeout)
        text = (data.get("message") or {}).get("content") if isinstance(data, dict) else None
        if not isinstance(text, str) or not text.strip():
            raise LLMError("Ollama returned no text.")
        return text
