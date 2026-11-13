---
title: Fighting the Borg
category: Game
order: 20
aliases: borg, collective, cube, sphere, adapt, adaptation, remodulate, remod, modulate, rotate, duty, tune, retune, tune shields, harmonics, harmonic, vinculum, relay, weak point, dormant, drones, assimilation, repel, security, intruders, seal, vent
summary: The Borg learn your weapons, take your crew and regrow their hulls. Learn them first, then strike hard.
see: away-team, scan, crew, tactics, transport
---
The Borg don't fight the way captains do. They don't retreat, bargain or surrender. Every weapon that hurts them teaches them, every drone that comes aboard is trying to make your crew into more drones, and their hulls grow back. **Trading shots loses.** What wins is guile first and then power: learn the ship, find the opening, then land everything at once.

## They adapt

Each hit teaches the hive about the weapon that landed it. Soon your phasers barely scratch them and your torpedoes lose their bite. A scan shows how far they have got (the **ADAPTED** gauges), and your officers call it out.

```console
remodulate
seven, take the phasers
duty phasers
```

- `remodulate` puts your phasers on a new frequency, which the hive must learn from nothing. The banks lose their charge while they change over. Each new frequency is learned faster than the last, and least of all when Seven picks it.
- `duty phasers` has your science officer remodulate for you before the hive catches up.
- Hold your fire and mass it. Potshots teach them for free, but a full volley lands before they can answer.

## Seven's work

Seven of Nine knows the Collective from the inside. Give her one duty at a time:

```console
tune shields
duty harmonics
duty off
```

- **Shields** (`tune shields`): she tunes your shield harmonics against their cutting beams. Tuned past halfway, their transporters can't lock on, so no drones come aboard. In time they shift frequency and she has to start again.
- **Harmonics** (`duty harmonics`): she keeps scanning their ships. Halfway through the survey she finds the ship's **vinculum relay**. When it is complete she has the ship's **shield harmonics**, and `design harmonic` builds torpedoes that pass straight through her shields. When Seven runs the science station on her own, she takes this duty herself and reports her progress. The gauge in the Borg panel shows how far she has got.
- If Seven is away or hurt, Spock takes the science station and the duties, a little more slowly.

## The weak point

Every Borg ship routes its vinculum relay through some unremarkable system: a battery, a transporter, a probe launcher. Once your scans have found it, aim at it: `target cube relay` (or "Worf, target their relay"). Destroy it and **every drone aboard goes dormant**. The ship goes dark: no shields, no weapons, no helm, and no healing.

While she sleeps:

- Hit her warp drives or reactors and she goes up in a chain reaction. Stand well clear.
- Or send an [[away-team]] across by transporter: plant charges, wreck her weapons, or bring a drone home.

When the drones wake, they reroute the relay and you have to find it again.

## Drones aboard

Drones beam through any shield that isn't tuned against them. Once aboard, every crewman they overpower becomes another drone, and once enough of them are settled in they take your systems one at a time.

```console
repel security
repel seal
```

- `repel security` sends security teams to the decks they hold, so the drones win fewer fights for a while.
- `repel seal` seals and vents their sections. Most of the drones die, and a few of your own crew with them.
- The Doctor's **inoculation** (`design inoculate`) protects your crew from assimilation. Spock's **encryption** (`design encrypt`) keeps the drones out of your systems. Seven can **sever** the drones aboard from the hive (`design sever`).
- When the last drone is gone, any system they took comes back to you, damaged.

## Power alone

A cube can be beaten by power alone, but it will cost you dearly. Guile and power together win. A good order of battle:

1. Keep the range open and let Seven survey the cube.
2. Tune your shields before the drones come.
3. Find the relay, then send Worf in, or burn it out.
4. Strike while she sleeps.
