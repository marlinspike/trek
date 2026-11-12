"""Language models for the game, made from the captain's settings: the one place providers are built [E].

The battle session wires its own (officers, hails, the console's translator, named orders); anything else that
wants a model, such as the tour's captain's log, asks here, so the screens never touch a provider.
"""

from __future__ import annotations

from ..llm.service import LLMService


def make_service(llm_settings: dict[str, object], workers: int = 1) -> LLMService | None:
    """A model service from the `llm` settings, or None when none is set up (or it can't be reached)."""
    try:
        from ..llm.providers import config_from_settings, make_provider

        cfg = config_from_settings(llm_settings)
        if cfg is None:
            return None
        return LLMService(make_provider(cfg), workers=workers)
    except Exception:  # noqa: BLE001 - no model is never an error: the game plays without one
        return None


__all__ = ["make_service"]
