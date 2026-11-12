"""The game, as something you can play without a screen [E].

`begin.sim` is the simulation and `begin.ai` and `begin.crew` the minds in it. A session is one game being
played: it owns the clock, takes the captain's orders and says what happened. The UI (`begin.ui`) presents a
session and never reaches past it, so the AI, the game modes or a network link can change without touching
the screen. See `session/interface.py` for the contract and docs/ARCHITECTURE.md for the whole picture.
"""
