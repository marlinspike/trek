"""Speaking orders in battle, and the voice page [E].

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state.

Hold the push-to-talk key (Right Alt, which is Option on a Mac; `voice key` changes it), say the order and let
go. A mic pill by the console shows the level while it listens and "hearing" while the engine works. What was
heard runs exactly as if typed, the officer reads it back, and the log shows the words. If the console
can't make sense of them and there's no language model to ask, they wait in the console to be fixed: a
misheard order is never guessed at.

`voice` opens the voice page: which engine hears, whether it's ready and what it still needs, the
push-to-talk key, a Test button (three seconds of speech, then what was heard and how long it took), and
Download for the local Whisper model. Everything is kept in config/ (settings.json "voice", config/voice/).
"""

from __future__ import annotations

import queue
import threading
import time
from typing import TYPE_CHECKING

import pygame

import dataclasses

from ...voice.engines import VoiceError, download_model, make_engine
from ...voice.recorder import Recorder
from ...voice.settings import ENGINE_WORDS, ENGINES, MODELS, PTT_KEYS, VoiceSettings
from .. import theme
from .state import SceneState
from .. import gfx

if TYPE_CHECKING:
    from ..battle_scene import BattleScene

KEYS = {"right alt": pygame.K_RALT, "right ctrl": pygame.K_RCTRL, "right shift": pygame.K_RSHIFT,
        "caps lock": pygame.K_CAPSLOCK, "f13": pygame.K_F13, "backslash": pygame.K_BACKSLASH}
TEST_SECONDS = 3.0
ENGINE_TITLES = {"mac": "Mac speech (on this Mac)", "whisper-local": "Whisper on this computer",
                 "whisper-server": "Whisper server (this computer or the network)", "cloud": "Cloud transcription"}


class VoiceMixin(SceneState):
    def _voice_setup(self: BattleScene, store: dict[str, object] | None) -> None:
        self.voice_store: dict[str, object] = store if store is not None else {}
        self.vset: VoiceSettings = VoiceSettings.from_dict(self.voice_store)
        self.recorder: Recorder | None = None
        self.voice_state: str = "idle"          # idle | listening | hearing | testing
        self.voice_note: str = ""                # the voice page's last word (a test result, a download)
        self._voice_q: queue.Queue[tuple[str, str, float]] = queue.Queue()
        self._test_until: float = 0.0

    def _voice_save(self: BattleScene) -> None:
        self.voice_store.clear()
        self.voice_store.update(self.vset.to_dict())

    def ptt_key(self: BattleScene) -> int:
        return KEYS.get(self.vset.key, pygame.K_RALT)

    def _voice_hints(self: BattleScene) -> list[str]:
        names = [s.name for s in self.obs.own_ships()]
        names += [c.label.split(" (")[0] for c in self.obs.contacts().values() if c.identified]
        names += [o.name for o in self.session.officers().values()]
        return list(dict.fromkeys(names))

    # ------------------------------------------------------------ push to talk

    def _voice_event(self: BattleScene, ev: pygame.event.Event) -> bool:
        if not self.vset.enabled or ev.type not in (pygame.KEYDOWN, pygame.KEYUP) or ev.key != self.ptt_key():
            return False
        if ev.type == pygame.KEYDOWN and self.voice_state == "idle":
            self.recorder = self.recorder or Recorder()
            if self.recorder.start():
                self.voice_state = "listening"
                self.focus_keystroke()
            else:
                self.toast = (self.recorder.error or "No microphone.", theme.CAUTION, 4.0)
        elif ev.type == pygame.KEYUP and self.voice_state == "listening":
            self._hear(self.recorder.stop() if self.recorder is not None else None, "order")
        return True

    def _hear(self: BattleScene, wav: bytes | None, kind: str) -> None:
        if wav is None:
            self.voice_state = "idle"
            if kind == "test":
                self.voice_note = "Nothing heard: speak while the test runs."
            return
        self.voice_state = "hearing"
        engine = make_engine(self.vset)
        hints = self._voice_hints()
        started = time.monotonic()

        def work() -> None:
            try:
                text = engine.transcribe(wav, hints)
                self._voice_q.put((kind, text, time.monotonic() - started))
            except VoiceError as e:
                self._voice_q.put(("error", str(e), 0.0))
            except Exception as e:  # noqa: BLE001 - an engine failing must never stop a battle
                self._voice_q.put(("error", f"{type(e).__name__}: {e}", 0.0))

        threading.Thread(target=work, daemon=True, name="voice").start()

    def _voice_poll(self: BattleScene) -> None:
        if self.voice_state == "testing" and time.monotonic() >= self._test_until:
            self._hear(self.recorder.stop() if self.recorder is not None else None, "test")
        while True:
            try:
                kind, text, secs = self._voice_q.get_nowait()
            except queue.Empty:
                return
            self.voice_state = "idle"
            if kind == "error":
                self.voice_note = text
                self._log(f"Voice: {text}", theme.CAUTION)
                self.toast = (text, theme.CAUTION, 4.0)
            elif kind == "test":
                self.voice_note = f'Heard "{text}" in {secs:.1f} s.' if text else "Nothing was heard. Speak up, or try another engine."
            elif kind == "download":
                self.voice_note = text
                self._log(text, theme.GOOD)
            elif not text:
                self.toast = ("Didn't hear an order.", theme.TEXT_DIM, 2.0)
            else:
                self.spoken(text)

    def spoken(self: BattleScene, text: str) -> None:
        """Words heard from the captain: run them as typed, unless nothing could make sense of them."""
        line = self._with_pointing(text, self.pointed_ship())
        err = self.session.understood(line)
        if err is not None:
            self.type_line(line)        # never guessed at: it waits to be fixed
            self.toast = (f'Heard "{text}": {err} Fix it and press Enter.', theme.CAUTION, 5.0)
            return
        self._log(f'  heard: "{text}"', theme.TEXT_DIM, channel="bridge")
        self.run_console(line)

    # ------------------------------------------------------------ `voice ...`

    def voice_command(self: BattleScene, val: object) -> None:
        words = str(val or "").strip().lower().split()
        v = self.vset
        if not words:
            self.overlay = "voice"
            return
        head, rest = words[0], " ".join(words[1:])
        if head in ("on", "off"):
            v.enabled = head == "on"
        elif head == "engine" and rest in ENGINE_WORDS or head in ENGINE_WORDS and not rest:
            v.engine = ENGINE_WORDS[rest if head == "engine" else head]
        elif head == "server" and rest:
            v.server_url = rest if rest.startswith("http") else f"http://{rest}"
        elif head == "model" and rest in MODELS:
            v.model = rest
        elif head == "key" and rest in PTT_KEYS:
            v.key = rest
        elif head == "test":
            self.voice_test()
            return
        elif head == "download":
            self.voice_download()
            return
        else:
            self._log("voice · voice on|off · voice engine mac|local|server|cloud · voice server <url> · "
                      f"voice model {'|'.join(MODELS)} · voice key {'|'.join(PTT_KEYS)} · voice test · voice download",
                      theme.CAUTION)
            return
        self._voice_save()
        self._log(self.voice_summary(), theme.TEXT_DIM)

    def voice_summary(self: BattleScene) -> str:
        v = self.vset
        if not v.enabled:
            return "Voice off. 'voice on' brings it back."
        why = make_engine(v).ready()
        state = "ready" if why is None else why
        return f"Voice: {ENGINE_TITLES[v.engine]}, {state}. Hold {v.key.title()} and speak an order."

    def voice_test(self: BattleScene) -> None:
        self.recorder = self.recorder or Recorder()
        if self.voice_state != "idle":
            return
        if not self.recorder.start():
            self.voice_note = self.recorder.error or "No microphone."
            return
        self.voice_state = "testing"
        self._test_until = time.monotonic() + TEST_SECONDS
        self.voice_note = "Listening for three seconds: say an order."

    def voice_download(self: BattleScene) -> None:
        name = self.vset.model
        self.voice_note = f"Downloading the {name} model…"

        def work() -> None:
            try:
                path = download_model(name, lambda f: setattr(self, "voice_note", f"Downloading the {name} model… {f:.0%}"))
                self._voice_q.put(("download", f"The {name} model is ready ({path.stat().st_size / 1e6:.0f} MB).", 0.0))
            except VoiceError as e:
                self._voice_q.put(("error", str(e), 0.0))

        threading.Thread(target=work, daemon=True, name="voice-download").start()

    # ------------------------------------------------------------ drawing

    def _draw_mic(self: BattleScene, surf: pygame.Surface) -> None:
        st = self.voice_state
        if st not in ("listening", "hearing"):
            return
        r = pygame.Rect(0, 0, 210, 26)
        r.bottomright = (self.console_rect.right - 4, self.console_rect.y - 4)
        gfx.draw.rect(surf, theme.BG_PANEL_HI, r, border_radius=13)
        gfx.draw.rect(surf, theme.ALERT if st == "listening" else theme.FRIEND, r, 1, border_radius=13)
        cx, cy = r.x + 16, r.centery
        if st == "listening":
            lv = self.recorder.level if self.recorder is not None else 0.0
            gfx.draw.circle(surf, theme.ALERT, (cx, cy), 5)
            gfx.draw.circle(surf, theme.dim(theme.ALERT, 0.6), (cx, cy), int(7 + 6 * lv), 1)
            theme.text(surf, f"Listening · let go of {self.vset.key.title()}", (r.x + 30, r.y + 5), theme.TEXT, 12)
        else:
            beat = 0.5 + 0.5 * __import__("math").sin(time.monotonic() * 6)
            gfx.draw.circle(surf, theme.mix(theme.BG, theme.FRIEND, beat), (cx, cy), 5)
            theme.text(surf, "Hearing…", (r.x + 30, r.y + 5), theme.TEXT_DIM, 12)

    def _voice_page(self: BattleScene, surf: pygame.Surface) -> None:
        v = self.vset
        r = self._modal(surf, 760, 410, "Voice")
        x, y = r.x + 24, r.y + 40
        theme.text(surf, "Hold the push-to-talk key, say an order, let go. What's heard runs as if typed, and is read back.",
                   (x, y), theme.TEXT_DIM, 12)
        y += 30
        for eng in ENGINES:
            why = make_engine(dataclasses.replace(v, engine=eng)).ready()
            on = v.engine == eng
            self.ui.button(surf, pygame.Rect(x, y, 26, 22), "●" if on else "", lambda e=eng: self.voice_command(f"engine {e}"),
                           f"Use {ENGINE_TITLES[eng]}", active=on, size=11)
            theme.text(surf, ENGINE_TITLES[eng], (x + 38, y + 3), theme.TEXT if on else theme.TEXT_DIM, 13,
                       weight="medium" if on else "regular")
            state = "ready" if why is None else why
            if why is None and eng == "whisper-server":
                state = "address set: Test checks the server answers"
            theme.text(surf, state, (x + 360, y + 4), theme.GOOD if why is None else theme.TEXT_FAINT, 11)
            y += 30
        y += 6
        theme.text(surf, "Push to talk", (x, y + 4), theme.TEXT_DIM, 12)
        bx = x + 120
        for k in PTT_KEYS:
            w = theme.text_width(k.title(), 11) + 16
            self.ui.button(surf, pygame.Rect(bx, y, w, 22), k.title(), lambda kk=k: self.voice_command(f"key {kk}"),
                           f"Hold {k.title()} to speak", active=v.key == k, size=11)
            bx += w + 4
        y += 34
        if v.engine == "whisper-local":
            theme.text(surf, "Model", (x, y + 4), theme.TEXT_DIM, 12)
            bx = x + 120
            for m in MODELS:
                w = theme.text_width(m, 11) + 16
                self.ui.button(surf, pygame.Rect(bx, y, w, 22), m, lambda mm=m: self.voice_command(f"model {mm}"),
                               "tiny is quickest, medium the most accurate", active=v.model == m, size=11)
                bx += w + 4
            self.ui.button(surf, pygame.Rect(bx + 10, y, 100, 22), "Download", self.voice_download,
                           "Fetch this model into config/voice/models", size=11)
            y += 34
        if v.engine == "whisper-server":
            theme.text(surf, f"Server  {v.server_url}   (voice server <address> changes it)", (x, y + 4), theme.TEXT_DIM, 12)
            y += 30
        if v.engine == "cloud":
            theme.text(surf, f"Key from ${v.cloud_key_env} · {v.cloud_url}", (x, y + 4), theme.TEXT_DIM, 12)
            y += 30
        self.ui.button(surf, pygame.Rect(x, y, 120, 28), "Test" if self.voice_state == "idle" else "Listening…",
                       self.voice_test, "Speak for three seconds and see what is heard", accent=theme.GOOD, size=12)
        self.ui.button(surf, pygame.Rect(x + 130, y, 120, 28), "Voice on" if not v.enabled else "Voice off",
                       lambda: self.voice_command("off" if v.enabled else "on"), "Turn speaking orders on or off", size=12)
        theme.text(surf, self.voice_note, (x + 270, y + 6), theme.TEXT, 13)
        y += 44
        theme.text(surf, "Ollama and other chat models don't hear speech; Whisper or the Mac hears, then the console "
                         "(and your language model) understands.", (x, y), theme.TEXT_FAINT, 11)
        theme.text(surf, "Esc closes · settings are kept in config/settings.json, models in config/voice/",
                   (x, r.bottom - 28), theme.TEXT_FAINT, 11)


__all__ = ["VoiceMixin"]
