"""The engineering docs keep up with the powers in the game, not only the manual.

docs/REFERENCE.md is written by hand, so when the Borg arrived nobody added them to its AI table and they were
missing for weeks. These fail when a faction in factions.toml has no row in REFERENCE.md's nation table, when a
row's numbers drift from the data, or when a power Begin never had is not explained in DEVIATIONS.md."""

from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parent.parent / "docs"
BEGIN_NATIONS = {"federation", "klingon", "romulan", "orion"}     # the four powers of the original game


def _rows() -> dict[str, list[float]]:
    text = (DOCS / "REFERENCE.md").read_text(encoding="utf-8")
    rows: dict[str, list[float]] = {}
    for line in text.splitlines():
        m = re.match(r"^\|\s*([A-Za-z][\w ]*?)(?:\s*\[E\])?\s*\|((?:\s*[\d.]+\s*\|){6})\s*$", line)
        if m:
            rows[m.group(1).strip()] = [float(x) for x in m.group(2).split("|") if x.strip()]
    return rows


def test_every_faction_has_a_row_in_the_reference_ai_table(content) -> None:  # type: ignore[no-untyped-def]
    rows = _rows()
    missing = [f.name for f in content.factions.values() if f.name not in rows]
    assert not missing, f"docs/REFERENCE.md §14 has no AI row for: {', '.join(missing)}"
    for f in content.factions.values():
        d = f.dogma
        want = [d.aggression, d.bravery, d.loyalty, d.fanaticism, d.boarding, d.deviation]
        assert rows[f.name] == want, f"REFERENCE.md row for {f.name} {rows[f.name]} differs from factions.toml {want}"


def test_every_power_begin_never_had_is_explained_in_deviations(content) -> None:  # type: ignore[no-untyped-def]
    text = (DOCS / "DEVIATIONS.md").read_text(encoding="utf-8")
    heads = [ln for ln in text.splitlines() if ln.startswith("#")]
    missing = [f.long_name or f.name for f in content.factions.values() if f.id not in BEGIN_NATIONS
               and not any(f.name in h for h in heads)]
    assert not missing, f"docs/DEVIATIONS.md has no section for: {', '.join(missing)}"
