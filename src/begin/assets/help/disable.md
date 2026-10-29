---
title: Disabling or taking out enemy ships
category: Crew
order: 2
aliases: disable, cripple, disarm, knock out, objective, disable shields, disable weapons, disable torpedoes, disable phasers, destroy, eliminate, take out, bait, fire bait
summary: Ask Seven to knock out the shields, phasers, torpedoes, engines or sensors of one ship or several, or to take ships out altogether, and she works out how.
see: crew, targeting, conn, deflector
---
Tell Seven what you want knocked out, and on whom. She makes a plan, carries it out, reports each ship as its systems go down, and tells you when the job is done or can't be done.

```console
seven, disable the Klingons' shields
seven, knock out Gorkon's torpedoes
seven disarm them
seven, take out the Wraith
disable gorkon zantha phasers
destroy wraith
disable off
```

"Take out", "destroy" or "finish off" without naming any systems means the whole ship: she keeps at it until it is gone.

- **What:** shields, phasers (or disruptors), torpedoes (tubes), weapons (phasers and torpedoes), engines, sensors or the cloaking device.
- **Whom:** ship names, a race ("the Klingons", "the Romulans"), or "all" / "them". With no ship named, she takes your current target, or every enemy if you have none.
- **Stop:** `disable off`, or "Seven, cancel that". A new order about the same systems replaces the old one.
- Typed without an officer's name, the console gives the job to your science officer. `disable tubes 1 2` still switches off your *own* tubes; it only means the enemy's when you name a ship, a race, or a system your tubes don't have.

## How she does it

- **Scans** each target to see what is working, and to know when the job is done.
- **Aims phasers** at the chosen systems, focused tight for accuracy, whenever banks are charged and bear.
- **Torpedoes come as one full salvo from close range,** just outside the distance they need to arm. The enemy's point defense gets little time to react and has too many rounds to stop. Seven fuses each round to burst on a ring around where the target will be, with the proximity fuse set tighter than usual, so a dodge in any direction still lands inside a blast.
- **Two ships close together** get a salvo burst between them, so one volley hits both.
- **Bait.** Against a trigger-happy defense she fires one torpedo first. Their point defense pours several phaser banks onto it, and the rest of the salvo arrives a second later while those banks are still recharging. Klingon and Orion crews fall for it, and so does any crew that has lost a lot of people (a scan tells her). Disciplined Romulan and Federation crews send one bank per torpedo and keep the rest charged, so against them she uses the ring burst instead.

## Baiting yourself

```console
bait
bait gorkon
```

`bait` fires one torpedo at your target (or the ship you name) and every other loaded tube a cycle later.

## How enemy point defense behaves

Every ship's point defense depends on who is manning it. Its race sets its discipline, from the trigger-happy Klingons and Orions to the careful Romulans and Starfleet. Crew losses slow its reactions, spoil its aim and erode its discipline, and a damaged sensor array or computer makes it react late. Every round in a salvo counts: a disciplined crew answers a salvo of seven with up to seven banks.
- **A target that cloaks** is hunted with the [[deflector]] pulse or the [[tachyon]] detector.
- When a target's hull gets low she stops using torpedoes on it, because the job is to disable the ship, not destroy it.

She doesn't steer. Keep the ship within torpedo range (about 3,500 to 7,500 units) and ideally phaser range, or hand the helm to Spock (`delegate helm`). Your own orders still come first: anything you fire or target yourself overrides her for a few seconds.

A system counts as knocked out when it is damaged at all, because a damaged system stays off line until it is fully repaired. Weapons count as disabled when every phaser or tube is off line; shields when at least two thirds of the generators are. Enemy crews do repair, so act on her report quickly.
