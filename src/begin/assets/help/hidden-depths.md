---
title: Hidden depths
category: Captain's manual
order: 8
aliases: hidden depths, secrets, tricks, tips and tricks, advanced, advanced tactics, not obvious, things you can do
summary: Things the game lets you do that no button tells you about, each with the order that does it.
see: sword-and-mind, coach
---
Everything here works in the game today. None of it is on a button, and most of it changes how a battle goes once you know it.

## Power and shields

- **Lower the shields facing away.** Raised shields cost energy every cycle. If you can't pay for all of them, *none* of them hold that cycle. When power is tight, `lower 4 5 6` keeps the forward shields solid.
- **Charge, then disable.** A disabled bank keeps its charge but stops drawing power. Charge every bank, disable the ones that don't bear (`disable banks 3 4`), and enable them when they do.
- **Reinforce the shield you will keep toward her**, not the one that is already failing. Reinforcing costs four times the energy and halves the drain, so it buys the most on a shield that is still strong.
- **The boost buys time, not speed.** Geordi's team doesn't raise your top warp. It lets you hold it 40% longer. Call it as a long run starts, not when the gauges are already red. `boost`

## Phasers and torpedoes

- **Phasers are point defense too.** A wide spread (`fire all phasers 45`) sweeps a cloud of incoming torpedoes out of the sky. Reserve a bank or two for it with `role banks 5 6 defense`.
- **A fan only helps when it's wider than the fuse.** At 6,000 units a 2° fan changes nothing, because the proximity fuse already covers that much. 10° covers a sharp turn. Too wide a fan leaves gaps between the torpedoes.
- **Bait the trigger-happy.** Klingon and Orion crews fire several banks at a single torpedo. Fire one first and the salvo a cycle later, while their banks recharge. `bait`
- **Fire early at a charging ship.** Her own speed shrinks your arming distance. Wait too long and your torpedoes pass straight through her unarmed.
- **Torpedoes still work against a ship you can't see.** Fired at a cloaked ship, they fly to her last known position, and the bridge tells you how each one ended.
- **Scans show what she has ready.** A scan counts her charged banks and loaded tubes. A ship that has just fired everything is the ship to close on.
- **Lay a probe field.** Fire probes on a set course ahead of an enemy fleet (`fire probes 1 2 course 180`) and detonate them by code when the fleet arrives (`detonate all`).
- **Probes don't give up.** A homing probe outruns any ship slower than itself. Against a crippled ship or a base, it can't be escaped.

## Aimed fire and taking ships

- **Aimed damage lasts.** A system knocked out by aimed fire takes her crew three times as long to repair.
- **A destroyed shield generator is a permanent hole.** A shield you knock down comes back within cycles. A generator destroyed by `aim shields` doesn't, and your transporters can beam through the hole.
- **An empty ship falls at once.** Aim at her life support until her crew is gone. A derelict falls to your boarders without a fight.
- **Spare her engines if you mean to keep her.** Warp drives are the slowest system to repair, and a destroyed one has to be rebuilt from nothing.
- **The last ship gets 60 cycles.** When the last enemy is left helpless, the battle stays open for 60 cycles so you can board her.
- **A surrendered crew doesn't resist.** Board a ship that has struck her colours with six or more and you lose no one, and her crew become your prisoners.

## The mind

- **Taunting is a lure.** An enraged captain closes on you and won't listen. That is exactly what a phaser-heavy ship wants. `hail gorkon <your taunt>`
- **A bluff can be read.** A claim of strength fails if they have scanned you and seen your damage, and they won't like being lied to.
- **Klingons will withdraw, not surrender.** Offer a way out with honour.
- **Prisoners are currency.** On a tour, hand them to Starfleet in the Ready Room for torpedoes and probes, and every 40 earns another reinforcement call. Or offer them back over a hail: a captain is far readier to withdraw for his own people.
- **Mercy travels and so does treachery.** Spare a ship that surrendered and later captains yield more readily. Fire on one and later captains fight to the end and disbelieve your terms.
- **Rally the crew when it counts.** A speech (`address crew ...`) lifts morale by up to 12. At 100, repairs run 25% faster and tubes load 15% faster. The crew needs 60 cycles before another speech helps.

## Cloaks and plasma

- **Aim ahead of a vanishing ship.** A cloaked ship keeps moving. Burst the tachyon detector a little ahead of her last fix, along her last heading.
- **Turn before you pulse.** The deflector pulse only looks ahead, a 60° cone from your bow.
- **A damaged drive gives anyone away.** A badly damaged warp drive vents plasma at warp, cloak or no cloak. `sweep` follows trails much further than usual, and `seeker` flies a torpedo down one.
- **It works against you too.** If Geordi says you are venting plasma, repair the drives or drop below warp 1, or every enemy sensor can follow you.
- **Under the refit cloak, move after every shot.** The enemy sees only the flash where you fired.

## The Borg

- **Potshots teach them for free.** Mass every volley.
- **Each new frequency is learned faster than the last**, and least of all when Seven picks it. Let her take the phaser watch (`duty phasers`).
- **Stolen harmonics work on every Borg ship**, not just the one you stole them from, until the hive notices.
- **The away team is safe only while you keep hurting the hive.** Stop firing, or cloak, and the drones may notice the little ship. Each crossing in one battle is riskier than the last.
- **Bring a drone home.** A drone rescued from a dormant ship lets the Doctor make every later scan of the Borg go further.
- **A sleeping ship's core is a bomb.** Destroy her warp drive or reactor while she is dormant and she goes up in a chain reaction. Stand well clear.
- **When she wakes, the relay moves.** You have to find it again, so make the dormant window count.
- **On a tour, the hive remembers you.** Most of what it learned about your weapons is still known at the next stop, so remodulate early.

## The bridge

- **Orders work while paused.** Pause, think, give every order, then resume.
- **Typing slows the battle**, to a quarter speed, until you press Enter.
- **`chart from <ship>`** measures ranges and bearings from an ally or an enemy, not just from you.
- **Evasive manoeuvres beat aimed torpedoes.** Enemy rounds are aimed where you would be if you held course, so any turn as they launch makes them miss. `evasive`
- **Change ships to fight on.** `beam <ally>` moves you and your command, and your officers come with you.
- **Veteran officers act for you.** Once trust reaches Veteran, an urgent proposal you leave unanswered, such as evasive manoeuvres or shields up, is carried out.
- **Record what worked.** `record last 3 as strike` turns your last three orders into a named order you can run again with one word.
