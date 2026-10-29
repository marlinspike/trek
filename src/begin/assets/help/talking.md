---
title: Talking to your officers
category: Crew
order: 1
aliases: ask, say, talk, conversation, question, rapport, relationship
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

Officer lines are in `src/begin/content/data/officers.toml`. Edit them, change a personality, or swap in a different officer for a station.
