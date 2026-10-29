---
title: Torpedoes
category: Weapons
order: 2
aliases: tor, torp, torps, torpedo, torpedoes, tubes, tube, envelope, proximity
summary: Long-range warheads with proximity fuses. Types differ in speed, punch and reach.
see: fire, loading, lock, weapons-guide, coach
---
Torpedoes are fired from **tubes**. They fly in a straight line at a fixed speed (plasma torpedoes home in) and explode when they pass within their **proximity** distance of a ship. Unlike phasers, their warhead does not weaken with range, apart from plasma, which fades as it travels.

## The torpedo envelope

A torpedo is harmless until it has flown long enough to **arm**, and it self-destructs when its time fuse runs out. Together these set the band of ranges where a shot can work:

- **minimum range** = arming time × closing speed. Fire closer than this and the torpedo passes the target before it arms.
- **maximum range** = (arming time + time fuse) × closing speed.

The closing speed includes the target's own motion. A ship charging at you shrinks the minimum and stretches the maximum; a ship running away does the opposite. The [[coach]] works this out for your current target.

> **Tip** Torpedoes miss more often the farther they fly, because the target has longer to change course. The nearer half of the envelope gives the best hit rate.

## Torpedo types

{{torpedo_table}}

- **Warp** is the torpedo's speed: faster torpedoes arrive before the target can react, and reach farther.
- **Warhead** is the blast strength. Shield-bore warheads damage shields but not the hull.
- **Arms at** and **Reach** are the envelope against a stationary target.
- **Max prox** is the widest proximity fuse the type allows.
- **Reload** is how many cycles a tube takes to charge for the next torpedo.

## Firing

```console
fire all torpedoes
fir tor 1,2,3
torp all
ft at gorkon
```

## Loading, proximity and type

Tubes reload by themselves (**autoload**). Use `load` to change the proximity, `autoload` to change the torpedo type, and `unload` to empty a tube so it can be reloaded with new settings.

```console
load tubes prox 400
load tubes 1 2 350
autoload tor mk8
unload tubes 1 2
disable tubes 3 4
enable all tubes
```

> **Coach** A torpedo bursts the moment its target comes within the proximity distance, and its blast fades to nothing at the edge of its reach: 50 × the warhead, so 500 units for a Mark 7. At proximity 500 a Mark 7 bursts right at that edge and barely scratches the target. At 250 it delivers about 70% of its punch, and at 100 about 90%. A wide proximity still catches nimble ships, so the [[coach]] suggests a setting that balances the two (half the blast reach at most).

## Shields soak up hits

A shield facing the blast absorbs damage up to its strength before anything reaches the hull, and each hit drains it by only a fraction of what it absorbed. Heavy ships such as the Klingon Dreadnought have shields strong enough to swallow whole volleys. After each volley the log tells you what happened ("Hits on Wraith: 8, all absorbed (shield 1 now 87%)"). Keep hitting the same shield until it collapses, or turn to strike a weaker one; a `scan` shows them all.

## Leading and dispersion

Tubes locked on a ship aim where it will be, using its speed and course. A **dispersion** angle fans a salvo around that point. Against a ship that is jinking, a fan gives one or two hits instead of a clean miss.

```console
lock all tubes on gorkon
lock tubes 1 2 on gorkon 0
lock all tubes on gorkon with a dispersion of 30
```

## Status

```console
tubes
```

The table shows each tube's charge, lock, mark, contents and proximity. A tube shown at 100% loads its torpedo on the next cycle.
