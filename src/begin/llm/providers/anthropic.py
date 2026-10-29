"""Anthropic (Claude) through the official SDK: `pip install anthropic` (or the `llm` extra).

The SDK finds credentials itself (ANTHROPIC_API_KEY, or an `ant auth login` profile).
"""

from __future__ import annotations

from typing import Any

from .base import LLMConfig, LLMError, Message


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, cfg: LLMConfig) -> None:
        try:
            import anthropic
        except ImportError as e:
            raise LLMError("The Anthropic provider needs the SDK: pip install anthropic") from e
        self._sdk = anthropic
        self.cfg = cfg
        kw: dict[str, Any] = {"timeout": cfg.timeout, "max_retries": 1}
        if cfg.base_url:
            kw["base_url"] = cfg.base_url
        self.client = anthropic.Anthropic(**kw)

    def complete(self, system: str, messages: list[Message]) -> str:
        kw: dict[str, Any] = {}
        if self.cfg.effort:
            kw["output_config"] = {"effort": self.cfg.effort}
        sdk = self._sdk
        try:
            resp = self.client.messages.create(model=self.cfg.model, max_tokens=self.cfg.max_tokens, system=system,
                                               messages=messages, **kw)  # type: ignore[arg-type]
        except sdk.AuthenticationError as e:
            raise LLMError("Anthropic rejected the API key (ANTHROPIC_API_KEY).") from e
        except sdk.NotFoundError as e:
            raise LLMError(f"Anthropic does not know the model '{self.cfg.model}'.") from e
        except sdk.RateLimitError as e:
            raise LLMError("Anthropic rate limit reached; try again shortly.") from e
        except sdk.APIStatusError as e:
            raise LLMError(f"Anthropic error {e.status_code}: {e.message}") from e
        except sdk.APIConnectionError as e:
            raise LLMError("Could not reach Anthropic.") from e
        if resp.stop_reason == "refusal":
            raise LLMError("The model declined to answer.")
        text = "".join(b.text for b in resp.content if b.type == "text")
        if not text.strip():
            raise LLMError("The model returned no text.")
        return text
