"""The provider interface and configuration.

Configuration lives in the user settings (`settings.json` → "llm") and can be
overridden by environment variables. API keys are read only from the
environment and are never written to disk:

    "llm": {"provider": "anthropic", "model": "<model id>", "effort": "low"}

    BEGIN_LLM_PROVIDER   anthropic | openai | openrouter | ollama
    BEGIN_LLM_MODEL      the provider's model id (required: there is no default)
    BEGIN_LLM_BASE_URL   optional endpoint override (e.g. a remote Ollama)
    ANTHROPIC_API_KEY, OPENAI_API_KEY, OPENROUTER_API_KEY

Requests run on a background thread (see `llm/service.py`), so a slow or
failing provider never stalls the game.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Mapping, Protocol

Message = dict[str, str]  # {"role": "user" | "assistant", "content": "..."}

PROVIDERS = ("anthropic", "openai", "openrouter", "ollama")


class LLMError(Exception):
    """A provider could not answer; the message is shown to the player."""


@dataclass(frozen=True)
class LLMConfig:
    provider: str
    model: str
    base_url: str | None = None
    timeout: float = 45.0
    max_tokens: int = 2000
    effort: str | None = None      # Anthropic only: low | medium | high ...


class Provider(Protocol):
    name: str

    def complete(self, system: str, messages: list[Message]) -> str: ...


def config_from_settings(llm: Mapping[str, object], env: Mapping[str, str] = os.environ) -> LLMConfig | None:
    """None when no provider is configured (the officers then answer offline)."""
    provider = str(env.get("BEGIN_LLM_PROVIDER") or llm.get("provider") or "").lower().strip()
    if not provider or provider == "off":
        return None
    if provider not in PROVIDERS:
        raise LLMError(f"Unknown LLM provider '{provider}'. Use one of: {', '.join(PROVIDERS)}.")
    model = str(env.get("BEGIN_LLM_MODEL") or llm.get("model") or "").strip()
    if not model:
        raise LLMError(f"Set a model for {provider}: BEGIN_LLM_MODEL or \"model\" in settings.json.")
    base = env.get("BEGIN_LLM_BASE_URL") or llm.get("base_url") or None
    effort = llm.get("effort")
    return LLMConfig(provider, model, str(base) if base else None,
                     float(llm.get("timeout", 45.0)),  # type: ignore[arg-type]
                     int(llm.get("max_tokens", 2000)),  # type: ignore[call-overload]
                     str(effort) if effort else None)


def make_provider(cfg: LLMConfig, env: Mapping[str, str] = os.environ) -> Provider:
    if cfg.provider == "anthropic":
        from .anthropic import AnthropicProvider

        return AnthropicProvider(cfg)
    if cfg.provider == "openai":
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(cfg, "openai", cfg.base_url or "https://api.openai.com/v1", env.get("OPENAI_API_KEY"))
    if cfg.provider == "openrouter":
        from .openai_compat import OpenAICompatProvider

        return OpenAICompatProvider(cfg, "openrouter", cfg.base_url or "https://openrouter.ai/api/v1",
                                    env.get("OPENROUTER_API_KEY"))
    from .ollama import OllamaProvider

    return OllamaProvider(cfg)


def post_json(url: str, body: dict[str, Any], headers: dict[str, str], timeout: float) -> dict[str, Any]:
    """POST JSON with the standard library and return the decoded reply."""
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed provider URLs
            return json.loads(resp.read().decode("utf-8"))  # type: ignore[no-any-return]
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "replace")[:300]
        raise LLMError(f"{e.code} from the provider: {detail}") from e
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        raise LLMError(f"Could not reach the provider: {e}") from e
    except ValueError as e:
        raise LLMError("The provider sent a reply that is not JSON.") from e


__all__ = ["LLMConfig", "LLMError", "Message", "PROVIDERS", "Provider", "config_from_settings", "make_provider", "post_json"]
