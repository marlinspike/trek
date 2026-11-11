---
title: Who fired what
category: Weapons
order: 9
aliases: colours, colors, legend, weapon colours, weapon colors, beam colours, torpedo colours, intercepted, shot down, fizzle, explosion
summary: Every race's phasers and torpedoes have their own colour, and a torpedo shot down looks different from one that hit.
see: phasers, torpedoes, firecontrol
---
Each nation's weapons have their own colour on the map, so in a crowded fight you can tell at a glance whose beam that was and whose torpedoes are coming. They differ in shape as well, which tells them apart even if two colours look alike to you: Klingon and Orion disruptors fly as bright bolts one after another, and each nation's torpedoes look their own way in flight (a turning photon star for the Federation, a harsh flickering flare for the Klingons, a big wobbling ball of plasma for the Romulans, a flickering bolt for the Orions). A heavier warhead is drawn bigger and brighter.

## Reading a shot

A phaser shot happens in steps, and each one tells you something. First the bank that's firing lights up, so you see which bank it is and which way it bears. Then the beam races out to the target. If the target's shield holds, the beam stops on the shield bubble and splashes across it. If it gets through, it reaches the hull, throws sparks, and gas vents from the breach. A full-charge, tightly focused shot is thicker and brighter than a weak one, and a point-defense shot is a thin, quick flick.

A shield facing that gives way bursts into sparks, and a system hit inside a ship shows as a small blast on her hull a moment later.

An enemy torpedo heading for one of your ships is ringed faintly with its proximity-fuse radius, so you can see how close is too close. If it's off the edge of the map, a red marker at the edge shows where it's coming from.

When your own ship takes a heavy blow the map gives a small jolt. `hud jolt off` keeps it still; `hud jolt on` brings it back.

{{weapon_colors}}

A ship you haven't identified yet fires in plain white: identifying it with sensors also tells you its colours.

## Hit or shot down?

- **A torpedo that went off where it was meant to** (on a ship, or where it was sent to burst) flashes white-hot in the middle and throws out a bright ring in its nation's colour, the size of its blast.
- **A torpedo shot down** by point defense or any other phaser fire gives a small grey star of debris and no flash. If it was already armed it still bursts, so a faint grey ring shows how far the blast reached, but it went off early, wherever the beam caught it.

So a salvo that reaches its target is a string of bright coloured rings around it, and a salvo the enemy's point defense stopped is a scatter of grey stars on the way in.

The colours are set per nation in `content/data/factions.toml` (`colors`: `phaser`, `torpedo`, `phaser_style` and `torpedo_style`), if you would like to change them.
