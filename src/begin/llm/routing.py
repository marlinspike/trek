"""An optional second language model for character voices: richer Klingon, Romulan and other alien speech [E].

The main model (settings.json → "llm") does everything that must follow the game's rules: reading the captain's
orders, the console's plain-English translation, judging a speech. A second model can take over the lines that are
only flavour, where a different model may simply speak better in character: an enemy captain answering a hail or
taunting you, an officer's chatter, the officers' parts of the captain's log.

    "llm": {
      "provider": "ollama", "model": "lfm3",
      "character": {
        "provider": "ollama", "model": "<another local model>",
        "for": ["captains"],                 # which situations: captains, taunts, officers, chatter, log
        "factions": ["klingon"],             # captains of these factions only (left out: every faction)
        "officers": [],                      # officers by id (worf, spock, ...) (left out: every officer)
        "notes": {"klingon": "Use a few words of Klingon (tlhIngan Hol), each followed by its meaning."},
        "only": ["worf"]                     # these characters speak through this model alone (see below)
      }
    }

"only" pins characters (officer ids, or factions for enemy captains) to the character model: everything they say
goes there, whatever "for", "factions" and "officers" say, and if it fails the main model does not stand in (an
officer then answers offline, as with no model at all). Pinning never covers the console or the game's judgements.

Every other key of "character" (base_url, think, timeout, max_tokens, effort) means what it means for the main model.
"enabled": false keeps the settings but sends everything to the main model. The debug logs follow the main model's
switches, and the second model's requests show up in them under its own model name.

If the second model fails (not running, too slow), the same request goes to the main model, so a hail is never left
unanswered. Nothing here knows about ships: the session passes `faction_of`, which names an enemy ship's faction.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Mapping

from .providers.base import LLMConfig, LLMError, Message, Provider, config_from_settings, parse_switch

# what each situation covers; the tags are the ones LLMService requests carry (crew/hails.py, crew/conversation.py,
# ui/tour_scene.py). Anything else (the console, named orders, judging a speech) always stays on the main model.
SITUATIONS: dict[str, str] = {
    "captains": "Enemy captains answering when you hail them",
    "taunts": "Enemy captains calling you unprompted: boasts, threats, insults",
    "officers": "Your officers answering when you talk to them",
    "chatter": "Your officers' remarks during the battle, put in their own words",
    "log": "Your officers' parts of the captain's log on a tour",
}
DEFAULT_FOR = ("captains", "taunts")
CHARACTER_KEY = "character"
_HAIL, _TAUNT, _LINE = "\0hail:", "\0hailvoice:", "\0line:"
_NEVER = ("console", "orders")


@dataclass(frozen=True)
class CharacterRoute:
    """Which requests the character model answers, and what extra it is told."""

    situations: frozenset[str] = frozenset(DEFAULT_FOR)
    factions: frozenset[str] = frozenset()     # empty: every faction
    officers: frozenset[str] = frozenset()     # empty: every officer
    notes: Mapping[str, str] = field(default_factory=dict)   # faction or officer id (or "*") -> added to the prompt
    only: frozenset[str] = frozenset()         # officer ids or factions that speak through the character model alone

    def place(self, tag: str) -> tuple[str, str] | None:
        """(situation, who) for a request tag: who is a ship id for captains, an officer id for the crew."""
        if not tag or tag in _NEVER:
            return None
        if tag.startswith(_TAUNT):
            return "taunts", tag[len(_TAUNT):]
        if tag.startswith(_HAIL):
            return "captains", tag[len(_HAIL):]
        if tag.startswith(_LINE):
            return "chatter", tag[len(_LINE):]
        if tag.startswith("log:"):
            return "log", tag[4:]
        if tag.startswith("\0"):
            return None             # the game's own judgements (e.g. weighing the captain's speech)
        return "officers", tag      # an officer's id: a conversation

    def subject(self, tag: str, faction_of: Callable[[str], str | None]) -> str | None:
        """The faction or officer the request speaks for when the character model should answer it, else None."""
        where = self.place(tag)
        if where is None:
            return None
        situation, who = where
        if situation in ("captains", "taunts"):
            fac = faction_of(who)
            if fac is None:
                return None
            if fac in self.only:
                return fac
            return fac if situation in self.situations and (not self.factions or fac in self.factions) else None
        if who in self.only:
            return who
        return who if situation in self.situations and (not self.officers or who in self.officers) else None

    def pinned(self, subject: str) -> bool:
        """True when this character speaks through the character model alone, with no main model standing in."""
        return subject in self.only

    def note(self, subject: str) -> str:
        return " ".join(n for n in (self.notes.get("*", ""), self.notes.get(subject, "")) if n).strip()


def _names(raw: object) -> frozenset[str]:
    if isinstance(raw, str):
        raw = [raw]
    if not isinstance(raw, (list, tuple, set, frozenset)):
        return frozenset()
    return frozenset(str(x).strip().lower() for x in raw if str(x).strip())


def route_from_settings(ch: Mapping[str, object]) -> CharacterRoute:
    situations = _names(ch.get("for")) if "for" in ch else frozenset(DEFAULT_FOR)
    unknown = situations - SITUATIONS.keys()
    if unknown:
        raise LLMError(f"Unknown situation(s) for the character model: {', '.join(sorted(unknown))}. "
                       f"Use: {', '.join(SITUATIONS)}.")
    notes = ch.get("notes")
    return CharacterRoute(situations, _names(ch.get("factions")), _names(ch.get("officers")),
                          {str(k).lower(): str(v) for k, v in notes.items()} if isinstance(notes, Mapping) else {},
                          _names(ch.get("only")))


def character_from_settings(llm: Mapping[str, object]) -> tuple[LLMConfig, CharacterRoute] | None:
    """The character model's config and route, or None when there is none (or it is switched off).

    The environment's BEGIN_LLM_* variables are for the main model, so they are not read here; the debug log
    switches are inherited from the main model.
    """
    ch = llm.get(CHARACTER_KEY)
    if not isinstance(ch, Mapping) or not ch or not parse_switch(ch.get("enabled", True)):
        return None
    sub = {k: v for k, v in ch.items() if k not in ("for", "factions", "officers", "notes", "only", "enabled")}
    sub.update({k: llm[k] for k in ("log_prompts", "log_tokens") if k in llm})
    cfg = config_from_settings(sub, env={})
    if cfg is None:
        return None
    return cfg, route_from_settings(ch)


class RoutedProvider:
    """The main model, with the character model answering the requests its route covers.

    Who asked comes from `llm.usage.caller`, which LLMService sets on its worker thread before each request,
    so nothing upstream changes: every screen and module still submits to one service.
    """

    def __init__(self, main: Provider, character: Provider, route: CharacterRoute,
                 faction_of: Callable[[str], str | None] = lambda ship: None) -> None:
        self.main = main
        self.character = character
        self.route = route
        self.faction_of = faction_of
        self.name = main.name
        self.fallbacks = 0        # requests the character model failed and the main model answered

    def complete(self, system: str, messages: list[Message]) -> str:
        from .usage import caller

        subject = self.route.subject(caller.get(), self._faction)
        if subject is None:
            return self.main.complete(system, messages)
        note = self.route.note(subject)
        try:
            return self.character.complete(system + ("\n\n" + note if note else ""), messages)
        except Exception as e:  # noqa: BLE001 - the main model is the safety net for anything the second one can't do
            if self.route.pinned(subject):
                raise e if isinstance(e, LLMError) else LLMError(f"{type(e).__name__}: {e}") from e
            self.fallbacks += 1
            return self.main.complete(system, messages)

    def _faction(self, ship: str) -> str | None:
        try:
            return self.faction_of(ship)
        except Exception:  # noqa: BLE001 - a ship that's gone: answer with the main model
            return None


def with_character(main: Provider, llm: Mapping[str, object],
                   faction_of: Callable[[str], str | None] = lambda ship: None) -> Routed:
    """`main`, routed through the character model when one is configured.

    A character model that is misconfigured is left out (the main model answers everything) rather than stopping
    the game; `Routed.problem` says why, for the battle log.
    """
    try:
        found = character_from_settings(llm)
        if found is None:
            return Routed(main)
        from .providers.base import make_provider

        cfg, route = found
        return Routed(RoutedProvider(main, make_provider(cfg), route, faction_of), cfg, route)
    except Exception as e:  # noqa: BLE001 - no second model is never an error
        return Routed(main, problem=str(e) or type(e).__name__)


@dataclass(frozen=True)
class Routed:
    provider: Provider
    cfg: LLMConfig | None = None          # the character model's, when one is in use
    route: CharacterRoute | None = None
    problem: str | None = None            # why a configured character model was left out

    def note(self) -> str | None:
        """One line for the battle log about the character model, or None when there is nothing to say."""
        if self.problem:
            return f"Character voice model left out ({self.problem}); the main model speaks for everyone."
        if self.cfg is None or self.route is None:
            return None
        return f"Character voices through {self.cfg.provider} ({self.cfg.model}): {', '.join(sorted(self.route.situations))}."


__all__ = ["CHARACTER_KEY", "CharacterRoute", "DEFAULT_FOR", "Routed", "RoutedProvider", "SITUATIONS",
           "character_from_settings", "route_from_settings", "with_character"]
