---
title: Disabling enemy systems
category: Crew
order: 2
aliases: disable, cripple, disarm, knock out, objective, disable shields, disable weapons, disable torpedoes, disable phasers
summary: Ask Seven to knock out the shields, phasers, torpedoes, engines or sensors of one ship or several, and she works out how.
see: crew, targeting, conn, deflector
---
Tell Seven what you want knocked out, and on whom. She makes a plan, carries it out, reports each ship as its systems go down, and tells you when the job is done or can't be done.

```console
seven, disable the Klingons' shields
seven, knock out Gorkon's torpedoes
seven disarm them
disable gorkon zantha phasers
disable off
```

- **What:** shields, phasers (or disruptors), torpedoes (tubes), weapons (phasers and torpedoes), engines, sensors or the cloaking device.
- **Whom:** ship names, a race ("the Klingons", "the Romulans"), or "all" / "them". With no ship named, she takes your current target, or every enemy if you have none.
- **Stop:** `disable off`, or "Seven, cancel that". A new order about the same systems replaces the old one.
- Typed without an officer's name, the console gives the job to your science officer. `disable tubes 1 2` still switches off your *own* tubes; it only means the enemy's when you name a ship, a race, or a system your tubes don't have.

## How she does it

- **Scans** each target to see what is working, and to know when the job is done.
- **Aims phasers** at the chosen systems, focused tight for accuracy, whenever banks are charged and bear.
- **Torpedoes come as one full salvo from close range,** just outside the distance they need to arm. The enemy's point defense gets little time to react and has too many rounds to stop. Seven fuses each round to burst on a ring around where the target will be, with the proximity fuse set tighter than usual, so a dodge in any direction still lands inside a blast.
- **Two ships close together** get a salvo burst between them, so one volley hits both.
- **A target that cloaks** is hunted with the [[deflector]] pulse or the [[tachyon]] detector.
- When a target's hull gets low she stops using torpedoes on it, because the job is to disable the ship, not destroy it.

She doesn't steer. Keep the ship within torpedo range (about 3,500 to 7,500 units) and ideally phaser range, or hand the helm to Spock (`delegate helm`). Your own orders still come first: anything you fire or target yourself overrides her for a few seconds.

A system counts as knocked out when it is damaged at all, because a damaged system stays off line until it is fully repaired. Weapons count as disabled when every phaser or tube is off line; shields when at least two thirds of the generators are. Enemy crews do repair, so act on her report quickly.
