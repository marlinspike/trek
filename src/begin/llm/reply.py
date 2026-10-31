"""Reading what a language model said: its JSON answer, or whatever it managed instead.

Small local models wrap JSON in prose or code fences, repeat it, cut it off, or copy the command
syntax's brackets literally. These helpers recover the spoken words and the commands from all of that.
They are shared by the officers, the hails and the console translator.
"""

from __future__ import annotations

import json
import re


def clean_command(line: str) -> str:
    """Small models copy the syntax notation literally: 'target derango[weapons]', 'fire all phasers [spread 45]'."""
    line = re.sub(r"[\[\]<>`]", " ", line)
    return " ".join(line.split()).strip(" .;")


_SAY = re.compile(r'"say"\s*:\s*"((?:\\.|[^"\\])*)', re.S)


NUDGE = ("Your last answer had nothing to say aloud. Reply now, in character, with at least one short sentence "
         "in \"say\".")


def first_object(text: str) -> dict[str, object] | None:
    """The first JSON object in a model's answer, even with prose, code fences or a second copy around it."""
    dec = json.JSONDecoder()
    i = text.find("{")
    while i >= 0:
        try:
            data, _ = dec.raw_decode(text, i)
        except ValueError:
            data = None
        if isinstance(data, dict):
            return data
        i = text.find("{", i + 1)
    return None


def spoken(text: str) -> str:
    """What to show as speech from an answer that may be JSON, broken JSON, or plain words."""
    data = first_object(text)
    if data is not None:
        return str(data.get("say", "")).strip()
    m = _SAY.search(text)                       # broken or cut-off JSON: rescue the words, never show the braces
    if m:
        try:
            return str(json.loads('"' + m.group(1).rstrip("\\") + '"')).strip()
        except ValueError:
            return m.group(1).replace('\\"', '"').strip()
    if "{" in text and '"' in text and ":" in text:
        text = text[:text.find("{")]           # some other JSON-ish tail: keep only the words before it
    return text.strip().strip("`").strip().strip('"').strip()


def parse_reply(text: str) -> tuple[str, list[str]]:
    """The model's JSON reply → (spoken text, commands). Plain text is accepted as speech."""
    data = first_object(text)
    if data is None:
        return spoken(text), []
    cmds = data.get("commands") or []
    if not isinstance(cmds, list):
        cmds = [cmds]
    return str(data.get("say", "")).strip(), [c for c in (clean_command(str(x)) for x in cmds) if c][:4]


__all__ = ["NUDGE", "clean_command", "first_object", "parse_reply", "spoken"]
