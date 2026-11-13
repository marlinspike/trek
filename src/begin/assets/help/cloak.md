---
title: Cloaking device
category: Ship systems
order: 3
aliases: cloak, cl, decloak, uncloak, invisible, stealth, hunt, find, locate, find cloaked ship, sweep, sniff, exhaust, plasma, plasma trail, seeker, seekers, plasma-seeker
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

## Plasma trails

A warp drive that is badly damaged vents plasma while the ship is at warp, and **any** ship's sensors can follow it, cloak or no cloak. A cloaked ship with a leaking drive shows on your map as an **exhaust contact**: a fading rose-coloured wake that ends in a soft, wavering ring where she probably is. It is a rough fix, give or take 700 units, and it never shows her clearly.

It works both ways. If your own drives are hurt, Geordi warns you that you are venting plasma. Repair the drives, or drop below warp 1, and the trail goes cold.

```console
sweep
sweep talon
design seeker
seeker talon
```

- `sweep` (or "Seven, look for exhaust") has your science officer follow plasma much further than usual for a while and report every trail found. `sweep <ship>` looks for one ship's.
- `design seeker` has Seven or Spock build a **plasma-seeker** torpedo. `seeker <ship>` fires it into her trail, and `seeker` alone fires down the nearest one. The torpedo flies the trail itself, every turn she made, and homes on her at the end of it. If the trail goes cold first, it bursts where the trail ends.

## The Enterprise's refit cloak

In the tour, the Enterprise can be refitted with a cloak built from Romulan salvage and made to fire through. When she cloaks, enemy sensors lose her at once, with no lingering track to follow. She can fire without lifting the cloak: the enemy sees the flash where the shot came from and nothing more, so move after every shot. A damaged warp drive still gives her away.

