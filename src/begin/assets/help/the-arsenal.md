---
title: The arsenal
category: Captain's manual
order: 6
aliases: arsenal, weapons, weapon systems, special rounds, special torpedoes, harmonic torpedo, harmonic torpedoes, point defence
summary: Phasers, torpedoes, probes, point defense and the special rounds your officers build, and when each one is the right tool.
see: fire, phasers, torpedoes, probes, firecontrol, weapons-guide
---
Every weapon has a range where it works and a range where it is wasted. Most of winning with the sword is knowing which is which, right now, against this target.

## Phasers: the knife

Phasers hit the instant you fire, but they are short-ranged, about 2,000 units for most ships. They weaken with distance: at three-quarters of their reach a hit is half as strong as at point-blank. They also weaken with **spread**:

- A narrow spread (`spread 10`) puts the whole charge on one ship.
- A wide one (up to 45°) is weaker, but it can catch several objects at once, including incoming torpedoes.

Each bank recharges from the ship's power after it fires.

{{phaser_falloff}}

Banks locked on a target follow her. Others hold a fixed **mark** relative to your bow. A bank can be given a **role**: offense, defense (kept for point defense), or both.

## Torpedoes: the spear

A torpedo flies straight at a fixed speed and bursts when it passes within its **proximity** setting of a ship. Its warhead doesn't weaken with range, apart from plasma, which fades. Before it can burst it must fly far enough to **arm**, and its time fuse ends its flight. Together these set the **envelope**:

- **Minimum range** is the arming time multiplied by the closing speed.
- **Maximum range** is the arming time plus the time fuse, multiplied by the closing speed.

A ship charging at you shrinks the minimum. A ship running away stretches it. Fire inside the minimum and the torpedo passes straight through her unarmed. The [[coach]] works the envelope out for your current target.

**Proximity is a trade.** A blast fades to nothing at the edge of its reach, so a wide proximity catches a nimble ship but barely scratches her, while a tight one hits hard but needs good aim. The coach suggests a balance.

**Fans.** Tubes locked on a ship lead her. `fire all torpedoes spread 10` fans a salvo around the lead point. A fan only helps once its width at her range is greater than the proximity, and too wide a fan leaves gaps she can slip through. At 6,000 units a 10° fan covers about 1,050 units, enough to catch a sharp turn.

{{torpedo_table}}

**Warheads.** **Antimatter** is the standard warhead. A **shield-bore** warhead loses less to the shield it strikes, but it does not damage the hull. **Plasma** homes in on its target but fades as it flies.

## Probes: the patient weapon

Probes are slow, but most of them home in on their target, and their warheads are large. A ship slower than the probe can't outrun it, which makes probes the weapon for bases, cripples and big cruisers. After launch you can steer one, re-target it or detonate it by its control code (`status probes` lists them).

**Data probes** carry little or no warhead, but they fly fast and see far. Wherever one flies, your whole side sees what it sees.

{{probe_table}}

## Point defense: the shield you fire

Point defense uses idle phaser banks to shoot down incoming torpedoes and probes. Choose how much of your firepower it may take:

| Doctrine | It uses |
|---|---|
| off | nothing |
| conservative | reserved banks, against imminent hits |
| balanced | reserved banks, plus flexible banks against dangerous salvos |
| aggressive | any idle bank, against anything armed and in range |

Every power mans its point defense differently. Klingon and Orion crews are trigger-happy and pour several banks onto a single round. That is why one torpedo fired a second ahead of a salvo, the **bait**, strips their defense bare. Romulan and Starfleet crews answer one bank per round. See [[firecontrol]] and [[disable]].

## The special rounds

Your officers can build rounds no armoury carries:

- **The tachyon detector** (`design tachyon`, Spock and Seven). A torpedo whose burst lights up every cloaked ship within 6,000 units for about 30 cycles. It reaches about 39,000 units. See [[tachyon]].
- **The deflector pulse** (`design deflector`). Not a round: the main dish set up to sweep a 60° cone ahead of your bow, out to 15,000 units. It is reusable every 30 cycles. See [[deflector]].
- **The plasma-seeker** (`design seeker`, Seven and Spock). A torpedo that flies a damaged ship's plasma trail, every turn she made, and homes on her at the end of it. When it hits, you have a six-second firing solution on her, cloak or no cloak: `strike <ship> <system>` has Seven fire it and spend that window for you. See [[cloak]].
- **Harmonic torpedoes** (`design harmonic`). Against a Borg ship whose shield harmonics Seven has learned, they pass straight through her shields. See [[borg]].

## Other tools

| Tool | What it does | See |
|---|---|---|
| Tractor beam | holds a ship within 1,000 units, to drag an ally clear or pin an enemy for your torpedoes and boarders | [[tractor]] |
| Transporters | board, move crew, or move yourself to another ship, within 3,000 units through lowered shields | [[transport]] |
| Cloak | every Romulan class, and the Enterprise's refit in one tour; enemy sensors can't see you until you fire or are hit | [[cloak]] |
| Self-destruct | a blast proportional to your power, felt by everyone nearby; abortable until the last five cycles | [[destruct]] |

## Weapon colours

You can tell who is firing by the colour and shape of their fire:

{{weapon_colors}}
