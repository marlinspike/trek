"""Keeping what goes to the language model small and steady.

Every request is a system prompt plus a short conversation. Nothing in the game
sends a growing log: each call site keeps its own rolling window (an officer's
last few exchanges, the console's last few lines), and `fit` is the safety net
under all of them, applied by `LLMService` to every request. It drops the
oldest turns until the whole prompt fits the budget, and never drops the
system prompt or the newest message.

`STABLE_END` marks where a system prompt's unchanging part ends (the rules,
the reply format, the command reference) and the part that changes every
request begins (the situation, what an officer said lately). Prompts put the
unchanging part first, so a provider can reuse it instead of reading it again:
Anthropic caches it (`cache_control`), and Ollama keeps a matching prefix in
its context. Providers that don't use the mark call `flatten`.
"""

from __future__ import annotations

Message = dict[str, str]     # as in providers/base.py (not imported: the providers import this module)

STABLE_END = "\x1e"          # ASCII record separator: never typed, never in model output
CHARS_PER_TOKEN = 4          # the same rough rule the token log uses for estimates
PROMPT_BUDGET = 3500         # tokens a whole prompt (system and conversation) may take before old turns go
MESSAGE_CAP = 2000           # characters any one message may carry (a pasted essay is cut, not sent whole)
MIN_CONTEXT = 4096           # Ollama: the smallest context window asked for


def tokens(text: str) -> int:
    return (len(text) + CHARS_PER_TOKEN - 1) // CHARS_PER_TOKEN


def flatten(system: str) -> str:
    """The system prompt as one plain text, without the stable-part mark."""
    return system.replace(STABLE_END, "\n")


def split(system: str) -> tuple[str, str]:
    """(unchanging part, changing part); the first is empty when the prompt has no mark."""
    if STABLE_END not in system:
        return "", system
    stable, _, rest = system.partition(STABLE_END)
    return stable.rstrip(), flatten(rest).lstrip()


def prompt_tokens(system: str, messages: list[Message]) -> int:
    return tokens(system) + sum(tokens(m.get("content", "")) for m in messages)


def fit(system: str, messages: list[Message], budget: int = PROMPT_BUDGET) -> list[Message]:
    """The conversation, trimmed to fit `budget` tokens with the system prompt: oldest turns first, a reply never
    left without the line it answered, and the newest message always kept. Long messages are cut to MESSAGE_CAP."""
    out = [m if len(m.get("content", "")) <= MESSAGE_CAP else {**m, "content": m["content"][:MESSAGE_CAP] + "…"}
           for m in messages]
    while len(out) > 1 and prompt_tokens(system, out) > budget:
        out.pop(0)
        while len(out) > 1 and out[0].get("role") == "assistant":
            out.pop(0)       # a conversation starts with the captain's words, not the model's answer
    return out


def context_window(max_tokens: int, budget: int = PROMPT_BUDGET) -> int:
    """Ollama's num_ctx: room for the largest prompt `fit` lets through (with a margin, since tokens are estimated)
    and the reply, as a power of two from MIN_CONTEXT. It depends on settings only, never on the request, so it
    stays the same all game: a different num_ctx makes Ollama load the model again."""
    need = int(budget * 1.25) + max_tokens
    size = MIN_CONTEXT
    while size < need:
        size *= 2
    return size


__all__ = ["CHARS_PER_TOKEN", "MESSAGE_CAP", "MIN_CONTEXT", "PROMPT_BUDGET", "STABLE_END", "context_window", "fit",
           "flatten", "prompt_tokens", "split", "tokens"]
