---
title: Cloaking device
category: Ship systems
order: 3
aliases: cloak, cl, decloak, uncloak, invisible, stealth, hunt, find, locate, find cloaked ship, sweep, sniff, exhaust, plasma, plasma trail, seeker, seekers, plasma-seeker, strike, sweep and strike, sweepstrike, kill chain, firing solution
summary: Hide your ship from enemy sensors, at the cost of energy, until you fire or are hit.
see: tachyon, deflector, scan, chart, tactics
---
Every Romulan ship carries a cloaking device, and so does the Enterprise after her refit in one tour. While it runs, enemy sensors can't find the ship at all.

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

## Sweep and strike

The whole kill chain in one order. When a cloaked ship leaks plasma, tell your science officer to **sweep and strike**, and name what to hit:

```console
strike talon shields
sweep strike talon warp
str tal sh
Seven, sweep and strike the Talon's weapons
track her exhaust and hit her engines
strike off
```

Seven keeps a sweep running for the trail, designs a plasma-seeker if none is loaded, and has the helm close to about 5,000 units off the trail fix: torpedo range, outside most disruptors. She fires the seeker down the trail. **The moment it hits, its telemetry gives you a firing solution for six seconds.** She shows on your sensors wherever she is, cloak or no cloak, and Seven puts every loaded torpedo, and every phaser that bears, into the system you named. Then the window closes, she is gone again, and Seven starts over until that system is out.

On the map the hit bursts out from her in a ring of plasma light. Four hot brackets snap onto her, and a thin ring around them drains clockwise as the seconds run out. Her label reads **FIRING SOLUTION** with the seconds left, and so does her line in the contacts list.

- **Name the system**: shields, phasers, torpedoes, weapons, warp (or engines), sensors or cloak. Name none, or say `hull`, and the salvo goes into her hull to kill her. Systems shorten like anything else: `str tal sh` is the Talon's shields.
- **Say it any way you like.** "Seven, sweep and strike the Talon", "seeker strike talon warp", "follow her plasma trail and take out her engines", "fire a seeker at the Talon and knock out her weapons" and "kill chain on the Talon" all work, typed or spoken, with or without a language model.
- **Name no ship** and Seven takes the nearest one whose trail she can see.
- **It only works while she leaks.** A captain who repairs her drive, or drops below warp 1, leaves nothing to follow. After 45 seconds with no trail and no sight of her, Seven calls it off and tells you why.
- **A ship you can already see** gets the same aimed salvo straight away, with no seeker needed.
- The counsel (O) offers it whenever a cloaked enemy is leaking. Seven picks the system that decides the fight: her warp drive if she is running, her weapons if you are badly hurt, otherwise her shields. Worf would rather put the whole salvo into her hull.

## The Enterprise's refit cloak

In the tour, the Enterprise can be refitted with a cloak built from Romulan salvage and made to fire through. When she cloaks, enemy sensors lose her at once, with no lingering track to follow. She can fire without lifting the cloak: the enemy sees the flash where the shot came from and nothing more, so move after every shot. A damaged warp drive still gives her away.

