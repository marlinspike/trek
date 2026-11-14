---
title: Tours of duty
category: Game
order: 5
aliases: tour, tours, tour of duty, starting squadron, starting squadrons, squadrons, perks, generated tour, another patrol, boss, officers' view, request, request reinforcements, reinforcements, ready room, squadron, captain's log, log, waves
summary: Linked battles with a squadron you choose: damage, crews, torpedoes and prizes carry from one stop to the next.
see: after-battle, crew, dock, fleet
---
A tour of duty is a patrol of several stops, each one a battle. Open one from the main menu (**Tour of duty**, or **T**). New to the game? The first tour on the list, the **[[shakedown|Shakedown Cruise]]**, teaches one part of the ship at each stop. Every tour follows the [[difficulty]] you chose.

Your squadron carries everything that matters from one fight to the next: hull and system damage, casualties, torpedoes and probes fired, morale, and the ships you take as prizes. Shields, batteries, heat and positions start fresh each time. A ship that is destroyed, abandoned, surrendered or boarded is gone for the rest of the tour. If the flagship is lost, the tour is over; at a starbase, so is losing the starbase. Against the Borg, if their drones take the flagship, the tour ends there.

## The squadron

Before the tour you choose the escorts that sail with the flagship. Each class costs its mass from the tour's fleet budget, so one heavy cruiser costs about as much as two destroyers and an interceptor. The flagship herself, the Enterprise, is a Dreadnought and costs nothing.

### Starting squadrons

Below the yard are the **starting squadrons**: named escort groups you earn as your officers come to trust you ([[styles|trust]]) and as you bring tours home. Pick one and it fills your escorts, at their usual cost, and brings a perk for the whole tour. Add more ships if the budget allows; send one of the squadron's ships back and the perk goes with her.

| Squadron | Ships | Perk | Earned with |
|---|---|---|---|
| Destroyer screen | a destroyer and an interceptor | none | always there |
| Worf's strike group | two destroyers | **veteran**: their crews start in high spirits and settle back there, not to the usual, between stops | Worf's trust (Trusted) |
| La Forge's tender group | a destroyer and an interceptor | **tender**: a supply ship sails with you, an extra quarter of a reload for every ship at every stop | La Forge's trust (Trusted) |
| Spock's survey wing | two interceptors | **liaison**: one more call to Starfleet for reinforcements | Spock's trust (Trusted) |
| Starfleet detachment | a heavy cruiser | **veteran** and **liaison** | one tour won |

Squadrons are escorts and their perks only: the flagship is always the tour's own, a Dreadnought for the Enterprise. The Ready Room names the squadron you sailed with.

## The Ready Room

Between stops you are in the Ready Room, over the patrol chart.

- **The briefing.** The officer who knows the threat best tells you what to expect, and what the enemy has learned about you so far. Fight with aimed fire and boarding parties and their captains grow wary; run your magazines low and they close in.
- **Your officers' view.** Worf, Spock, La Forge and Seven each give two sentences on the next stop: the force to beat and where to strike, how that navy likes to fight and the geometry of any mission, how the squadron will arrive and whether a refit or a call to Starfleet is worth it, and what the sensors can and can't tell us yet. See [[counsel]].
- **Your decision.** Some stops ask you to choose, for example whether to put in for a refit. A refit makes every ship good, but the enemy uses the time too.
- **The squadron.** Each ship as Geordi expects her to arrive. On the way, crews repair systems and patch hulls (to 75% at most; a starbase does the rest), and a supply ship tops up the magazines. **Keep at base** leaves a ship behind to be refitted; she misses the next fight.
- **Request reinforcements.** Starfleet sends a ship. Called from the Ready Room, she meets you at the stop, or partway into the fight if the trip is short. Each tour allows only a few calls.

## In battle

| Command | What it does |
|---|---|
| `request reinforcements` | ask Starfleet for a ship (`reinforcements` works too). The map shows her ETA; she drops out of warp behind your starbase or your ship, away from the enemy |

Starbase battles come in **waves**: when you beat one, the next drops out of warp after a lull. Use the lull to dock damaged ships ([[dock]]). The battle is not over while more attackers are coming.

A reinforcement and any prize you take join your squadron for the rest of the tour.

## The captain's log

After each stop your officers write up their stations, each captain in the squadron reports on their own ship, and the captain's entry is drafted for you. Click it to rewrite it: your words are kept as written. With a language model configured ([[llm]]), the officers rewrite their entries in their own voices while you read.

The log is also kept as Markdown in `config/tours/<tour>-log.md`. Edit the captain's entries there between sessions and the game reads them back. At the end of the tour you get a rating: stops won, kills and prizes, ships lost and crews brought home.

## A fresh patrol every time

The last tour on the list is made for you: a generated patrol, different each time. Pick it and press **Another patrol** until one appeals, or take what you're given. Each one has a sector, one adversary for the whole tour (Klingons, Romulans or Orions) and five stops:

- **Four stops built from the patrol situations** ([[patrol]]): an ambush, a wolf pack, a second wave, a distress call, a convoy or a runner. At least one is a mission.
- **The threat rises.** The first stop is a skirmish; each one after brings more and better ships, sized against the squadron you can field, not the flagship alone. The briefings say so as it happens.
- **Two choices.** Before the third stop, refit at the starbase (everything made good, but they send one more ship) or press on. Before the last, strike before they gather (less repair on the way, one fewer ship in her screen) or come in repaired (and meet one more).
- **The boss.** The last stop is the commander behind the raids, aboard their heaviest class, with a screen and a reserve that drops out of warp when the screen is beaten. Take or destroy the flagship and the tour is won.

The Enterprise is your Dreadnought on every generated tour, as on every other. A generated tour saves and resumes like the rest, and its number is in its description: the same number is always the same patrol.

## Your own tours

Write your own in `config/tours/<anything>.toml`, in the same format as the shipped ones (`src/begin/content/data/tours.toml`): the stops, their briefings, the enemies, any choices and waves. A tour with the same id as a shipped one replaces it.

## The Collective

The Borg tour plays by a few rules of its own. The hive remembers your weapons from one stop to the next: most of what it learned of your phasers and torpedoes it still knows, so remodulate early. Seven, in turn, reads them faster each time. Before the third stop you decide whether to keep the Treaty of Algeron or let Spock and Geordi fit the cloak they built from Romulan salvage. With the cloak, you can fire from under it ([[cloak]]), but every time you call for reinforcements, Starfleet asks why the flagship is cloaked. The question goes in the log.
