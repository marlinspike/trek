---
title: Officers and language models
category: Crew
order: 2
aliases: llm, language model, character voices, second model, klingon language, ai, anthropic, claude, openai, openrouter, ollama, provider, api key, think, nothink, local model
summary: Let your officers answer in their own words through Anthropic, OpenAI, OpenRouter or a local Ollama model.
see: talking, crew, plain-english
---
The game is complete without a language model: officers answer offline. If you connect one, every question you put to an officer goes to the model with that officer's personality and a summary of what your ship knows. When you give an order, their answer can include commands, which go through the console like anything you type and are only carried out for that officer's stations. When you ask a question, any commands in the answer are only suggestions: they appear under the reply for you to type, and nothing is carried out.

The same model also lets you type orders at the console in plain English: see [[plain-english]].

Requests run in the background, so a slow or failing model never stalls the battle. If a request fails, the officer answers offline and says why.

## Setting it up

The quickest way is from a terminal, which saves the `llm` section of `config/settings.json` in the project folder for you and then asks Spock one question to prove it works:

```
begin --llm provider=ollama model=lfm3 think=off
begin --llm-test
```

`--llm-test` prints the provider, the model, whether thinking is on, how long the answer took, the raw reply, and what Spock would say. `--llm provider=off` switches the model off again, and `--llm think=` (nothing after the `=`) removes a setting.

You can also edit the file by hand, or use environment variables. Keys are read only from the environment and are never saved.

```
"llm": {"provider": "anthropic", "model": "<model id>"}
"llm": {"provider": "ollama", "model": "lfm3", "think": false}
```

| Provider | `provider` | Key (environment variable) | Notes |
|---|---|---|---|
| Anthropic | `anthropic` | `ANTHROPIC_API_KEY` | needs the SDK: `pip install anthropic` (or `pip install -e .[llm]`) |
| OpenAI | `openai` | `OPENAI_API_KEY` | |
| OpenRouter | `openrouter` | `OPENROUTER_API_KEY` | any model OpenRouter offers |
| Ollama | `ollama` | none | a local server, `http://localhost:11434` by default |

- `model` is required: use any model id your provider offers.
- `base_url` points at a different endpoint, such as Ollama on another machine.
- `effort` (Anthropic only) sets how hard the model thinks: `low` is quick and suits conversation.
- `think` (Ollama) turns a local reasoning model's thinking on or off: `true` or `think`, `false` or `nothink`, or a level such as `low`, `medium` or `high` for models that offer levels. Leave it out to use the model's own default. Thinking makes answers slower but sometimes better; for chat during a battle, off is usually the better choice. The model's reasoning is never shown, only its answer. If a model cannot think, Ollama refuses `think: true`, and the officer's error message says so.
- `console` decides what you type at the console goes to the model: `on` (the default: only lines the console doesn't recognise), `always`, or `off`. See [[plain-english]].
- `timeout` is how many seconds to wait for an answer: 120 by default for Ollama, since a local model may need loading first, and 45 for the others. `max_tokens` caps the length of an answer.
- The environment variables `BEGIN_LLM_PROVIDER`, `BEGIN_LLM_MODEL`, `BEGIN_LLM_BASE_URL` and `BEGIN_LLM_THINK` override the file. Set `BEGIN_LLM_PROVIDER=off` to turn it off for one session.

The console log says which provider the officers are using when a battle starts.

## A second model for character voices

A second model can speak for the game's characters while the first keeps the jobs that follow rules. It suits a model that is better at staying in character, or at alien languages: Klingon captains who use tlhIngan Hol, Romulans who are coldly formal. Turn it on, and choose who it speaks for, on the main menu's **Character voices** page (V); the model itself is set in `config/settings.json` under `llm`, or from a terminal:

```
begin --llm character.provider=ollama character.model=<model> character.for=captains,taunts
begin --llm-voice-test klingon
```

```
"llm": {"provider": "ollama", "model": "lfm3",
        "character": {"provider": "ollama", "model": "<model>", "for": ["captains", "taunts"],
                      "factions": ["klingon"],
                      "notes": {"klingon": "Use a few words of Klingon, each followed by its meaning."}}}
```

- `for` is any of `captains` (answering a hail), `taunts` (an enemy calling you), `officers` (answering you), `chatter` (their remarks) and `log` (the captain's log). Left out, it is `captains` and `taunts`.
- `factions` and `officers` narrow it (left out: everyone). `notes` adds a line to a faction's or officer's prompt, or to everyone's with `"*"`.
- `enabled: false` keeps the settings and lets the main model speak for everyone. `--llm character=off` removes it.
- Plain-English orders, named orders and judging your speeches always stay with the main model. If the second model fails, the main one answers that line, so nobody goes silent.
- Its requests appear in the debug logs under its own model name.

## What the model sees

The officer's personality, their station, your rapport, the console command syntax, and a short factual summary of the battle: your ship's state, weapons, shields and power, the contacts on your sensors with their range and bearing, and the coach's notes. Never anything your side could not know.
