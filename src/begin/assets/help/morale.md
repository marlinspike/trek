---
title: Crew morale
category: Crew
order: 3
aliases: morale, spirits, address, rally, speech, address crew, captain's address
summary: Every crew has spirits that rise and fall with the fight, and a word from the captain can lift them.
see: crew, repair, status
---
Every ship's crew, yours and the enemy's, has **morale** from 0 to 100. It starts at the race's usual level and moves with the fight:

| Lowers it | Raises it |
|---|---|
| hull damage and crew lost | damage you deal to enemy hulls |
| a system destroyed, a shield collapsing | an enemy ship destroyed or surrendering (most for the ship that did it) |
| a friendly ship lost | repairs completed, the hull patched |
| | your address to the crew |

Out of the fight (no hits for 15 cycles and no enemy within 12,000) it drifts back to the usual level.

Races take it differently. Starfleet crews start at 80 and are hard to shake. Klingons start at 85 and hold under fire, losing little to damage. Romulans start at 75. Orion pirates start at 60 and break quickly once the fight stops paying.

## What it does

Morale is the crew's will, not its numbers: losing crew already slows repairs and weakens the ship. So its effect is modest. At 50 it does nothing. At 100, repairs run 25% faster, torpedo tubes load 15% faster, and point defense and aimed fire are 15% better. At 0 they are the same amounts worse. Enemy captains with a shaken crew retreat sooner and surrender more readily, and a keen crew keeps them in the fight longer.

## Seeing it

The Own ship panel shows it beside your crew count ("steady 62"), and the Bridge crew tab shows it with an **Address crew** button. Hover over either to see what it is doing right now. `morale` lists every ship on your side. Spock tells you when the crew's spirits shift sharply, and suggests a word from you when they are low.

## Addressing the crew

```console
address crew This ship has never lost a fight. Hold together and we bring her home.
rally the crew: steady, people, we have them
```

A speech lifts morale by up to 12 points. With a language model set up (see [[llm]]), it judges how rousing your words are for the moment and Spock tells you how the crew took them; a flat or rude speech does little. Without one, any speech counts as an ordinary good one (8 points). The crew needs a minute (60 cycles) before another speech does any good.
