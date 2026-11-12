"""Language models for the game, made from the captain's settings: the one place providers are built [E].

The battle session wires its own (officers, hails, the console's translator, named orders); anything else that
wants a model, such as the tour's captain's log, asks here, so the screens never touch a provider. The settings
page for the character voice model (llm/routing.py) reads its situations from here for the same reason.
"""

from __future__ import annotations

import os
import time
from collections.abc import Mapping

from ..console.translator import MODES as CONSOLE_MODES
from ..llm.providers.base import PROVIDERS
from ..llm.routing import CHARACTER_KEY, DEFAULT_FOR as DEFAULT_CHARACTER_FOR, SITUATIONS as CHARACTER_SITUATIONS
from ..llm.service import LLMService

KEY_ENV = {"anthropic": "ANTHROPIC_API_KEY", "openai": "OPENAI_API_KEY", "openrouter": "OPENROUTER_API_KEY"}
DEFAULT_ADDRESS = {"ollama": "http://localhost:11434", "openai": "https://api.openai.com/v1",
                   "openrouter": "https://openrouter.ai/api/v1", "anthropic": "Anthropic's own"}
TEST_QUESTION = "Mr. Spock, a one-sentence status report, please."


def make_service(llm_settings: dict[str, object], workers: int = 1) -> LLMService | None:
    """A model service from the `llm` settings, or None when none is set up (or it can't be reached)."""
    try:
        from ..llm.providers import config_from_settings, make_provider

        cfg = config_from_settings(llm_settings)
        if cfg is None:
            return None
        from ..llm.routing import with_character

        return LLMService(with_character(make_provider(cfg), llm_settings).provider, workers=workers)
    except Exception:  # noqa: BLE001 - no model is never an error: the game plays without one
        return None


def problem(llm_settings: Mapping[str, object]) -> str | None:
    """What is wrong with the `llm` settings as they stand (main model, then the character model), or None."""
    from ..llm.providers import config_from_settings
    from ..llm.routing import character_from_settings

    try:
        config_from_settings(llm_settings, env={})
        character_from_settings(llm_settings)
    except Exception as e:  # noqa: BLE001 - shown to the captain, never raised
        return str(e)
    return None


def key_problem(provider: str, env: Mapping[str, str] = os.environ) -> str | None:
    """A cloud provider's key comes only from the environment: say so when it isn't there."""
    name = KEY_ENV.get(provider)
    return f"Set {name} in the environment before starting Begin" if name and not env.get(name) else None


def ask_once(llm_settings: Mapping[str, object], character: bool = False,
             question: str = TEST_QUESTION) -> tuple[bool, str, float]:
    """One real question through the main model (or the character model): (worked, the reply or why not, seconds).

    Slow by nature (a local model may need loading): call it from a worker thread, never the frame loop.
    """
    from ..llm.providers import config_from_settings, make_provider
    from ..llm.routing import character_from_settings
    from ..llm.usage import caller

    t0 = time.perf_counter()
    try:
        if character:
            found = character_from_settings(llm_settings)
            cfg = found[0] if found else None
        else:
            cfg = config_from_settings(llm_settings)
        if cfg is None:
            return False, "No model is set up.", 0.0
        caller.set("llm-test")
        system = ("You are a starship's science officer in a tactical battle game, answering your captain. "
                  "Reply in one short sentence.")
        text = make_provider(cfg).complete(system, [{"role": "user", "content": question}])
    except Exception as e:  # noqa: BLE001 - the answer is the error, in words
        return False, str(e) or type(e).__name__, time.perf_counter() - t0
    return True, " ".join(str(text).split()), time.perf_counter() - t0


__all__ = ["CHARACTER_KEY", "CHARACTER_SITUATIONS", "CONSOLE_MODES", "DEFAULT_ADDRESS", "DEFAULT_CHARACTER_FOR", "KEY_ENV",
           "PROVIDERS", "TEST_QUESTION", "ask_once", "key_problem", "make_service", "problem"]
