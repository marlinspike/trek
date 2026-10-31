---
title: Tours of duty
category: Game
order: 5
aliases: tour, tours, tour of duty, request, request reinforcements, reinforcements, ready room, squadron, captain's log, log, waves
summary: Linked battles with a squadron you choose: damage, crews, torpedoes and prizes carry from one stop to the next.
see: after-battle, crew, dock, fleet
---
A tour of duty is a patrol of several stops, each one a battle. Open one from the main menu (**Tour of duty**, or **T**).

Your squadron carries everything that matters from one fight to the next: hull and system damage, casualties, torpedoes and probes fired, morale, and the ships you take as prizes. Shields, batteries, heat and positions start fresh each time. A ship that is destroyed, abandoned, surrendered or boarded is gone for the rest of the tour. If the flagship is lost, the tour is over; at a starbase, so is losing the starbase.

## The squadron

Before the tour you choose the escorts that sail with the flagship. Each class costs its mass from the tour's fleet budget, so one heavy cruiser costs about as much as two destroyers and an interceptor.

## The Ready Room

Between stops you are in the Ready Room, over the patrol chart.

- **The briefing.** The officer who knows the threat best tells you what to expect, and what the enemy has learned about you so far. Fight with aimed fire and boarding parties and their captains grow wary; run your magazines low and they close in.
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

## Your own tours

Write your own in `config/tours/<anything>.toml`, in the same format as the shipped ones (`src/begin/content/data/tours.toml`): the stops, their briefings, the enemies, any choices and waves. A tour with the same id as a shipped one replaces it.
