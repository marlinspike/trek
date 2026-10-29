"""Application shell: window, scene switching and the frame loop."""

from __future__ import annotations

import os

import pygame

from ..battle import BattleSetup, build_battle
from ..content import default_content
from .battle_scene import BattleScene
from .menu_scene import MenuScene
from .settings import Settings

TARGET_FPS = 60


class App:
    def __init__(self, size: tuple[int, int] | None = None, headless: bool = False) -> None:
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        pygame.init()
        pygame.key.set_repeat(350, 40)
        self.settings = Settings.load()
        self.size = size or tuple(self.settings.window)  # type: ignore[assignment]
        flags = pygame.RESIZABLE
        self.screen = pygame.display.set_mode(self.size, flags)
        pygame.display.set_caption("Begin — tactical starship simulation")
        self.clock = pygame.time.Clock()
        self.content = default_content()
        self.running = True
        self.menu = MenuScene(self.content, self.settings, self.start_battle, self.stop)
        self.menu.layout(self.size)
        self.scene: MenuScene | BattleScene = self.menu
        self.fps = 0.0

    def stop(self) -> None:
        self.running = False

    def start_battle(self, setup: BattleSetup) -> BattleScene:
        battle = build_battle(self.content, setup)
        scene = BattleScene(battle, self.screen.get_size(), self.back_to_menu, keys=self.settings.keys)
        scene.speed = float(self.settings.speed) if float(self.settings.speed) in (0.25, 0.5, 1.0, 2.0, 4.0) else 1.0
        self.scene = scene
        return scene

    def back_to_menu(self) -> None:
        if isinstance(self.scene, BattleScene):
            self.settings.speed = self.scene.speed
            self.settings.save()
        self.menu.page = "main"
        self.menu.layout(self.screen.get_size())
        self.scene = self.menu

    def frame(self, dt: float) -> None:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.VIDEORESIZE:
                self.settings.window = (ev.w, ev.h)
                self.scene.handle(ev)
            else:
                self.scene.handle(ev)
        self.scene.update(dt)
        self.scene.draw(self.screen)
        pygame.display.flip()

    def run(self) -> None:
        while self.running:
            dt = min(0.1, self.clock.tick(TARGET_FPS) / 1000.0)
            self.fps = self.clock.get_fps()
            self.frame(dt)
        self.settings.save()
        pygame.quit()


__all__ = ["App"]
