---
title: Giving orders
category: Captain's manual
order: 5
aliases: giving orders, how to give orders, commanding, command, ways to command, input, plain words, plain orders
summary: Every way to give an order, from Begin's terse console to plain words, your voice, the wheel and battle plans written in advance.
see: console, bridge, talking, plain-english, orders, voice-orders, keys
---
You can command the ship however suits the moment. All of these do the same things, so mix them freely:

- keys and the mouse
- a radial wheel
- Begin's console
- plain words
- an officer's name
- your voice
- a plan written before the battle

## Keys and the mouse

The fastest orders are single keys:

| Key | Does |
|---|---|
| **Tab** | targets the nearest enemy |
| **F** | fires phasers |
| **T** | fires torpedoes |
| **P** | fires probes |
| **W** and **S** | change warp |
| **A** and **D** | turn |
| **G** | raises or lowers every shield |
| **V** | cycles point defense |
| **X** | scans your target |
| **R** | cycles which of her systems you aim at |
| **Space** | pauses |

Right-click the map to steer toward a point, and Shift+right-click a ship to pursue her. Every key is listed in [[controls]].

Right-click a ship, or press **E** for your target, to open the **command wheel**: phasers, torpedoes, disable, close to, hail, board, elude, target. Every slice is a console line, and the log shows it, so the wheel teaches you the console as you use it. See [[bridge]].

## The console

Press **Enter** and type. The console speaks Begin's language, and any word can be cut short as long as it stays unique. All of these fire every torpedo tube:

```console
fire all torpedoes
fir tor al
ft
```

Lists of mounts can be written `1 2 3`, `1,2,3` or `1-3`. Ships can be named by any unique start of their name (`pursue gor`), or by contact number (`target #7`). Filler words such as *the*, *to* and *at* are ignored. Separate orders with `;` to send them together. **Tab** finishes the word you are typing. While you type, the battle eases to a quarter speed and a faint line under the console says what Enter would do. See [[console]].

## Plain words

Many orders can simply be said:

- "hit their shields"
- "finish her off"
- "I'll take the helm"
- "all stop"
- "take a shuttle over to the cube"
- "look for exhaust"
- "program a torpedo to follow her"

The console knows these without any setup. With a language model connected ([[llm]]), it understands nearly anything you type. It shows the console commands it chose, marked **≈**, and then runs them, so you learn the real syntax as you play. The model never surrenders, self-destructs or ends the battle on its own reading of your words. See [[plain-english]].

## Talking to an officer

Start a line with an officer's name: `seven, scan gorkon`, `worf, fire all torpedoes`, `spock, what do you recommend?`.

- Each officer carries out orders for their own station. Worf will fire but won't steer.
- Each answers questions about their station.
- Some jobs are whole tasks, such as `seven, disable their shields`, `worf, capture her` or `spock, manage repairs`.

See [[talking]] and [[your-crew|Your crew]].

## Your voice

Hold **Right Alt** (Option on a Mac), say the order, and let go. What was heard runs exactly as if you had typed it, and a misheard order is never guessed at. See [[voice-orders]].

## Battle plans

A **named order** is a plan you write before the fight, as a list of steps. In battle, one word runs the whole list. "Their" and "the target" mean whichever ship you have targeted when the step runs, so one plan works against any enemy.

```console
beta-1
record strike
record stop
orders
```

`record` turns what you just did into a plan you can run again. **Key macros** (`key F2 fire all torpedoes`) and **alert conditions** (`alert red`) are plans too. See [[orders]], [[keys]] and [[alert]].

## When an order can't be carried out

The log says why: "Unable to comply: No phaser banks are charged." Officers read every order back ("Course 090, warp 6."), so if what you hear isn't what you meant, say it again. To stop everything at once, say `cease fire` (the guns) or `stand down` (the guns and every officer). See [[ceasefire]].
