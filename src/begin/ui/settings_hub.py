"""Settings, from the main menu: everything in config/ a captain would want to change, without a text editor.

One page with a rail of sections down the left (Up and Down move through them) and the section's settings on
the right. Every change is saved the moment it is made, to the same files the game always read:
config/settings.json for the game's own settings, config/officers.toml for the officers (and there only the
line that changed: see crew/officer_file.py). Typed values (a model's name, a server's address) are kept on
Enter or a click elsewhere; Esc puts back what was there. Nothing here knows how a language model is built:
it asks session/models.py, as the architecture tests require.

Sections: Display, Sound, Battle, Bridge, Speaking orders, Language model, Character voices, Officers, Files.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import Any, Callable

import pygame

from ..content.schema import ContentDB
from ..crew import officer_file
from ..paths import config_dir, open_folder
from ..session import models
from ..session.prefs import FOCUS, MODES as BRIDGE_STYLES, PRESETS as BRIDGE_PRESETS, PROPOSALS, READBACKS, \
    SUBTITLES, BridgePrefs
from ..settings import Settings
from ..voice.settings import ENGINES, MODELS as WHISPER_MODELS, PTT_KEYS, VoiceSettings
from . import gfx, theme
from .present import RENDERER_INFO, RENDERERS, DisplayControl
from .widgets import UI, TextField

RAIL_W = 236              # the section rail's width
ROW = 48                  # one setting's height
LABEL_W = 210             # the label column, before the controls
SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0)
FACTIONS = ("klingon", "romulan", "orion")


@dataclass(frozen=True)
class Section:
    key: str
    title: str
    blurb: str
    hotkey: str = ""


SECTIONS = (
    Section("display", "Display", "How the game is drawn: sharpness on Retina and 4K screens, light and glow.", "D"),
    Section("sound", "Sound", "How loud, which phaser and torpedo you hear, and the ship's hum."),
    Section("battle", "Battle", "The speed battles start at, your officers' chatter, and the map's jolt."),
    Section("bridge", "Bridge", "How the bridge talks to you: subtitles, read-backs, the command wheel, proposals."),
    Section("voice", "Speaking orders", "Hold a key and say the order: what hears you, and which key."),
    Section("model", "Language model", "The model your officers think with, and that reads plain-English orders."),
    Section("voices", "Character voices", "A second model for alien captains and officers: more Klingon, more Romulan.",
            "V"),
    Section("officers", "Officers", "Your bridge officers' names, ranks, traits and how they speak."),
    Section("files", "Files", "Everything here is a plain text file in config/: which ones are yours so far."),
)

ENGINE_TITLES = {"mac": "Mac speech", "whisper-local": "Whisper on this computer",
                 "whisper-server": "Whisper server", "cloud": "Cloud transcription"}
PROVIDER_TITLES = {"off": "Off", "ollama": "Ollama", "anthropic": "Anthropic", "openai": "OpenAI",
                   "openrouter": "OpenRouter"}
FILES = (
    ("settings.json", "Everything on this page except the officers."),
    ("officers.toml", "Your officers: what the Officers section writes, and personas, backgrounds and lines."),
    ("orders.toml", "Your named tactical orders (execute order beta-1)."),
    ("hails.toml", "Enemy captains' answers to a hail when there's no language model."),
    ("wheel.toml", "Your own command wheel."),
    ("alerts.toml", "Your own red, yellow and green alert conditions."),
    ("begin2.key", "Begin 2.0 key macros: F2 fire all torpedoes."),
    ("sounds", "WAV files that replace the game's own sounds."),
    ("help", "Manual pages of your own."),
    ("tours", "Tours of duty in progress, their logs, and tours you write."),
)


def _words(raw: object) -> list[str]:
    return [str(v) for v in raw] if isinstance(raw, list) else ([str(raw)] if raw else [])


class SettingsHub:
    def __init__(self, settings: Settings, content: ContentDB, close: Callable[[], None],
                 display: DisplayControl | None = None, audio: Callable[[], Any] = lambda: None) -> None:
        self.settings = settings
        self.content = content
        self.close = close
        self.display = display
        self.audio = audio
        self.sections = [s for s in SECTIONS if s.key != "display" or display is not None]
        self.section = self.sections[0].key
        self.t = 0.0
        self.scroll = 0
        self._height = 0                         # how tall the section drew last frame (for scrolling)
        self._view = pygame.Rect(0, 0, 0, 0)     # where the section is drawn
        self._right = 0                          # the card's inner right edge: nothing is drawn past it
        self.fields: dict[str, TextField] = {}
        self._drag: Callable[[int], None] | None = None
        self._sliders: list[tuple[pygame.Rect, Callable[[int], None]]] = []
        self.note = ""                           # a line of news under the section: a test's answer, a download
        self.note_ok = True
        self._busy = ""                          # what a worker thread is doing ("" when nothing)
        self._ready: dict[str, str | None] | None = None      # each voice engine's readiness, worked out once
        self._crew_cache: list[tuple[str, str, Any]] | None = None
        self._shipped: dict[str, Any] | None = None            # the officers as the game ships them
        self._mine: dict[str, dict[str, officer_file.Value]] = {}   # what officers.toml itself says, per officer
        self.officer = ""

    # ------------------------------------------------------------ opening, keys and the mouse

    def open(self, section: str | None = None) -> None:
        if section is not None and any(s.key == section for s in self.sections):
            self.section = section
        self.scroll = 0
        self._ready = None
        self._crew_cache = None
        self._mine.clear()

    def go(self, key: str) -> None:
        self._unfocus()
        if key != self.section:
            self.section, self.scroll, self.note = key, 0, ""

    @property
    def editing(self) -> TextField | None:
        return next((f for f in self.fields.values() if f.focused), None)

    def _unfocus(self) -> None:
        f = self.editing
        if f is not None:
            f.done()
            pygame.key.stop_text_input()

    def handle(self, ev: pygame.event.Event) -> bool:
        """True when the event was the page's own (typing, dragging, scrolling); clicks go on to the hotspots."""
        f = self.editing
        if ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
            if f is not None and not f.rect.collidepoint(ev.pos):
                self._unfocus()
            for r, set_x in self._sliders:
                if r.collidepoint(ev.pos):
                    self._drag = set_x
                    set_x(ev.pos[0])
                    return True
            return False
        if ev.type == pygame.MOUSEMOTION and self._drag is not None:
            self._drag(ev.pos[0])
            return True
        if ev.type == pygame.MOUSEBUTTONUP and self._drag is not None:
            self._drag = None
            self.settings.save()
            return True
        if ev.type == pygame.MOUSEWHEEL:
            room = max(0, self._height - self._view.height)
            self.scroll = max(0, min(room, self.scroll - ev.y * 40))
            return True
        if f is not None and ev.type == pygame.TEXTINPUT:
            f.text(ev.text)
            return True
        if ev.type != pygame.KEYDOWN:
            return f is not None and ev.type == pygame.TEXTINPUT
        if f is not None:
            f.key(ev)
            if not f.focused:
                pygame.key.stop_text_input()
            return True
        keys = [s.key for s in self.sections]
        if ev.key in (pygame.K_UP, pygame.K_DOWN):
            i = keys.index(self.section) + (-1 if ev.key == pygame.K_UP else 1)
            self.go(keys[i % len(keys)])
            return True
        if ev.key == pygame.K_ESCAPE:
            self.close()
            return True
        return False

    def update(self, dt: float) -> None:
        self.t += dt

    def _field(self, key: str, value: str, commit: Callable[[str], str | None], placeholder: str = "") -> TextField:
        """The field for `key`, kept between frames; when it isn't being typed in it shows the saved value."""
        f = self.fields.get(key)
        if f is None:
            f = self.fields[key] = TextField(value, placeholder, commit)
        f.commit, f.placeholder = commit, placeholder
        if not f.focused and not f.error:
            f.value = value
        return f

    def _type_in(self, f: TextField) -> None:
        self._unfocus()
        f.focus(self.t)
        pygame.key.start_text_input()

    def _text(self, surf: pygame.Surface, key: str, rect: pygame.Rect, value: str, commit: Callable[[str], str | None],
              placeholder: str = "", tip: str = "", mono: bool = False, enabled: bool = True,
              prefill: bool = False) -> TextField:
        f = self._field(key, value, commit, placeholder)
        f.prefill = prefill
        f.draw(surf, rect, self.ui, tip or "Click to type; Enter keeps it, Esc puts it back", self.t, enabled, mono)
        if enabled and self.ui.hotspots and self.ui.hotspots[-1].rect == rect:
            self.ui.hotspots[-1].action = partial(self._type_in, f)
        if f.error:
            theme.text(surf, f.error, (rect.x + 2, rect.bottom + 4), theme.ALERT, 12)
        return f

    def _save(self) -> None:
        self.settings.save()

    # ------------------------------------------------------------ drawing

    def draw(self, surf: pygame.Surface, ui: UI, top: int = 200) -> None:
        self.ui = ui
        w, h = surf.get_size()
        x = 84
        self._sliders = []
        # the rail of sections
        y = top
        for s in self.sections:
            r = pygame.Rect(x, y, RAIL_W, 40)
            on = s.key == self.section
            hover = r.collidepoint(ui.mouse)
            if on or hover:
                gfx.draw.rect(surf, theme.BG_PANEL_HI if on else theme.BG_PANEL, r, border_radius=3)
            if on:
                gfx.draw.rect(surf, theme.FRIEND, pygame.Rect(r.x, r.y + 8, 3, r.height - 16), border_radius=1)
            theme.text(surf, s.title.upper(), (r.x + 18, r.y + 12), theme.TEXT if on else theme.TEXT_DIM, 14, "display")
            if s.hotkey:
                theme.text(surf, s.hotkey, (r.right - 14, r.y + 13), theme.TEXT_FAINT, 12, "mono", anchor="topright")
            ui.add(r, partial(self.go, s.key), s.blurb)
            y += 44
        ui.button(surf, pygame.Rect(x, y + 18, 140, 36), "Back", self._back, "Back to the main menu (Esc)", size=13)
        theme.text(surf, "↑ ↓ move between sections", (x, y + 66), theme.TEXT_FAINT, 12)

        # the section, on a card
        px = x + RAIL_W + 28
        card = pygame.Rect(px, top, max(480, min(900, w - px - (60 if w >= 1280 else 28))), max(300, h - top - 40))
        self._right = card.right - 28
        sec = next(s for s in self.sections if s.key == self.section)
        theme.panel(surf, card)
        theme.text(surf, sec.title, (card.x + 28, card.y + 20), theme.TEXT, 22, "display")
        theme.text(surf, sec.blurb, (card.x + 28, card.y + 54), theme.TEXT_DIM, 14)
        gfx.draw.line(surf, theme.BORDER, (card.x + 28, card.y + 84), (card.right - 28, card.y + 84), 1)
        foot = card.bottom - 34
        self._view = pygame.Rect(card.x + 1, card.y + 92, card.width - 2, foot - card.y - 100)
        before = len(ui.hotspots)
        surf.set_clip(self._view)
        y0 = self._view.y + 8 - self.scroll
        end = getattr(self, "_" + self.section)(surf, card.x + 28, y0, card.width - 56)
        surf.set_clip(None)
        self._height = end - (self._view.y + 8 - self.scroll) + 12
        # a control scrolled out of sight can't be clicked
        ui.hotspots[before:] = [hs for hs in ui.hotspots[before:] if self._view.contains(hs.rect)
                                or self._view.colliderect(hs.rect) and hs.rect.height > self._view.height]
        self._sliders = [(r, f) for r, f in self._sliders if self._view.colliderect(r)]
        if self._height > self._view.height:
            frac = self._view.height / self._height
            bar_h = max(30, int(self._view.height * frac))
            room = self._height - self._view.height
            by = self._view.y + int((self._view.height - bar_h) * (self.scroll / room if room else 0))
            gfx.draw.rect(surf, theme.BORDER_HI, pygame.Rect(card.right - 8, by, 3, bar_h), border_radius=1)
        where = "config/officers.toml" if self.section == "officers" else "config/settings.json"
        if self.section == "files":
            where = str(config_dir())
        note_w = theme.text_width(self.note, 12) + 24 if self.note else 0
        theme.text(surf, theme.fit(f"Saved as you change it, in {where}", 12, card.width - 56 - note_w),
                   (card.x + 28, foot + 6), theme.TEXT_FAINT, 12)
        if self.note:
            theme.text(surf, theme.fit(self.note, 12, card.width - 56), (card.right - 28, foot + 6),
                       theme.GOOD if self.note_ok else theme.CAUTION, 12, anchor="topright")

    def _back(self) -> None:
        self._unfocus()
        self.close()

    def _choice(self, surf: pygame.Surface, at: tuple[int, int], *args: Any, **kw: Any) -> int:
        """A row of choices that stays inside the card (the buttons tighten up on a narrow window)."""
        kw["room"] = self._right - at[0]
        return self.ui.choice(surf, at, *args, **kw)

    def _label(self, surf: pygame.Surface, x: int, y: int, label: str) -> int:
        theme.text(surf, label, (x, y + 9), theme.TEXT_DIM, 15)
        return x + LABEL_W

    def _hint(self, surf: pygame.Surface, x: int, y: int, text: str, width: int,
              color: theme.Color = theme.TEXT_FAINT, size: int = 13) -> int:
        """Wrapped words under a control; returns the y below them."""
        line = ""
        for wd in text.split():
            if line and theme.text_width(line + " " + wd, size) > width:
                theme.text(surf, line, (x, y), color, size)
                y += size + 7
                line = wd
            else:
                line = (line + " " + wd).strip()
        if line:
            theme.text(surf, line, (x, y), color, size)
            y += size + 7
        return y

    def _heading(self, surf: pygame.Surface, x: int, y: int, text: str, width: int) -> int:
        theme.text(surf, text.upper(), (x, y + 6), theme.TEXT_FAINT, 12, "display")
        gfx.draw.line(surf, theme.dim(theme.BORDER, 0.8), (x + theme.text_width(text.upper(), 12, "display") + 14, y + 13),
                      (x + width, y + 13), 1)
        return y + 34

    def _level(self, surf: pygame.Surface, x: int, y: int, value: float, set_: Callable[[float], None],
               enabled: bool = True) -> None:
        """A 0 to 100% slider with its value beside it; click or drag."""
        r = pygame.Rect(x + 10, y + 8, max(120, min(260, self._right - x - 190)), 18)
        hit = self.ui.slider(surf, r, value, enabled)
        theme.text(surf, f"{round(value * 100)}%", (r.right + 22, y + 8), theme.TEXT if enabled else theme.TEXT_FAINT,
                   14, "mono")
        if enabled:
            self._sliders.append((hit, lambda px: set_(round(max(0.0, min(1.0, (px - r.x) / r.width)) * 20) / 20)))

    def _hear_x(self, cx: int) -> int:
        """Where a "Hear it" button goes after a `_level` row: after the percentage, inside the card."""
        return min(cx + 360, self._right - 72)

    # ------------------------------------------------------------ Display

    def _display(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        d = self.display
        assert d is not None
        st, pr = self.settings, d.presenter
        choice = st.renderer if st.renderer in RENDERERS else "auto"

        def pick(value: str) -> None:
            st.renderer = value
            self._save()

        cx = self._label(surf, x, y, "Renderer")
        self._choice(surf, (cx, y), [(r, RENDERER_INFO[r][0], RENDERER_INFO[r][1]) for r in RENDERERS], choice, pick)
        y = self._hint(surf, cx, y + 44, RENDERER_INFO[choice][1], width - LABEL_W) + 14
        gpu = pr.name == "gpu"
        cx = self._label(surf, x, y, "Light and glow")
        self.ui.toggle(surf, (cx, y), st.bloom, lambda: d.set_bloom(not st.bloom),
                       "Weapon fire lights the hulls near it, cards cast a soft shadow, and phasers, bolts and blasts "
                       "get a soft halo. Never on text.")
        y = self._hint(surf, cx, y + 44, "Takes effect at once." if gpu else
                       "Takes effect at once. The halo round weapon light needs the graphics card.", width - LABEL_W) + 18

        r = pygame.Rect(x, y, width, 96)
        gfx.draw.rect(surf, theme.BG_INPUT, r, border_radius=4)
        gfx.draw.rect(surf, theme.BORDER, r, 1, border_radius=4)
        theme.text(surf, "NOW", (r.x + 16, r.y + 12), theme.TEXT_FAINT, 11, "display")
        now = f"Graphics card at {pr.density:g}x" if gpu else "Software drawing"
        theme.text(surf, now, (r.x + 16, r.y + 32), theme.GOOD if gpu else theme.TEXT, 16, weight="medium")
        if gpu:
            detail = pr.note.split("(", 1)[-1].rstrip(")")
        elif pr.why:
            detail = f"The graphics card isn't drawing: {pr.why}."
        else:
            detail = "As chosen above."
        self._hint(surf, r.x + 16, r.y + 60, detail, r.width - 32, theme.CAUTION if pr.why else theme.TEXT_DIM)
        y = r.bottom + 18
        if choice != d.started_with:
            theme.text(surf, f"{RENDERER_INFO[choice][0]} takes over when the game starts again.", (x, y + 10),
                       theme.CAUTION, 14)
            self.ui.button(surf, pygame.Rect(x + width - 180, y, 180, 36), "Restart now", d.restart,
                           "Close and reopen the game with the new renderer", size=14, accent=theme.GOOD)
            y += 50
        return y

    # ------------------------------------------------------------ Sound

    def _sound(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        st = self.settings

        def volume(v: float) -> None:
            st.volume = v
            a = self.audio()
            if a is not None:
                a.volume = v

        def mute() -> None:
            st.muted = not st.muted
            a = self.audio()
            if a is not None:
                a.muted = st.muted
            self._save()

        def hum(v: float) -> None:
            st.hum = v
            a = self.audio()
            if a is not None:
                a.hum = v

        cx = self._label(surf, x, y, "Sound")
        self.ui.toggle(surf, (cx, y), not st.muted, mute, "M mutes in battle too")
        y += ROW
        cx = self._label(surf, x, y, "Volume")
        self._level(surf, cx, y, float(st.volume), volume, not st.muted)
        self.ui.button(surf, pygame.Rect(self._hear_x(cx), y + 2, 72, 30), "Hear it", partial(self._hear, "blast", 1.0),
                       "A torpedo blast at this volume", enabled=not st.muted, size=12)
        y += ROW
        cx = self._label(surf, x, y, "Engine hum")
        self._level(surf, cx, y, float(st.hum), hum, not st.muted)
        self.ui.button(surf, pygame.Rect(self._hear_x(cx), y + 2, 72, 30), "Hear it", partial(self._hear, "hum", -1.0),
                       "The ship's hum under a battle, at this level (0: none)", enabled=not st.muted, size=12)
        y += ROW + 8
        y = self._heading(surf, x, y, "Which version", width)
        for name, label, sound in (("phaser", "Phaser", "phaser"), ("torpedo", "Torpedo launch", "launch")):
            cx = self._label(surf, x, y, label)
            current = str(st.sounds.get(name, "d"))
            self._choice(surf, (cx, y), [(v, v.upper(), f"Version {v.upper()}: click to hear it")
                                          for v in "abcd"], current, partial(self._pick_sound, name, sound),
                           enabled=not st.muted, min_width=48)
            y += ROW
        y = self._hint(surf, x, y + 4, "Your own WAV files in config/sounds/ (phaser.wav, torpedo.wav and the others "
                       "listed in the manual's sound page) replace the game's sounds outright.", width) + 4
        return y

    def _hear(self, name: str, level: float) -> None:
        a = self.audio()
        if a is None or self.settings.muted:
            self.note, self.note_ok = "Sound is still being made; try again in a moment.", False
            return
        if level < 0:
            level = float(self.settings.hum)
        a.play(name, time.monotonic(), 0.0, level)

    def _pick_sound(self, name: str, sound: str, variant: str) -> None:
        self.settings.sounds = {**self.settings.sounds, name: variant}
        self._save()
        a = self.audio()
        if a is not None:
            a.choose(sound, variant)
        self._hear(sound, 1.0)

    # ------------------------------------------------------------ Battle

    def _battle(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        st = self.settings

        def speed(v: str) -> None:
            st.speed = float(v)
            self._save()

        def flip(key: str) -> None:
            setattr(st, key, not getattr(st, key))
            self._save()

        cx = self._label(surf, x, y, "Starting speed")
        now = float(st.speed) if float(st.speed) in SPEEDS else 1.0
        self._choice(surf, (cx, y), [(str(s), f"{s:g}x", "How fast battle time runs; + and - change it in battle")
                                      for s in SPEEDS], str(now), speed, min_width=56)
        y = self._hint(surf, cx, y + 44, "The speed a battle starts at. A battle you leave keeps the speed you left "
                       "it at for the next one.", width - LABEL_W) + 10
        cx = self._label(surf, x, y, "Officer chatter")
        self.ui.toggle(surf, (cx, y), bool(st.chatter), partial(flip, "chatter"),
                       "Officers comment on the battle as it goes")
        y = self._hint(surf, cx, y + 42, "Your officers remark on what's happening: hits, kills, a shield going "
                       "down. Their reports and answers to you are never silenced.", width - LABEL_W) + 10
        cx = self._label(surf, x, y, "Map jolt")
        self.ui.toggle(surf, (cx, y), bool(st.jolt), partial(flip, "jolt"),
                       "The map jolts when our ship takes a heavy blow")
        y = self._hint(surf, cx, y + 42, "The map shakes a little when our ship takes a heavy blow.", width - LABEL_W)
        return y + 6

    # ------------------------------------------------------------ Bridge

    def _bridge(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        p = BridgePrefs.from_dict(self.settings.bridge)

        def store() -> None:
            self.settings.bridge = p.to_dict()
            self._save()

        def style(mode: str) -> None:
            p.apply_mode(mode)
            store()

        def part(key: str, value: object) -> None:
            setattr(p, key, value)
            store()

        tips = {"full": "Officers speak in subtitles and read every order back; the wheel; the game eases while you "
                        "type; now and then an officer proposes an order",
                "quiet": "The same tools, but officers speak in the log unless it's urgent, nothing slows down and "
                         "nobody proposes anything unless asked",
                "classic": "The console as Begin had it: acknowledged lines, no subtitles, wheel or proposals"}
        cx = self._label(surf, x, y, "Style")
        self._choice(surf, (cx, y), [(m, m.title(), tips[m]) for m in BRIDGE_STYLES], p.mode, style, min_width=96)
        adjusted = any(getattr(p, k) != v for k, v in BRIDGE_PRESETS[p.mode].items())
        y = self._hint(surf, cx, y + 44, tips[p.mode] + "." + (" You've adjusted it below; pick the style again to "
                                                                "put it back." if adjusted else ""), width - LABEL_W) + 8
        y = self._heading(surf, x, y, "Its parts", width)
        switches = (("wheel", "Command wheel", "Right-click a ship, or press E, for a wheel of orders"),
                    ("map_orders", "Orders on the map", "Standing orders drawn on the map"),
                    ("preview", "Order preview", "A ghost on the map of what the order you're typing will do"))
        choices = (("subtitles", "Subtitles", SUBTITLES, "Officers' words low on the map: all, only urgent ones, or none"),
                   ("readbacks", "Read-backs", READBACKS, "Orders read back by the officer, only in the log, or a plain "
                                                          "acknowledged"),
                   ("focus", "While you type", FOCUS, "The battle eases to a quarter speed, pauses, or carries on"),
                   ("proposals", "Proposals", PROPOSALS, "How often an officer proposes an order (Y makes it so)"))
        for key, label, options, tip in choices:
            cx = self._label(surf, x, y, label)
            self._choice(surf, (cx, y), [(o, o.title(), tip) for o in options], str(getattr(p, key)),
                           partial(part, key), min_width=84)
            y += ROW
        for key, label, tip in switches:
            cx = self._label(surf, x, y, label)
            on = bool(getattr(p, key))
            self.ui.toggle(surf, (cx, y), on, partial(part, key, not on), tip)
            theme.text(surf, tip, (cx + 140, y + 9), theme.TEXT_FAINT, 13)
            y += ROW
        return self._hint(surf, x, y + 4, "In battle, hud bridge full, quiet or classic changes these too, and they're "
                          "kept here.", width)

    # ------------------------------------------------------------ Speaking orders

    def _voice(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        from ..voice.engines import make_engine

        v = VoiceSettings.from_dict(self.settings.voice)

        def store(**kw: object) -> None:
            for k, val in kw.items():
                setattr(v, k, val)
            self.settings.voice = v.to_dict()
            self._save()
            self._ready = None

        if self._ready is None:
            import dataclasses

            self._ready = {}
            for eng in ENGINES:
                try:
                    self._ready[eng] = make_engine(dataclasses.replace(v, engine=eng)).ready()
                except Exception as e:  # noqa: BLE001 - an engine that can't even say is not ready
                    self._ready[eng] = str(e)
        cx = self._label(surf, x, y, "Speaking orders")
        self.ui.toggle(surf, (cx, y), v.enabled, lambda: store(enabled=not v.enabled),
                       "Hold the push-to-talk key in battle and say the order")
        y += ROW
        cx = self._label(surf, x, y, "What hears you")
        for eng in ENGINES:
            on = v.engine == eng
            why = self._ready.get(eng)
            r = pygame.Rect(cx, y, width - LABEL_W, 34)
            self.ui.button(surf, pygame.Rect(cx, y + 5, 24, 24), "●" if on else "", partial(store, engine=eng),
                           f"Use {ENGINE_TITLES[eng]}", active=on, enabled=v.enabled, size=11)
            theme.text(surf, ENGINE_TITLES[eng], (cx + 36, y + 8), theme.TEXT if on else theme.TEXT_DIM, 14,
                       weight="medium" if on else "regular")
            state = "Ready" if why is None else why
            below = theme.para(surf, state, (cx + 250, y + 9), self._right - cx - 250,     # a long reason wraps
                               theme.GOOD if why is None else theme.TEXT_FAINT, 12, 17)
            r.height = max(r.height, below - y + 4)
            if v.enabled:
                self.ui.add(pygame.Rect(cx + 36, y, 200, 34), partial(store, engine=eng), f"Use {ENGINE_TITLES[eng]}")
            y = r.bottom + 2
        y += 10
        cx = self._label(surf, x, y, "Push to talk")
        self._choice(surf, (cx, y), [(k, k.title(), f"Hold {k.title()} to speak" + (" (Option on a Mac)"
                                                                                       if k == "right alt" else ""))
                                      for k in PTT_KEYS], v.key, lambda k: store(key=k), enabled=v.enabled, size=12,
                       min_width=52)
        y += ROW
        if v.engine == "whisper-local":
            cx = self._label(surf, x, y, "Whisper model")
            ex = self._choice(surf, (cx, y), [(m, m.removesuffix(".en"), "tiny is quickest, medium the most accurate")
                                               for m in WHISPER_MODELS], v.model, lambda m: store(model=m),
                                enabled=v.enabled, size=12, min_width=60)
            self.ui.button(surf, pygame.Rect(ex + 8, y, 110, 34), "Download", self._download,
                           "Fetch this model into config/voice/models", enabled=v.enabled and not self._busy, size=12)
            y += ROW
        if v.engine == "whisper-server":
            cx = self._label(surf, x, y, "Server address")
            self._text(surf, "voice.server", pygame.Rect(cx, y, min(420, width - LABEL_W), 34), v.server_url,
                       lambda s: self._server(s, store), "http://127.0.0.1:8080", mono=True)
            y += ROW + 6
        if v.engine == "cloud":
            y = self._hint(surf, x + LABEL_W, y, f"The key is read from {v.cloud_key_env} in the environment; "
                           f"speech goes to {v.cloud_url}.", width - LABEL_W, theme.TEXT_DIM) + 8
        return self._hint(surf, x, y + 4, "Whisper or the Mac hears the words; the console (and your language model) "
                          "understands them. Test the microphone in battle on the voice page (voice).", width)

    def _server(self, url: str, store: Callable[..., None]) -> str | None:
        if not url.startswith(("http://", "https://")):
            return "An address starts with http:// or https://"
        store(server_url=url.rstrip("/"))
        return None

    def _download(self) -> None:
        from ..voice.engines import VoiceError, download_model

        name = VoiceSettings.from_dict(self.settings.voice).model
        self._busy = "download"
        self.note, self.note_ok = f"Downloading the {name} model…", True

        def work() -> None:
            try:
                path = download_model(name, lambda f: setattr(self, "note", f"Downloading the {name} model… {f:.0%}"))
                self.note, self.note_ok = f"The {name} model is ready ({path.stat().st_size / 1e6:.0f} MB).", True
            except (VoiceError, OSError) as e:
                self.note, self.note_ok = str(e), False
            self._busy = ""
            self._ready = None

        threading.Thread(target=work, daemon=True, name="voice-download").start()

    # ------------------------------------------------------------ Language model

    def _llm_set(self, key: str, value: object, character: bool = False) -> None:
        llm = dict(self.settings.llm)
        if character:
            raw = llm.get(models.CHARACTER_KEY)
            ch: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
            if value in (None, ""):
                ch.pop(key, None)
            else:
                ch[key] = value
            llm[models.CHARACTER_KEY] = ch
        elif value in (None, ""):
            llm.pop(key, None)
        else:
            llm[key] = value
        self.settings.llm = llm
        self._save()

    def _provider_rows(self, surf: pygame.Surface, x: int, y: int, width: int, cfg: dict[str, object],
                       character: bool) -> int:
        """Provider, model and address: the same three rows for the main model and the character model."""
        tag = "voices" if character else "model"
        provider = str(cfg.get("provider") or ("ollama" if character else "off")).lower()
        names = [p for p in ("ollama", "anthropic", "openai", "openrouter") if p in models.PROVIDERS]
        options = ([] if character else [("off", "Off", "No model: officers answer with their own lines, and the "
                                                        "console takes console commands")])
        options += [(p, PROVIDER_TITLES[p], {"ollama": "A model on this computer or your network, through Ollama"}
                     .get(p, f"{PROVIDER_TITLES[p]}'s cloud: the key comes from {models.KEY_ENV.get(p, '')}"))
                    for p in names]
        cx = self._label(surf, x, y, "Provider")
        self._choice(surf, (cx, y), options, provider, lambda p: self._llm_set("provider", p, character),
                       size=12, min_width=60)
        y += ROW
        on = provider != "off"
        cx = self._label(surf, x, y, "Model")
        fw = min(420, width - LABEL_W)
        self._text(surf, f"{tag}.model", pygame.Rect(cx, y, fw, 34), str(cfg.get("model") or ""),
                   lambda s: self._llm_set("model", s, character),
                   {"ollama": "lfm3, llama3.2, qwen3…", "anthropic": "claude-…"}.get(provider, "the model's name"),
                   "The model's name, exactly as the provider spells it", mono=True, enabled=on)
        y += ROW
        cx = self._label(surf, x, y, "Address")
        self._text(surf, f"{tag}.base_url", pygame.Rect(cx, y, fw, 34), str(cfg.get("base_url") or ""),
                   lambda s: self._address(s, character), models.DEFAULT_ADDRESS.get(provider, ""),
                   "Leave it empty for the provider's usual address", mono=True, enabled=on)
        y += ROW
        if on:
            key = models.key_problem(provider)
            if key:
                cx = x + LABEL_W
                y = self._hint(surf, cx, y - 6, key + " (keys are never kept in the config folder).",
                               width - LABEL_W, theme.CAUTION) + 6
            elif provider in models.KEY_ENV:
                y = self._hint(surf, x + LABEL_W, y - 6, f"Key found in {models.KEY_ENV[provider]}.", width - LABEL_W,
                               theme.GOOD) + 6
        return y

    def _address(self, url: str, character: bool) -> str | None:
        if url and not url.startswith(("http://", "https://")):
            return "An address starts with http:// or https://"
        self._llm_set("base_url", url.rstrip("/"), character)
        return None

    def _test_row(self, surf: pygame.Surface, x: int, y: int, width: int, character: bool, enabled: bool) -> int:
        busy = self._busy == ("voices" if character else "model")
        self.ui.button(surf, pygame.Rect(x + LABEL_W, y, 150, 36), "Asking…" if busy else "Test it",
                       partial(self._test, character), "Ask the model one question and show its answer here",
                       accent=theme.GOOD, enabled=enabled and not self._busy, size=13)
        return y + ROW

    def _test(self, character: bool) -> None:
        self._unfocus()
        self._busy = "voices" if character else "model"
        llm = dict(self.settings.llm)
        self.note, self.note_ok = "Asking the model… (a local one may need a moment to load)", True

        def work() -> None:
            ok, text, secs = models.ask_once(llm, character)
            self.note = (f"Answered in {secs:.1f}s: “{text[:110]}{'…' if len(text) > 110 else ''}”" if ok
                         else f"No answer: {text[:140]}")
            self.note_ok = ok
            self._busy = ""

        threading.Thread(target=work, daemon=True, name="llm-test").start()

    def _model(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        llm = self.settings.llm
        y = self._provider_rows(surf, x, y, width, llm, False)
        on = str(llm.get("provider") or "off").lower() != "off"
        think = llm.get("think")
        current = "default" if think is None else "on" if think is True else "off" if think is False else str(think)
        cx = self._label(surf, x, y, "Thinking")
        self._choice(surf, (cx, y), [("default", "Model's own", "Whatever the model does by default"),
                                       ("on", "On", "Let a thinking model think first: better, slower"),
                                       ("off", "Off", "Answer at once: quicker, best for small local models")],
                       current if current in ("default", "on", "off") else "default",
                       lambda v: self._llm_set("think", {"on": True, "off": False}.get(v), False), enabled=on,
                       size=12, min_width=60)
        y += ROW
        cx = self._label(surf, x, y, "Plain English")
        mode = str(llm.get("console") or "fallback")
        self._choice(surf, (cx, y), [("off", "Off", "The console takes only console commands"),
                                       ("fallback", "When needed", "The model reads only lines the console doesn't "
                                                                   "understand"),
                                       ("always", "Always", "Every line goes through the model")],
                       mode if mode in models.CONSOLE_MODES else "fallback",
                       lambda v: self._llm_set("console", v), enabled=on, size=12, min_width=60)
        y += ROW
        cx = self._label(surf, x, y, "Debug logs")
        bx = self.ui.toggle(surf, (cx, y), bool(llm.get("log_prompts")), lambda: self._llm_set(
            "log_prompts", not llm.get("log_prompts")), "Every prompt and reply, in config/logs/llm-prompts.log",
            words=("Prompts", "Prompts")).right + 18
        self.ui.toggle(surf, (bx, y), bool(llm.get("log_tokens")), lambda: self._llm_set(
            "log_tokens", not llm.get("log_tokens")), "Token totals per game, in config/logs/llm-tokens.json",
            words=("Tokens", "Tokens"))
        y += ROW
        y = self._test_row(surf, x, y, width, False, on)
        problem = models.problem({k: v for k, v in llm.items() if k != models.CHARACTER_KEY}) if on else None
        if problem:
            y = self._hint(surf, x + LABEL_W, y - 4, f"Officers answer offline until this is fixed: {problem}",
                           width - LABEL_W, theme.CAUTION)
        return self._hint(surf, x, y + 4, "Without a model the game plays exactly as Begin did, and your officers speak "
                          "their own lines. Takes effect in the next battle.", width)

    # ------------------------------------------------------------ Character voices

    def _voices(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        st = self.settings
        raw = st.llm.get(models.CHARACTER_KEY)
        ch: dict[str, object] = dict(raw) if isinstance(raw, dict) else {}
        y = self._hint(surf, x, y, "A second model can speak for the game's characters: enemy captains with more of "
                       "their own language and temper, officers with more colour. The main model still reads your "
                       "orders and judges every hail; if the second one fails, the main one answers.", width,
                       theme.TEXT_DIM, 14) + 12
        has_model = bool(ch.get("model"))
        on = has_model and ch.get("enabled", True) not in (False, "off", "false")
        cx = self._label(surf, x, y, "Character voices")
        self.ui.toggle(surf, (cx, y), on, lambda: self._llm_set("enabled", not on, True),
                       "Off keeps the settings but lets the main model speak for everyone", enabled=has_model)
        if not has_model:
            theme.text(surf, "Give it a model below first", (cx + 120, y + 9), theme.TEXT_FAINT, 13)
        y += ROW
        y = self._provider_rows(surf, x, y, width, ch, True)
        y = self._test_row(surf, x, y, width, True, has_model)
        y = self._heading(surf, x, y, "Who it speaks for", width)

        def flip(key: str, item: str, universe: list[str]) -> None:
            chosen = _words(ch.get(key, list(models.DEFAULT_CHARACTER_FOR) if key == "for" else []))
            keep = [o for o in chosen if o not in universe]
            self._llm_set(key, [u for u in universe if (u in chosen) != (u == item)] + keep, True)

        chosen = _words(ch.get("for", list(models.DEFAULT_CHARACTER_FOR)))
        cx = self._label(surf, x, y, "Speaks for")
        bx = cx
        for name, tip in models.CHARACTER_SITUATIONS.items():
            self.ui.button(surf, pygame.Rect(bx, y, 96, 32), name.capitalize(),
                           partial(flip, "for", name, list(models.CHARACTER_SITUATIONS)), tip, active=name in chosen,
                           enabled=on, size=12)
            bx += 100
        y += ROW
        facs = _words(ch.get("factions", []))
        cx = self._label(surf, x, y, "Captains of")
        bx = cx
        for fac in FACTIONS:
            self.ui.button(surf, pygame.Rect(bx, y, 96, 32), self.content.factions[fac].name,
                           partial(flip, "factions", fac, list(FACTIONS)), "None picked: captains of every race",
                           active=fac in facs, enabled=on, size=12)
            bx += 100
        y += ROW
        only = _words(ch.get("only", []))
        crew = [(oid, short) for oid, short, _ in self._crew()]
        cx = self._label(surf, x, y, "Only this model")
        bx = cx
        for oid, short in crew:
            self.ui.button(surf, pygame.Rect(bx, y, 96, 32), short, partial(flip, "only", oid, [o for o, _ in crew]),
                           "Everything this officer says goes to the second model, whatever is picked above; if it "
                           "fails they answer offline, never through the main model", active=oid in only, enabled=on,
                           size=12)
            bx += 100
        y += ROW
        return self._hint(surf, x, y + 4, "Takes effect in the next battle. Notes for a race or an officer (a line "
                          "added to their prompt) are set with begin --llm character.notes.<who>=...", width)

    # ------------------------------------------------------------ Officers

    def _crew(self) -> list[tuple[str, str, Any]]:
        """(id, short name, profile) for each bridge officer, as the captain's file has them; read when needed."""
        if self._crew_cache is None:
            from ..crew.characters import load_officers

            try:
                profiles = load_officers(traits_file=self._officer_path())
            except Exception:  # noqa: BLE001 - a broken officers file must not break the menu
                profiles = load_officers()
            self._crew_cache = [(o.id, o.name if len(o.name) <= 10 else o.name.split()[0], o) for o in profiles.values()]
        return self._crew_cache

    @staticmethod
    def _officer_path() -> Path:
        return config_dir() / "officers.toml"

    def _officers(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        from ..crew.characters import load_officers

        crew = self._crew()
        if not crew:
            return y
        if self.officer not in [o for o, _, _ in crew]:
            self.officer = crew[0][0]
        bx = x
        for oid, short, _ in crew:
            self.ui.button(surf, pygame.Rect(bx, y, 120, 36), short, partial(self._pick_officer, oid),
                           f"{short}'s settings", active=oid == self.officer, size=14)
            bx += 126
        y += 56
        if self._shipped is None:
            self._shipped = load_officers()
        shipped = self._shipped[self.officer]
        me = next(p for o, _, p in crew if o == self.officer)
        path = self._officer_path()
        mine_all = self._mine.setdefault(self.officer, {k: officer_file.read_field(path, self.officer, k)
                                                         for k in officer_file.EDITABLE})
        fw = width - LABEL_W - 120
        rows = (("name", "Name", shipped.name, "Who they are on your bridge; they answer to the new name"),
                ("rank", "Rank", shipped.rank, "Their rank, as the log and the bridge use it"),
                ("traits", "Traits", ", ".join(shipped.traits), "A few words on how they come across, with commas"),
                ("response_style", "How they speak", shipped.response_style,
                 "How they answer when a language model writes their words: length, tone, register"))
        for key, label, ship_value, tip in rows:
            cx = self._label(surf, x, y, label)
            mine = mine_all[key]
            value = ", ".join(mine) if isinstance(mine, list) else (mine or "")
            self._text(surf, f"officer.{self.officer}.{key}", pygame.Rect(cx, y, fw, 34), value,
                       partial(self._officer_set, self.officer, key), ship_value, tip, prefill=True)
            if mine is not None:
                self.ui.button(surf, pygame.Rect(cx + fw + 10, y + 2, 104, 30), "As shipped",
                               partial(self._officer_set, self.officer, key, ""),
                               f"Take {label.lower()} out of officers.toml, so the game's own is used", size=12)
            y += ROW + 4
        y = self._hint(surf, x + LABEL_W, y - 4, "Grey words are the game's own; click to change them. "
                       "Only the line you change is written.", fw, theme.TEXT_FAINT) + 10
        y = self._heading(surf, x, y, "On the bridge now", width)
        theme.text(surf, f"{me.rank} {me.name}".strip(), (x, y), theme.TEXT, 16, weight="medium")
        y = self._hint(surf, x, y + 26, ", ".join(me.traits) or "No traits", width, theme.TEXT_DIM, 13)
        y = self._hint(surf, x, y, me.response_style, width, theme.TEXT_DIM, 13) + 8
        y = self._hint(surf, x, y, "Personas, backgrounds, interests, quirks and their own lines for any moment live in "
                       "officers.toml too (officers.example.toml shows them all). None of it changes how well an "
                       "officer does the job.", width) + 6
        self.ui.button(surf, pygame.Rect(x, y, 200, 34), "Open config folder", self._open_folder,
                       "Your officers.toml, orders and the rest", size=12)
        return y + 44

    def _pick_officer(self, oid: str) -> None:
        self._unfocus()
        self.officer = oid

    def _officer_set(self, oid: str, key: str, text: str) -> str | None:
        value: officer_file.Value = [t for t in text.split(",")] if key in officer_file.LISTS else text
        try:
            officer_file.set_field(self._officer_path(), oid, key, value)
        except ValueError as e:
            return str(e)
        self._crew_cache = None          # read the file again: the new name shows everywhere
        self._mine.clear()
        f = self.fields.get(f"officer.{oid}.{key}")
        if f is not None and not text:
            f.value, f.error = "", ""
        return None

    # ------------------------------------------------------------ Files

    def _files(self, surf: pygame.Surface, x: int, y: int, width: int) -> int:
        folder = config_dir()
        for name, what in FILES:
            p = folder / name
            yours = p.is_dir() and any(p.iterdir()) if p.is_dir() else p.is_file()
            theme.text(surf, name + ("/" if not name.count(".") else ""), (x, y + 2), theme.TEXT if yours else
                       theme.TEXT_DIM, 14, "mono")
            theme.text(surf, "yours" if yours else "not yet", (x + 170, y + 3), theme.GOOD if yours else theme.TEXT_FAINT,
                       12, "display")
            y = max(y + 34, theme.para(surf, what, (x + 260, y + 3), width - 260, theme.TEXT_DIM, 13, 19) + 12)
        y += 10
        self.ui.button(surf, pygame.Rect(x, y, 220, 36), "Open config folder", self._open_folder,
                       "Show the folder in Finder, Explorer or your file manager", accent=theme.GOOD, size=13)
        y += 54
        keys = self.settings.keys
        if keys:
            y = self._heading(surf, x, y, "Key macros", width)
            for k, line in sorted(keys.items()):
                theme.text(surf, k, (x, y), theme.TEXT, 13, "mono")
                y = theme.para(surf, line, (x + 80, y), width - 80, theme.TEXT_DIM, 13, 20, "mono") + 2
        return self._hint(surf, x, y + 8, "Copy an .example file to start your own. API keys never go in this folder: "
                          "they come only from the environment.", width)

    def _open_folder(self) -> None:
        ok = open_folder(config_dir())
        self.note, self.note_ok = ("Opened the config folder.", True) if ok else (f"It's at {config_dir()}", False)


__all__ = ["SECTIONS", "Section", "SettingsHub"]
