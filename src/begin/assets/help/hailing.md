---
title: Hailing enemy captains
category: Crew
order: 4
aliases: hail, hailing, channel, open channel, comms, prisoners, brig, surrender terms, enemy captains, intimidate
summary: Open a channel to an enemy captain: demand surrender, tell them to leave, threaten, bluff or just talk.
see: morale, transport, crew, llm
---
Every enemy ship has a captain with a mind of their own, and you can talk to them.

    hail gr'oth Lower your shields and prepare to be boarded. Your crew will be treated well.
    hail all Leave this sector and we will hold our fire.
    hail                       (opens a channel to your current target)
    open a channel to the Gr'oth
    worf, hail the Klingons

Your words are read for what they ask. You can **demand surrender**, tell them to **withdraw**, **threaten** them, **bluff** (claim strength or help you don't have), **taunt** them, or **just talk**, and a hail that asks nothing still tells you their state of mind. Offering fair terms (prisoners treated well, safe passage, a way out with honour) makes a demand more persuasive. Insults make it less so.

## What decides the answer

The game decides, not the words alone. Each enemy captain has a **temper** and an **obstinacy**, rolled around their race's values:

| Race | Watching their allies battered makes them | At the start they are |
|---|---|---|
| Klingon | angry: they fight harder and go after the ship that did it | stubborn |
| Romulan | wary | very stubborn |
| Orion | frightened | easily talked round |

Every shield you collapse, every torpedo into an ally's hull, and above all every ship of theirs destroyed or taken, is watched by the captains still fighting. Depending on temper it makes them **shaken** or **enraged**, and every loss wears down their obstinacy, so even a stubborn captain comes round once they have seen enough. Their own damage, their crew's [[morale|morale]] and the odds as they see them count as well.

A shaken captain retreats sooner and yields more readily. An enraged one closes on you, refuses to listen, and may cut the channel. Anger cools with time; fear lingers.

A **bluff** works only if their scans don't show it up: if they have scanned you and your hull is battered, they will know, and they won't like being lied to.

## Surrender, and what comes after

A captain who surrenders **lowers their shields and powers down their weapons**. Then it is your choice:

- keep firing, and every hit goes straight into the hull; or
- beam a party of **six or more** across (`beam <ship> <crew>`, or `worf, capture her`). A surrendered crew does not resist: you take the ship without losing anyone, and her crew are held as **prisoners of war**. `prisoners` shows who you hold.

Fire on a ship that has surrendered and every enemy captain who sees it will trust you less. Their next surrender will be much harder to get, and the angry ones will fight to the end.

A captain who agrees to **withdraw** holds fire and leaves the field. Fire on them and the agreement is off.

## The comms panel

When you hail a ship, or a captain hails you, the comms card shows who is on the channel, their mood, and the last few words exchanged. Enemy ships whose captain you have heard from carry a small mood mark on the map: a red flame when enraged, amber when shaken, blue when wavering, and a white flag once they have surrendered.

Your science officer reads each answer for you ("They are close to giving way, Captain"), and your tactical officer tells you what a surrender or withdrawal means for your next move.

## With and without a language model

Without a model, your words are sorted by keywords and the enemy answers with lines written for their race and mood. You can change or add lines in `config/hails.toml`; see the bundled `hails.toml` for the layout. With a model ([[llm|LLM]]), the model plays the enemy captain. It reads your actual words, judges how persuasive they are, and answers in character, knowing their losses and their mood. Captains also hail you in their own words when what they have seen changes their mind. The model never decides the outcome. It writes both a yes and a no, and the battle picks which one is said.

## On a tour of duty

Word travels ahead of you. Ships that surrendered to you and were spared, and ships you let withdraw as agreed, make later captains readier to yield; ships you fired on after they had yielded make later captains fight to the end and disbelieve your terms. The briefing in the Ready Room tells you what the enemy has heard.

Prisoners stay in your brig from one stop to the next. In the Ready Room, **Hand over prisoners** passes them to a Starfleet transport, which leaves torpedoes and probes, and every 40 prisoners earns another reinforcement call. Or keep them, and offer them back over a hail ("leave now and we will return your people"): a captain is far readier to withdraw for that, and the prisoners are beamed back to their ship when they agree.
