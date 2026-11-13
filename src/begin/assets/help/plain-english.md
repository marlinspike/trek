---
title: Orders in plain English
category: Getting started
order: 4
aliases: translate, interpret, english, plain english, natural language, plain-english
summary: With a language model set up, type orders in your own words and the console works out the commands.
see: console, llm, talking
---
When a language model is set up (see [[llm]]), you don't have to remember the console's wording. Type what you mean and the console works it out:

```console
turn hard right and go to warp 6
get the shields up and hit the klingon's engines
what's the best way to deal with a cloaked ship?
```

Each command the model chooses is shown in the log with a **≈** in front, then carried out exactly as if you had typed it, so you pick up the real syntax as you play:

```console
> get the shields up and hit the klingon's engines
  … interpreting
≈ raise all
≈ target gorkon propulsion
≈ fire all phasers
```

If what you said could mean more than one thing that matters, such as which of two enemy ships, the console asks instead of guessing. Just answer: "the closer one" or "gorkon" is enough, because it remembers what you were talking about. A question about the game gets a short answer, often with the command to use.

## Without a model

The bridge's everyday words work with no language model at all. The console turns them into its own commands, and the log shows what it did:

| You say | It does |
|---|---|
| "red alert", "yellow alert" | `alert red`, `alert yellow` |
| "set course 180", "heading 270", "turn to 090" | `helm 180`, and so on |
| "come about", "hard to port", "turn right 45" | turns from her present course: about, 90° or the degrees you give |
| "go to warp 5", "warp factor 5" | `warp 5` |
| "full speed ahead", "punch it" | her best warp |
| "full stop", "slow down", "speed up" | `stop`, or two warp slower or faster |
| "attack", "engage", "attack the Gorkon" | target her (or the nearest enemy), pursue her and open fire |
| "take us in", "close to 3000" | pursue the target, or hold her at that range |
| "retreat", "get us out of here", "keep our distance" | elude the target |
| "fire everything", "fire at will", "keep firing" | every phaser and tube, or weapons free |
| "target the nearest enemy", "lock onto the closest one" | the ship Tab would pick |
| "damage report", "how are the shields?", "where is the enemy?" | the status, shields and chart displays |
| "what do you recommend?" | opens the counsel |
| "manage repairs" | an officer directs the repair crews |
| "launch a probe", "send an away team" | `fire probes`, `away` |
| "zoom in", "zoom out" | halves or doubles the range shown |
| "more power to the engines", "divert power to engines" | `boost`, Geordi's engine boost |
| "more power to the forward shields", "reinforce the aft shields" | reinforces that shield; with no side named, the one facing the target |
| "give me warp 8", "ahead full" | `warp 8`, or her best warp |
| "lay in a course for the Gorkon" | pursue her |
| "can you get the warp drive back?", "repair the phasers first" | sends the repair crews there |
| "all ships, attack the Gorkon", "fleet, form up on me", "squadron, hold fire" | `tell all ...`: the order goes to every ally |
| "Yorktown, defend me", "Excalibur, fall back" | `tell yorktown defend me`, `tell excalibur run` |
| "make it so", "aye", "do it" | takes the officer's proposal on the screen, like **Y**; "no" or "not now" turns it down, like **N** |

An ally's name at the start of a line speaks to that ship, as **tell** does. Allies understand "escort me", "form up on me", "cover me", "attack the Gorkon", "attack my target", "fall back", "hold fire", "open fire", "defend the Yorktown", "report" and "stop". For the whole fleet, start with "all ships", "fleet", "squadron", "wingmen" or "task force".

"The target", "her", "them" and "that ship" mean the ship you have targeted, or the nearest enemy if you have none. A ship whose name really is one of those words still answers to it.

## How it decides

The exact console always gets the first look, so anything typed in console syntax runs at once, with no wait. Only a line the console doesn't recognise goes to the model. Every command the model proposes is checked by the console before anything runs; if one is wrong, the model gets one try to fix it, and otherwise you see what went wrong and nothing runs.

The model never ends the battle, self-destructs, surrenders or changes ships on its own reading of your words. If it thinks you meant one of those, it shows the command and leaves you to type it.

Talking to an officer ("spock, ...") still goes to that officer, as before. The model can also pass a question on to an officer for you.

The exact console always wins, even while the computer is waiting for your answer to a question: a command it recognises, abbreviations included (`tor al`, `pha al`), runs at once and the question is dropped. Only a lone word or number, like `2` or `gorkon`, is taken as your answer.

The battle doesn't wait while the model thinks: a local model may take a few seconds, so pause first if you need time. While it works, the officers say their remarks as written rather than queueing at the model ahead of you. If it hasn't answered in 20 seconds the console gives up, says so, and runs nothing; type the command yourself, or check the model is running.

## Switching it

| Command | Effect |
|---|---|
| `translate on` | the default: only lines the console doesn't recognise go to the model |
| `translate always` | every line goes to the model first, even exact commands (slower) |
| `translate off` | the console only accepts its own syntax |
| `translate` | says which of these is set |

Your choice is saved in `config/settings.json` (`"console"` in the `llm` section) when the battle ends. You can also set it from a terminal: `begin --llm console=always`.

## What the model sees

Your words, the full console command list, and the same factual summary of the battle the officers get: your ship, your weapons and shields, the contacts on your sensors with their names, range and bearing, your allies and your officers. Never anything your side could not know.
