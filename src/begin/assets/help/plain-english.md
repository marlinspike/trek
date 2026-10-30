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
