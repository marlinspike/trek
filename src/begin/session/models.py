"""Language models for the game, made from the captain's settings: the one place providers are built [E].

The battle session wires its own (officers, hails, the console's translator, named orders); anything else that
wants a model, such as the tour's captain's log, asks here, so the screens never touch a provider. The settings
page for the character voice model (llm/routing.py) reads its situations from here for the same reason.
"""

from __future__ import annotations

from ..llm.routing import CHARACTER_KEY, DEFAULT_FOR as DEFAULT_CHARACTER_FOR, SITUATIONS as CHARACTER_SITUATIONS
from ..llm.service import LLMService


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


__all__ = ["CHARACTER_KEY", "CHARACTER_SITUATIONS", "DEFAULT_CHARACTER_FOR", "make_service"]
