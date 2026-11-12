"""Application shell: window, scene switching and the frame loop."""

from __future__ import annotations

import os
from pathlib import Path

import pygame

from ..battle import BattleSetup, build_battle
from ..content import default_content
from ..tour.run import TourRun
from .battle_scene import BattleScene
from .menu_scene import MenuScene
from .present import Presenter, open_presenter, prepare, relaunch_command
from ..settings import Settings
from .tour_scene import TourScene

TARGET_FPS = 60


ICON = Path(__file__).resolve().parent.parent / "assets" / "icon.png"


def _window_icon() -> pygame.Surface | None:
    """The Enterprise on the title bar, taskbar and (when run from Python) the Dock; drawn by tools/make_icon.py."""
    try:
        return pygame.image.load(str(ICON))
    except (pygame.error, FileNotFoundError):
        return None


class App:
    def __init__(self, size: tuple[int, int] | None = None, headless: bool = False,
                 renderer: str | None = None) -> None:
        if headless:
            os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
            os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
        self.settings = Settings.load()
        chosen = "software" if headless else (renderer or self.settings.renderer)
        self._started_with = chosen
        self.restarting = False
        prepare(chosen)
        pygame.init()
        pygame.key.set_repeat(350, 40)
        w, h = self.settings.window
        self.size: tuple[int, int] = size or (w, h)
        self.presenter: Presenter = open_presenter(chosen, self.size, _window_icon(), bloom=self.settings.bloom)
        if not headless:
            print(f"Begin: {self.presenter.note}")
        self.clock = pygame.time.Clock()
        self.content = default_content()
        self.running = True
        self.menu = MenuScene(self.content, self.settings, self.start_battle, self.stop, tours=self.open_tours,
                              display=self)
        self.menu.layout(self.size)
        self.tours: TourScene | None = None       # made the first time a tour is opened
        self.tour_run: TourRun | None = None      # the tour whose battle is being fought
        self.scene: MenuScene | BattleScene | TourScene = self.menu
        self.fps = 0.0

    @property
    def screen(self) -> pygame.Surface:
        """What the scenes draw on: the window's logical size, at the presenter's density."""
        return self.presenter.screen

    def stop(self) -> None:
        self.running = False

    # ------------------------------------------------------------ the Display page (DisplayControl)

    @property
    def started_with(self) -> str:
        return self._started_with

    def set_bloom(self, on: bool) -> None:
        self.settings.bloom = self.presenter.bloom = on
        self.settings.save()

    def restart(self) -> None:
        """Close cleanly and start again, so a renderer just chosen takes over."""
        self.settings.save()
        self.restarting = True
        self.running = False

    def _relaunch(self) -> None:
        import subprocess
        import sys

        cmd = relaunch_command(sys.argv, sys.orig_argv, sys.executable,
                               bool(getattr(sys, "frozen", False)))
        try:
            subprocess.Popen(cmd, close_fds=True)
        except OSError as e:
            print(f"Begin: couldn't restart ({e}); start the game again to use the new renderer")

    def start_battle(self, setup: BattleSetup) -> BattleScene:
        battle = build_battle(self.content, setup)
        scene = BattleScene(battle, self.screen.get_size(), self.back_to_menu, keys=self.settings.keys,
                            hidden=self.settings.hidden, llm=self.settings.llm, chatter=self.settings.chatter,
                            volume=self.settings.volume, muted=self.settings.muted,
                            sounds=self.settings.sounds, hum=self.settings.hum, jolt=self.settings.jolt,
                            bridge=self.settings.bridge, career=self.settings.career, voice=self.settings.voice)
        scene.speed = float(self.settings.speed) if float(self.settings.speed) in (0.25, 0.5, 1.0, 2.0, 4.0) else 1.0
        self.scene = scene
        return scene

    def _leave_battle(self) -> None:
        if isinstance(self.scene, BattleScene):
            self.settings.speed = self.scene.speed
            self.settings.muted = self.scene.audio.muted
            self.settings.volume = self.scene.audio.volume
            self.settings.sounds = self.scene.audio.settings()
            self.settings.hum = self.scene.audio.hum
            self.settings.jolt = self.scene.view.jolt
            self.scene.close()
            self.settings.save()

    # ------------------------------------------------------------ tours of duty

    def open_tours(self) -> None:
        if self.tours is None:
            self.tours = TourScene(self.content, self.settings, self.start_tour_battle, self.back_to_menu)
        self.tours.open()
        self.tours.layout(self.screen.get_size())
        self.scene = self.tours

    def start_tour_battle(self, run: TourRun) -> BattleScene:
        """The Ready Room's launch: travel to the stop, build its battle with the squadron as it is now."""
        fight = run.launch()
        scene = self.start_battle(fight.setup)
        scene.session.join_tour(run)
        scene.exit_label = "Return to the Ready Room"
        scene.on_exit = self.end_tour_battle
        self.tour_run = run
        return scene

    def end_tour_battle(self) -> None:
        """The battle is over (or left): take the squadron back to the Ready Room and write up the log."""
        scene, run = self.scene, self.tour_run
        assert isinstance(scene, BattleScene) and run is not None and self.tours is not None
        scene.session.finish_tour(run)
        self._leave_battle()
        self.tour_run = None
        self.tours.after_battle(run)
        self.tours.layout(self.screen.get_size())
        self.scene = self.tours

    def back_to_menu(self) -> None:
        self._leave_battle()
        self.menu.page = "main"
        self.menu.layout(self.screen.get_size())
        self.scene = self.menu

    def frame(self, dt: float) -> None:
        for ev in self.presenter.events():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.VIDEORESIZE:
                self.settings.window = (ev.w, ev.h)
                self.scene.handle(ev)
            else:
                self.scene.handle(ev)
        self.scene.update(dt)
        self.scene.draw(self.screen)
        self.presenter.present()

    def run(self) -> None:
        while self.running:
            dt = min(0.1, self.clock.tick(TARGET_FPS) / 1000.0)
            self.fps = self.clock.get_fps()
            self.frame(dt)
        if isinstance(self.scene, BattleScene):
            self.scene.close()
        elif isinstance(self.scene, TourScene):
            self.scene.save()
        self.settings.save()
        self.presenter.close()
        pygame.quit()
        if self.restarting:
            self._relaunch()


__all__ = ["App"]
