---
title: Talking to your officers
category: Crew
order: 1
aliases: ask, say, talk, conversation, question, rapport, relationship, traits, response style, response_style, character, personality, voice
summary: Ask an officer for a report or advice, or give an order in plain words.
see: crew, llm, coach
---
Start a line with an officer's name (a comma after it is optional, and the first few letters will do, as in `sev status`), or use `ask`:

```console
spock, what do you recommend?
worf, status
scotty, take engineering
seven, scan gorkon
worf, fire all torpedoes
ask spock how do we beat this ship
```

- Officers answer to their name, rank-free nicknames (`scotty`, `seven`) and their station (`tactical, status`).
- **Reports.** "status", "report" or "sitrep" gets a report on that officer's station.
- **Advice.** "what do you recommend?", "advice" or any other question gets that officer's best idea for their stations, with the command to carry it out. Spock advises on everything.
- **Orders.** Any console command works, as long as it belongs to that officer's station: Worf will fire, Scott will raise shields, but Worf won't steer.
- **Stations.** "take the helm", "take over" or "you have the conn" delegates the officer's station; "stand down" or "I have the conn" takes it back.

## Rapport

Each officer remembers how you treat them, from one battle to the next. Thanks and taking their advice build rapport; insults wear it down. `crew` shows each officer's mood. Rapport colours how they speak to you, and later parts of the game will draw on it.

## Offline and LLM answers

Without any setup, officers answer from what your sensors know: reports, the [[coach]]'s advice for their station, and their own lines. To have them answer in their own words, connect a language model: see [[llm|Officers and language models]]. Either way they only know what your side knows.

## Traits, and never the same line twice

Each officer has a few **traits**, words on how they come across: Spock is "precise and emphatic, dry wit, unflappable", and Seven is "highly effective, efficient, coolly confident, ex-Borg precision". With a language model, the traits colour everything an officer says. Their remarks during the battle are written fresh each time, in their voice, from what is happening, and the model is shown what they said lately so it doesn't repeat itself. Two battles never sound the same. Traits change how an officer talks, not how well they fight. Without a model, officers use their written lines.

Each officer also has a **response style**: how they answer when the model writes their words, such as length, tone and register. Worf's is "terse, clipped reports; few words and no pleasantries" and Seven's is "factual, crisp, coolly confident".

Make the officers your own in `config/officers.toml` (copy `config/officers.example.toml`):

```toml
[worf]
traits = ["honour-bound", "blunt", "quietly proud of his captain"]
response_style = "short soldier's reports, a growl when it goes badly"
```

Either line can be left out to keep the game's own. The game passes your traits and response styles to your model as you wrote them.

Officer lines are in `src/begin/content/data/officers.toml`. Edit them, change a personality, or swap in a different officer for a station.
