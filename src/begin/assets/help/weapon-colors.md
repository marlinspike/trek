---
title: Who fired what
category: Weapons
order: 9
aliases: colours, colors, legend, weapon colours, weapon colors, beam colours, torpedo colours, intercepted, shot down, fizzle, explosion
summary: Every race's phasers and torpedoes have their own colour, and a torpedo shot down looks different from one that hit.
see: phasers, torpedoes, firecontrol
---
Each nation's weapons have their own colour on the map, so in a crowded fight you can tell at a glance whose beam that was and whose torpedoes are coming. Klingon and Orion beams are also drawn as a string of bolts rather than a steady line, which tells them apart even if two colours look alike to you.

{{weapon_colors}}

A ship you haven't identified yet fires in plain white: identifying it with sensors also tells you its colours.

## Hit or shot down?

- **A torpedo that went off where it was meant to** (on a ship, or where it was sent to burst) flashes white-hot in the middle and throws out a bright ring in its nation's colour, the size of its blast.
- **A torpedo shot down** by point defense or any other phaser fire gives a small grey star of debris and no flash. If it was already armed it still bursts, so a faint grey ring shows how far the blast reached, but it went off early, wherever the beam caught it.

So a salvo that reaches its target is a string of bright coloured rings around it, and a salvo the enemy's point defense stopped is a scatter of grey stars on the way in.

The colours are set per nation in `content/data/factions.toml` (`colors`: `phaser`, `torpedo` and `phaser_style`), if you would like to change them.
