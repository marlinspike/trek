---
title: Tachyon detector torpedo
category: Ship systems
order: 4
aliases: tachyon, design, collaborate, invent, detector, detector torpedo, cloaked ships, find cloaked
summary: Spock and Seven build a one-off torpedo whose burst lights up cloaked ships.
see: cloak, crew, torpedoes, talking
---
Your sensors can't see a cloaked ship at all. When you think one is out there, Spock and Seven of Nine can work together on a torpedo that carries a tachyon emitter instead of a warhead. Where it bursts, the particles scatter off any cloaked hull nearby and outline it for about 30 cycles, long enough to target it and fire.

## Asking for one

Talk to either of them, in your own words or the console:

```console
spock, there's a cloaked ship out there
seven, can you build a tachyon detector?
design tachyon
```

They take about 20 cycles with a full crew (longer if the ship has lost crew). When it is ready, the round goes into one tube (an empty one if possible; a torpedo already in that tube goes back to the magazine), and they tell you which.

## Firing it

```console
tachyon 45 8000
tachyon gorkon
tachyon
```

- `tachyon <bearing> <range>` bursts it at that point, which is what you want when you only have a guess.
- `tachyon <ship>` bursts it at a ship's last known position, which works well for a ship that just vanished.
- A bare `tachyon` aims at your current target's last position.

The burst lights up every cloaked ship within 6,000 units, and the round can reach about 39,000 units. It does no damage. Once it is fired, the tube goes back to loading ordinary torpedoes, and you can ask for another detector.

## Where to aim

A ship that cloaks keeps moving, so aim a little ahead of where it vanished along its last heading. The science officer reports the last fix when a contact is lost. If you have ships in a fleet, only your ship needs to burst it: every ship on your side sees what the particles reveal.
