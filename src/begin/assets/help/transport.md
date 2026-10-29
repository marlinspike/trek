---
title: Transporters and boarding
category: Ship systems
order: 4
aliases: transport, beam, board, boarding, transporter, crew, change ships, transfer command, capture
summary: Beam crew between ships, send boarding parties, or move your command to another ship.
see: shields, tell, tractor
---
Transporters reach 3,000 units. Every transporter beam needs a clear path, so **the facing shield on both ships must be down**. Lower yours with `lower`, and wait for the enemy's to fall.

```console
beam excalibur
beam excalibur 20
board gorkon
board gorkon 30
```

## Changing ships

`beam <ally>` moves you and your command to one of your own ships within range. Your old ship carries on under an AI captain. Do this when your flagship is crippled but the fight is not over.

## Moving crew

`beam <ally> <count>` sends that many of your crew to an ally, to replace its losses.

## Boarding

`board <ship>` sends a boarding party onto an enemy. Without a number, it sends a sensible party for your transporters and crew. Each cycle the boarders fight the defending crew. Each nation fights boarding actions with different skill. If the defenders fall below six while six or more boarders still stand, the ship is **captured** and joins your side. If the boarders are wiped out, the attack fails.

Allies can board for you with `tell <ally> board <ship> <count>`. See [[tell]].
