---
title: Giving an officer the bridge
category: Crew
order: 1
aliases: conn, take the bridge, you have the bridge, i have the bridge, command, the conn, hand over command
summary: Let Spock, Seven, Worf or Scott command the whole ship, and take it back whenever you like.
see: crew, talking, tachyon
---
Any of your officers can take command of the whole ship. They run every station at once, with their own personality, while you watch, step in on the decisions you care about, or take the bridge back.

```console
seven, take the bridge
spock, you have the conn
conn worf
I have the bridge
conn captain
```

- **Giving it:** tell an officer to take the bridge (or the conn, or command), or type `conn <officer>`.
- **Taking it back:** say "I have the bridge" (to anyone, or to nobody in particular), type `conn captain`, or click the banner at the top of the map.
- While an officer has it, a banner across the top of the map says who, and the **Crew** tab shows them in command of every station.

## Who fights how

The officer in command uses their own judgement and temperament: Worf closes fast and hits hard, Spock keeps a careful, calculated range, Scott looks after the ship first, and Seven is efficient and relentless. They pick a target only when you haven't, and they never retreat, surrender or self-destruct.

Spock and Seven will also go after cloaked ships on their own: if an enemy vanishes, they build a [[tachyon]] detector and fire it where the ship should be.

## Flying the ship

An officer at the helm, whether they have the conn or just the helm station, flies like a captain who wants to live:

- **Dodging torpedoes.** Enemy torpedoes fly straight at where your ship would be if it held its course. The moment a salvo is launched, the helm works out where each round will pass under a spread of possible turns and speeds, using your ship's real turn rate and acceleration, and takes the one that makes them miss. A big ship at high warp turns slowly, so it can't dodge everything, but in test battles it cut the share of enemy torpedoes that hit by a quarter to over a third.
- **Flying for Seven.** When Seven is working on an objective (see [[disable]]), the helm sets up her shots: with a salvo loaded it brings the ship just inside torpedo range and outside the enemy's phasers, and keeps the strongest shield toward the enemy. A faster enemy that is already close can't be held off, so then the helm fights it head on rather than show it the stern.
- Otherwise the officer closes and fights as an AI captain would.

## Seeing what they are doing

While an officer has the conn or the helm, or is working an objective, a panel at the top left of the map shows each of them: their job, what they are doing right now ("Evading 4 torpedoes, coming to 229 warp 6", "Salvo of 8 on a ring around Wraith") and how the job stands ("Wraith 3/6 shields out, weakest up 15%"). On the map, the helm's chosen course is a dashed arrow (amber while dodging, with the torpedoes being dodged marked in red), Seven's target is bracketed with what she is after, and her last salvo's ring of bursts fades out over a few seconds.

They also say what they are doing as each step starts, even with chatter off, and when the job is finished Seven sums up what it took.

## Stepping in

You are still the captain. Any order you give, such as `target gorkon`, `helm 90 warp 6` or `fire all torpedoes`, overrides the officer for a few seconds, then they carry on from there. To keep one station for yourself, `assume <station>` takes it back while the officer keeps the rest. When you take the bridge back, the stations go back to whoever ran them before.
