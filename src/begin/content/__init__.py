"""Data-driven game content: ship classes, ordnance, factions, doctrines."""

from .loader import default_content, load_content
from .schema import ContentDB, Faction, ProbeDef, ShipClass, TorpedoDef

__all__ = ["ContentDB", "Faction", "ProbeDef", "ShipClass", "TorpedoDef", "default_content", "load_content"]
