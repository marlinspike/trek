---
title: Transporters and boarding
category: Ship systems
order: 4
aliases: transport, beam, board, boarding, transporter, crew, change ships, transfer command, capture
summary: Beam crew between ships, send boarding parties, or move your command to another ship.
see: shields, tell, tractor
---
Transporters reach 3,000 units. Every beam needs a clear path: **your shield facing her must be down** (lower it with `lower`), and **at least one of her shields must be down**, either destroyed or under 5%.

```console
beam excalibur
beam excalibur 20
board gorkon
board gorkon 30
```

From the screen: the **Board** button in the Target panel sends the default party to your target, and the panel says whether it is inside transporter range. In the **Fleet** tab, **Beam 20** sends 20 crew to the selected ally, and **Take command** moves you aboard it. A ship with enemy boarders on it shows their number in red under its name.

## Changing ships

`beam <ally>` moves you and your command to one of your own ships within range. Your old ship carries on under an AI captain. Do this when your flagship is crippled but the fight is not over.

## Moving crew

`beam <ally> <count>` sends that many of your crew to an ally, to replace its losses.

## Boarding

`board <ship>` sends a boarding party onto an enemy. Without a number, it sends a sensible party for your transporters and crew. Each cycle the boarders fight the defending crew. Each nation fights boarding actions with different skill. If the defenders fall below six while six or more boarders still stand, the ship is **captured** and joins your side. If the boarders are wiped out, the attack fails.

## Taking a ship

1. `target <ship>`, `spread 10`, and close in. `aim shields` and fire until one of her shield generators is destroyed. That hole stays open; a shield you merely knock down comes back within a few cycles.
2. `aim life support` and keep firing. Her crew falls quickly, and her hull holds. When it is gone she is adrift (derelict) with her shields down.
3. `lower`, then `board <ship>`. A derelict falls to your boarders at once. A ship with crew left fights them first.
4. She is yours: a prize crew holds her, and a captain from among them takes her helm. `beam <ship> 60` sends her more crew, since repair crews only work once she has a tenth of her complement. `beam <ship>` takes you aboard to command her yourself, and `repair <system>` sets the repair priority.

If the ship you left helpless is the last enemy, the battle stays open for 60 cycles so you can board her. Destroyed systems can only be rebuilt at a base, and warp drives are the slowest of all to repair, so choose what you shoot.

Allies can board for you with `tell <ally> board <ship> <count>`. See [[tell]].
