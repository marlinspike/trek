---
title: Fighting the Borg
category: Game
order: 20
aliases: borg, collective, cube, sphere, strike, opening, open shields, wreck, adapt, adaptation, remodulate, remod, modulate, rotate, duty, tune, retune, tune shields, harmonics, harmonic, vinculum, relay, weak point, dormant, drones, assimilation, repel, security, intruders, seal, vent
summary: The Borg learn your weapons, take your crew and regrow their hulls. Learn them first, open the way, then strike hard.
see: away-team, scan, crew, tactics, transport, tour, cloak
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

## Power through the opening

Power alone loses. A cube's shields drink a whole salvo, her drones mend whatever gets through, and her hull grows back. But power is how a cube dies, **once guile has opened the way**.

An opening is any way through her shields:

- **Her harmonics.** Stolen by an [[away-team]], they let every weapon you fire pass straight through for a few hits. Cracked by Seven's survey, they let your harmonic torpedoes through.
- **A dead facing.** A shield that is down, or a shield generator already destroyed.

Aimed fire that reaches her hull through an opening is a **strike**. Your gunners can see exactly what they are hitting, so the system they aim at is wrecked rather than scratched. While her shields are open the target panel says so, and Worf tells you each system he takes out.

```console
target cube propulsion
fire all torpedoes
fire all phasers
```

Choose what to wreck:

- **Her shields** (`target cube shields`). Destroyed generators are holes that stay open. Later salvos through them are strikes too, long after the harmonics are spent.
- **Her warp drives** (`target cube propulsion`). She can't run or chase. Each drive or reactor wrecked this way may set off her core, however whole her hull: stand clear.
- **Her crew decks** (`target cube crew`). Every salvo kills thousands of drones, and a ship with fewer drones repairs, regrows and boards more slowly.

The drones take a long time to mend what a strike wrecked, so make the salvo count. Aim every bank and tube at one system, and time the torpedoes so they land with the phasers.

**Then cloak.** The Enterprise's refit cloak lets her fire and vanish again. A cube can't beam drones to a ship she can't see, and her beams can't lock on it, so all she can shoot at is the flash where you were. Strike, cloak, move, and strike again through the holes you made.

A good order of battle:

1. Keep the range open and let Seven survey the cube. Tune your shields before the drones come.
2. Find the relay. Put her to sleep, and send Worf across to steal her harmonics.
3. When she wakes, put one full salvo through the harmonics into her shields, and the next into her drives.
4. Cloak, and finish her through the holes.

## Talking to them

`hail cube` gets an answer from the Collective, not from a captain. They never accept terms, and they never break. Their silence is not anger; there is simply nothing over there to persuade.

Three presets teach the Borg in order: **First Contact: a Borg Probe**, **The Sphere** and **Wolf at the Door: the Cube**. The tour **The Collective** strings them into a campaign ([[tour]]).
