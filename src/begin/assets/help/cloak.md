---
title: Cloaking device
category: Ship systems
order: 3
aliases: cloak, cl, decloak, uncloak, invisible, stealth, hunt, find, locate, find cloaked ship
summary: Hide your ship from enemy sensors, at the cost of energy, until you fire or are hit.
see: tachyon, deflector, scan, chart, tactics
---
Some ships, mostly Romulan and Klingon, carry a cloaking device. While it runs, enemy sensors can't find you at all.

```console
cloak on
cloak off
decloak
```

- `cloak` and `cloak on` engage it; `cloak off`, `decloak` or `uncloak` drop it.
- The cloak costs energy every cycle. If power runs out, it fails.
- **Firing gives you away.** For about a cycle after you fire a phaser or launch a torpedo or probe, the enemy can see you. Being hit shows you for about three cycles.
- Damage to the cloaking device switches it off, and a damaged cloak can't be engaged until it is repaired.

## Hunting a cloaked ship

When an enemy that can cloak vanishes at close range, it has almost certainly cloaked, and it has not gone far. Your science officer says so, with its last fix and heading, and calls it again when it shows (it fires, is hit, or is lit up). Watch for the moment it fires, and have tubes ready. Wide-spread phasers and torpedoes with a big proximity are your best chance.

The simplest way is to ask for it by name:

```console
seven, find the talon
hunt talon
where is the talon?
hunt off
```

- `hunt <ship>` (or `find`, `locate`, or telling an officer to find her) sets your science officer looking. They set up the tachyon detector and the deflector, burst the detector where she should be by now, and keep at it until she shows. Then she is your target, so you can fire at once. Nothing else is fired, and a hunt doesn't lift a cease fire.
- With no ship named, they look for the target you lost, else the nearest ship that has cloaked.
- `where is <ship>?` gives the last fix without starting anything. `hunt off` calls the search off.

Torpedoes still work against a ship you can't see. Fired at her, they fly to her last known position, and the bridge tells you how each shot ended: a hit (and she shows for a moment), a burst with nothing in reach, a round shot down, or a fuse run out with no sign of her.

Better still, ask Spock and Seven for a [[tachyon]] detector torpedo. Its burst lights up cloaked ships long enough to target them. At short range, a [[deflector]] pulse ahead of the bow does the same job without using a tube.
