---
title: Choosing weapons
category: Coach
order: 1
aliases: weapons guide, choosing weapons, torpedo types, probe types, compare, comparison, which torpedo, ordnance
summary: Torpedo and probe types compared, with live numbers from the game data, and how to pick between them.
see: torpedoes, probes, phasers, loading, coach
---
Each nation fields its own torpedoes and probes. They differ in four ways that matter in a fight: **speed** (how long the target has to dodge), **warhead** (how hard it hits), **range** (how long it flies before it fizzles), and **arming distance** (how far it must travel before it can explode). The tables below come straight from the game data, so they are always current.

## Torpedoes

{{torpedo_table}}

### How to choose

- **Long range, slow target:** a heavy warhead. A base or a crippled cruiser cannot dodge, so put everything you have into the hit.
- **Fast or turning target:** the fastest torpedo you have, with a wider proximity. The less time it is in flight, the less the target can move.
- **Strong shields:** a shield-bore warhead. It loses less to the shield it strikes.
- **Close range:** watch the arming distance. A torpedo fired inside it flies straight through its target.
- **Plasma** steers toward its target, but its warhead weakens as it flies. Fire it from close in.

Change what a tube holds with `load` or `autoload`. See [[loading]].

```console
autoload tor all photon 300
load all tubes 250
```

## Probes

{{probe_table}}

### How to choose

- Probes are slower than torpedoes, so they are best against targets that cannot outrun them: bases, damaged ships and big cruisers.
- Most probes home in on a ship. Others fly a set course and are good for laying a field ahead of a fleet, then setting off by code with `detonate`.
- A probe's timer decides how long it waits before it can be set off. Set it with `load launchers <list> <prox> time <t>`.

## Phasers

Phasers hit instantly, but they lose power with distance and with spread.

{{phaser_falloff}}

Fire at a narrow spread against one ship and a wide one against several objects, such as a cloud of incoming torpedoes. See [[phasers]].

## Ship classes

{{class_table}}
