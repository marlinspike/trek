---
title: The bridge
category: Getting started
order: 5
aliases: bridge setting, hud bridge, subtitles, readback, readbacks, focus, tactical focus, wheel, command wheel, proposals, proposal, make it so, preview, completion, tab, pointing, him, her, that one, map orders, full, quiet, classic
summary: Giving orders the way a captain does: officers read them back, a wheel on every ship, proposals you accept with Y.
see: console, orders, alert, styles, voice-orders, crew
---
Every way of giving an order still works: keys, clicks, the console. The bridge adds to them.

## Readbacks and subtitles

Every order you give through the console (and the wheel, a proposal or your voice, which all go through it) is read back by the officer at that station, in a sentence built from the order itself: *"Course 090, warp 6."*, *"Firing all phasers at the Hydra, aiming for her shields."* If what you hear back isn't what you meant, say it again.

Officers' words show low on the map, one voice at a time, with their station's mark: helm a chevron, tactical a diamond, engineering a hexagon, science a ring. The log keeps every word in two columns: **Bridge** (who said what) and **Computer** (everything else).

## The command wheel

Right-click a ship (or press `E` for your target) and pick an order. Eight slices, always in the same places for an enemy: Phasers, Torpedoes, Disable, Close to, Hail, Board, Elude, Target. Rest on a slice with a `›` for its second ring. Keys `1`-`8` pick a slice too. Your own ships and your own ship have wheels of their own.

Every slice is a console line, and the log shows it, so the wheel teaches the console. Right-clicking empty space still steers; Shift+right-click still pursues. Make the wheel your own in `config/wheel.toml` (copy it from the game's `content/data/wheel.toml`).

## While you type

The battle eases to a quarter speed while you type an order (**tactical focus**: an amber edge, the sound steps back), and runs again as soon as you press Enter, or after eight seconds without a key. Under the console, a faint line says what Enter would do, and the map shows a ghost of it: the course, the ship. `Tab` finishes the word you're typing: a command, a ship, an officer, a named order.

Point and say: with the mouse on a ship, "fire at **her**", "pursue **him**" or "scan **that one**" mean that ship. The log shows the line with her name in it.

## Proposals

Now and then an officer at a station you're running proposes an order: *"Torpedoes inbound, Captain. Evasive manoeuvres?"* `Y` makes it so, `N` belays it, or let it lapse. While you type, only an urgent one shows, as a chip above the console: `Ctrl+Y`. They're rare: one at a time, an officer at most once a minute.

## The Bridge setting

| Command | What it does |
|---|---|
| `hud bridge full` | everything above (the default) |
| `hud bridge quiet` | readbacks in the log only, subtitles only when urgent, no focus, no proposals |
| `hud bridge classic` | the console as it was: "acknowledged", nothing more |
| `hud wheel on\|off` · `hud focus slow\|pause\|off` · `hud proposals often\|rarely\|off` | one part at a time |
| `hud subtitles all\|urgent\|off` · `hud readbacks voiced\|log\|off` · `hud orders on\|off` · `hud preview on\|off` | |

The setting is kept in `config/settings.json`.
