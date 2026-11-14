"""Shortcuts to the bridge officers and to hailing frequencies: buttons that open the console ready to speak.

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state. What the
officers and other captains say and do is the session's (`session/comms.py`)."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from .state import SceneState

if TYPE_CHECKING:
    from ..battle_scene import BattleScene


class CommsMixin(SceneState):
    def _prompt(self: BattleScene, text: str) -> None:
        """Put words in the console, ready for the captain to finish."""
        self.console = text
        self.console_focus = True
        pygame.key.start_text_input()

    def hail(self: BattleScene, target: int | None, words: str) -> None:
        self.channels.hail(target, words)

    def open_channel(self: BattleScene, sid: int) -> None:
        """The Hail button: open a channel (they answer), then the console waits for the captain's words."""
        self.channels.open_channel(sid)

    def _comms_button(self: BattleScene, line: str) -> None:
        if line.startswith("\0type:"):
            self._prompt(line[len("\0type:"):])
            return
        self.run_console(line)

    def address_crew(self: BattleScene) -> None:
        """Open the console ready for a speech to the crew."""
        self.console = "address crew "
        self.console_focus = True

    def address(self: BattleScene, name: str) -> None:
        """Open the console ready to speak to an officer."""
        self.console = f"{name}, "
        self.console_focus = True


__all__ = ["CommsMixin"]
