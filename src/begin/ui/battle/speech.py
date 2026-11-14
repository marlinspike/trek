"""The officers' spoken voices in battle: what they say aloud, and the Bridge voices page [E].

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state.

Every line an officer says aloud (the session's `Voice` news), every proposal and every urgent word from the
computer goes to the `Speaker`, which decides from the settings what is heard. The page (Esc, then Bridge voices,
or `speak`) turns voices on or off, sets what is spoken, how loud and how quick, and recasts any officer; the main
menu's Settings has the same controls. Everything is kept in config/settings.json under "speech".
"""

from __future__ import annotations

from functools import partial
from typing import TYPE_CHECKING

import pygame

from ...speech import CAST, OFFICERS, RACES, SPEAK, SPEAK_TITLES, Speaker, SpeechSettings, choices
from ...speech.settings import RATE_MAX, RATE_MIN
from .. import theme
from .state import SceneState

if TYPE_CHECKING:
    from ..battle_scene import BattleScene

PARTS = {"spock": "spock", "worf": "worf", "geordi": "geordi", "la forge": "geordi", "laforge": "geordi",
         "seven": "seven", "sulu": "sulu", "chekov": "chekov", "doctor": "doctor", "computer": "computer",
         "klingon": "klingon", "klingons": "klingon", "romulan": "romulan", "romulans": "romulan", "orion": "orion",
         "orions": "orion", "borg": "borg"}


class SpeechMixin(SceneState):
    def _speech_setup(self: BattleScene, speaker: Speaker | None) -> None:
        self.speaker: Speaker = speaker if speaker is not None else Speaker.silent()
        self._spoken_proposal: object = None

    @property
    def speech(self: BattleScene) -> SpeechSettings:
        return self.speaker.settings

    def _speech_save(self: BattleScene, s: SpeechSettings) -> None:
        self.speaker.store.clear()
        self.speaker.store.update(s.to_dict())

    # ------------------------------------------------------------ what is said aloud

    def _speak(self: BattleScene, text: str, officer: str | None = None, faction: str | None = None,
               kind: str = "report", urgent: bool = False) -> None:
        if not self.audio.muted:            # M hushes the bridge with everything else
            self.speaker.say(text, officer, faction, kind, urgent)

    def _speak_proposal(self: BattleScene) -> None:
        """A new proposal is said aloud by the officer who makes it."""
        p = self.proposal
        if p is self._spoken_proposal:
            return
        self._spoken_proposal = p
        if p is not None:
            self._speak(p.text, p.officer, kind="proposal", urgent=p.urgent)

    # ------------------------------------------------------------ `speak`

    def speech_command(self: BattleScene, val: object) -> None:
        words = str(val or "").strip().lower().split()
        if not words:
            self.overlay = "speech"
            return
        s = self.speech
        head, rest = words[0], " ".join(words[1:])
        if head in ("on", "off"):
            s.enabled = head == "on"
            if not s.enabled:
                self.speaker.stop()
        elif head in SPEAK:
            s.speak, s.enabled = head, True
        elif head in ("hush", "quiet", "stop"):
            self.speaker.stop()
            return
        elif head == "volume" and _number(rest) is not None:
            n = _number(rest) or 0.0
            s.volume = max(0.0, min(1.0, n / 100 if n > 1 else n))
        elif head in ("rate", "pace", "speed") and _number(rest) is not None:
            n = _number(rest) or 1.0
            s.rate = max(RATE_MIN, min(RATE_MAX, n / 100 if n > 3 else n))
        elif head == "captains" and rest in ("on", "off"):
            s.captains = rest == "on"
        elif head == "hear" and rest in PARTS:
            self.speaker.hear(PARTS[rest])
            return
        else:
            self._log("speak · speak on|off · speak all|orders|urgent · speak volume 0-100 · speak rate 70-140 · "
                      "speak captains on|off · speak hear <officer> · speak hush", theme.CAUTION)
            return
        self._speech_save(s)
        self._log(self.speech_summary(), theme.TEXT_DIM)

    def speech_summary(self: BattleScene) -> str:
        s = self.speech
        if not s.enabled:
            return "Officers' voices off. 'speak on' brings them back."
        why = self.speaker.problem()
        state = "" if why is None else f" ({why})"
        return (f"Officers' voices: {SPEAK_TITLES[s.speak].lower()}, volume {s.volume * 100:.0f}, "
                f"pace {s.rate:.2f}×{state}.")

    # ------------------------------------------------------------ the page

    def _recast(self: BattleScene, part: str, step: int) -> None:
        voices = choices(part, self.speaker.voices())
        if not voices:
            return
        now = self.speaker.voice_for(part)
        i = voices.index(now) if now in voices else -1
        s = self.speech
        s.cast[part] = voices[(i + step) % len(voices)]
        self._speech_save(s)
        self.speaker.hear(part)

    def _uncast(self: BattleScene, part: str) -> None:
        s = self.speech
        s.cast.pop(part, None)
        self._speech_save(s)
        self.speaker.hear(part)

    def _set_speech(self: BattleScene, **kw: object) -> None:
        s = self.speech
        for k, v in kw.items():
            setattr(s, k, v)
        self._speech_save(s)
        if not s.enabled:
            self.speaker.stop()

    def _speech_page(self: BattleScene, surf: pygame.Surface) -> None:
        s = self.speech
        w, h = surf.get_size()
        r = self._modal(surf, min(820, w - 40), min(520, h - 40), "Bridge voices")
        x, y = r.x + 24, r.y + 40
        why = self.speaker.problem() if s.enabled else None
        intro = "Your officers speak their readbacks, reports and proposals aloud, each in a voice cast for them."
        theme.text(surf, theme.fit(intro, 12, r.width - 48), (x, y), theme.TEXT_DIM, 12)
        y += 20
        engine = self.speaker.engine.title if self.speaker.engine is not None else ""
        state = "ready" if why is None else why
        theme.text(surf, theme.fit(f"{engine}: {state}" if engine else state, 12, r.width - 48), (x, y),
                   theme.GOOD if why is None else theme.CAUTION, 12)
        y += 28
        self.ui.button(surf, pygame.Rect(x, y, 110, 26), "Voices on" if s.enabled else "Voices off",
                       lambda: self._set_speech(enabled=not s.enabled), "Turn the officers' voices on or off",
                       active=s.enabled, accent=theme.GOOD, size=12)
        bx = x + 124
        for mode in SPEAK:
            label = SPEAK_TITLES[mode]
            bw = theme.text_width(label, 11) + 20
            self.ui.button(surf, pygame.Rect(bx, y, bw, 26), label, partial(self._set_speech, speak=mode, enabled=True),
                           {"all": "Every line an officer says aloud", "orders": "Readbacks, proposals and warnings",
                            "urgent": "Only warnings"}[mode], active=s.speak == mode, size=11)
            bx += bw + 4
        self.ui.button(surf, pygame.Rect(bx + 10, y, 130, 26), "Captains speak" if s.captains else "Captains silent",
                       lambda: self._set_speech(captains=not s.captains), "Enemy captains speak their hails too",
                       active=s.captains, size=11)
        y += 36
        for label, key, value, step, lo, hi, shown in (
                ("Volume", "volume", s.volume, 0.1, 0.0, 1.0, f"{s.volume * 100:.0f}%"),
                ("Pace", "rate", s.rate, 0.05, RATE_MIN, RATE_MAX, f"{s.rate:.2f}×")):
            theme.text(surf, label, (x, y + 4), theme.TEXT_DIM, 12)
            self.ui.button(surf, pygame.Rect(x + 70, y, 26, 24), "−",
                           partial(self._set_speech, **{key: round(max(lo, value - step), 2)}), f"Less {label.lower()}",
                           size=12)
            theme.text(surf, shown, (x + 136, y + 4), theme.TEXT, 13, "mono", anchor="midtop")
            self.ui.button(surf, pygame.Rect(x + 176, y, 26, 24), "+",
                           partial(self._set_speech, **{key: round(min(hi, value + step), 2)}), f"More {label.lower()}",
                           size=12)
            x += 260
        x = r.x + 24
        y += 40
        col_w = (r.width - 48 - 20) // 2
        for i, parts in enumerate((OFFICERS, RACES)):
            cx, cy = x + i * (col_w + 20), y
            theme.text(surf, "YOUR OFFICERS" if i == 0 else "ENEMY CAPTAINS", (cx, cy), theme.TEXT_FAINT, 11,
                       weight="semibold")
            cy += 22
            for part in parts:
                if cy > r.bottom - 60:
                    break
                cy = self._cast_row(surf, part, cx, cy, col_w)
        theme.text(surf, "Esc closes · ◀ ▶ recast and play a line · kept in config/settings.json (\"speech\") · "
                         "also in Settings on the main menu", (x, r.bottom - 28), theme.TEXT_FAINT, 11)

    def _cast_row(self: BattleScene, surf: pygame.Surface, part: str, x: int, y: int, width: int) -> int:
        cast = CAST[part]
        name = self.crew.officer_name(part) if part in OFFICERS and part != "computer" else cast.title
        theme.text(surf, theme.fit(name, 13, 120, weight="medium"), (x, y + 3), theme.TEXT, 13, weight="medium")
        voice = self.speaker.voice_for(part) or "default"
        mine = part in self.speech.cast
        vx = x + 126
        vw = max(80, width - 126 - 92)
        self.ui.button(surf, pygame.Rect(vx, y, 22, 22), "◀", partial(self._recast, part, -1), "The voice before", size=10)
        theme.text(surf, theme.fit(voice, 12, vw - 52), (vx + 26 + (vw - 52) // 2, y + 4),
                   theme.CREW if mine else theme.TEXT_DIM, 12, anchor="midtop")
        self.ui.button(surf, pygame.Rect(vx + vw - 22, y, 22, 22), "▶", partial(self._recast, part, 1), "The voice after",
                       size=10)
        self.ui.button(surf, pygame.Rect(vx + vw + 6, y, 48, 22), "Hear", partial(self.speaker.hear, part),
                       f"{cast.title}: {cast.manner}", size=11)
        if mine:
            self.ui.button(surf, pygame.Rect(vx + vw + 58, y, 26, 22), "↺", partial(self._uncast, part),
                           "Back to the voice cast for them", size=11)
        return y + 26


def _number(text: str) -> float | None:
    try:
        return float(text.strip().rstrip("%×x"))
    except ValueError:
        return None


__all__ = ["PARTS", "SpeechMixin"]
