---
title: Tractor beam
category: Ship systems
order: 1
aliases: tractor, tr, release, tow, tractor beam
summary: Grab a ship within 1,000 units and drag it along with you.
see: dock, tell, transport
---
A tractor beam locks onto a ship within 1,000 units and pulls it along as you move. Use it to drag a crippled ally out of a fight, or to hold an enemy still for your torpedoes and boarding parties.

```console
tractor gorkon
tractor off
release
```

- Only ships fitted with a tractor beam can use one, and it must be working.
- The beam costs energy every cycle you hold it.
- How firmly it holds depends on your tractor's strength against the other ship's mass, and weakens with distance. A heavy ship, or one more than 1,250 units away, breaks free.
- Damage to the tractor, or running out of power, drops the beam.

Allies can tow for you: `tell <ally> tow <ship> to <base>` drags a ship to within 3,000 units of a base and lets it go, close enough to dock. See [[tell]].
