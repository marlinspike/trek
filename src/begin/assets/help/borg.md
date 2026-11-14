---
title: Fighting the Borg
category: Game
order: 20
aliases: borg, collective, advancements, advances, seven's advancements, borg sensors, sensor array, guided, guidance, borg-tuned, adaptive, adaptive shields, cube, sphere, strike, opening, open shields, wreck, adapt, adaptation, remodulate, remod, modulate, rotate, duty, tune, retune, tune shields, harmonics, harmonic, vinculum, relay, weak point, dormant, tractor, tractor beam, emitter, drain, hunt, drones, assimilation, repel, security, intruders, seal, vent
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
- **Harmonics** (`duty harmonics`): she keeps scanning their ships. Halfway through the survey she finds the ship's **vinculum relay**. When it is complete she has the ship's **shield harmonics**, and `design harmonic` builds torpedoes that pass straight through her shields. When Seven runs the science station on her own, she takes this duty herself, reports her progress, and loads harmonic torpedoes the moment she has the harmonics. The gauge in the Borg panel shows how far she has got. A cube is a great deal of ship to read: her survey takes about three times as long as a sphere's, so expect to hold the range a while before you know where to hit her.
- If Seven is away or hurt, Spock takes the science station and the duties, a little more slowly.

## Seven's advancements

On **The Collective** tour the Enterprise carries three of Seven's advancements, built from Borg technology. They come online the moment a Borg battle begins, and Seven tells you when they are up:

- **Borg sensors**: every scan of a Borg ship counts twice, so she finds the relay and the harmonics in half the time.
- **Borg-tuned torpedoes**: your torpedoes fly half as fast again at a Borg ship and hit it half as hard again, and because the guidance re-tunes every salvo the hive learns them about three times more slowly. A sphere is nearly as fast as the Enterprise but can't outrun them.
- **Adaptive shields**: your shields are tuned against their transporters from the first moment, and they tune three times as fast. When the hive shifts its beams you keep most of your tuning, and you never lose the block on their transporters.

A tour you write yourself can hand them out too: from the start (`advances` on the tour) or as the prize for winning a stop (`advances` on the stop). Either way they come online at the start of each Borg battle. If one is ever offline, `design sensors`, `design guided` or `design adaptive` brings it back, and Seven offers to do that herself.

## The weak point

Every Borg ship routes its vinculum relay through some unremarkable system: a battery, a transporter, a probe launcher. Once your scans have found it, aim at it: `target cube relay` (or "Worf, target their relay"). An officer running tactical on their own aims at it the moment it is found, unless you have named another system. Destroy it and **every drone aboard goes dormant**. The ship goes dark: no shields, no weapons, no helm, and no healing.

While she sleeps:

- Hit her warp drives or reactors and she goes up in a chain reaction. Stand well clear.
- Or send an [[away-team]] across by transporter: plant charges, wreck her weapons, or bring a drone home.

When the drones wake, they reroute the relay and you have to find it again.

## The cube hunts you

A cube does not stand off. She goes for the biggest ship on the field, the Enterprise, and she is faster than you are: warp 9.9 against your 9.5, so you can't keep the range open for ever. Once she is within about 3,000 she locks her **tractor beam** on you. It holds you where you are, inside her beams, and drains every one of your shields, about 6% a cycle, so her cutting beams start to reach the hull. Engineering tells you the moment she has you.

There are three ways out:

```console
target cube tractor
fire all
cloak on
```

- **Fire down the beam.** Her tractor runs out through her own shields, so fire aimed at the emitter gets through them (`target cube tractor`, or "target their tractor beam"). Wreck it, and she can't hold anything until her drones have half mended it. An officer running tactical aims at it the moment she takes hold, ahead of her relay.
- **Cloak.** A ship that vanishes slips the beam. An officer flying the Enterprise with the refit cloak does this on their own, and comes back a few cycles later.
- **Wait her out.** No emitter holds a starship for long. After about 8 cycles it overloads and lets go, and it needs some 20 more before it can hold anything again. By then your shields are gone and her beams are in your hull, so don't count on it.

Then get the range open again, and finish the survey before she catches you twice.

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

1. Keep the range open as long as you can and let Seven survey the cube. When she catches you, cut her tractor beam at once.
2. Find the relay. Put her to sleep, and send Worf across to steal her harmonics.
3. When she wakes, put one full salvo through the harmonics into her shields, and the next into her drives.
4. Cloak, and finish her through the holes.

## Talking to them

`hail cube` gets an answer from the Collective, not from a captain. They never accept terms, and they never break. Their silence is not anger; there is simply nothing over there to persuade.

Three presets teach the Borg in order: **First Contact: a Borg Probe**, **The Sphere** and **Wolf at the Door: the Cube**. The tour **The Collective** strings them into a campaign ([[tour]]).
