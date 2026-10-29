---
title: Officers and language models
category: Crew
order: 2
aliases: llm, language model, ai, anthropic, claude, openai, openrouter, ollama, provider, api key
summary: Let your officers answer in their own words through Anthropic, OpenAI, OpenRouter or a local Ollama model.
see: talking, crew
---
The game is complete without a language model: officers answer offline. If you connect one, every question you put to an officer goes to the model with that officer's personality and a summary of what your ship knows. Their answer can include orders, which go through the console like anything you type and are only carried out for that officer's stations.

Requests run in the background, so a slow or failing model never stalls the battle. If a request fails, the officer answers offline and says why.

## Setting it up

Add an `llm` section to `~/.begin-remake/settings.json`, or use environment variables. Keys are read only from the environment and are never saved.

```
"llm": {"provider": "anthropic", "model": "<model id>"}
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
- The environment variables `BEGIN_LLM_PROVIDER`, `BEGIN_LLM_MODEL` and `BEGIN_LLM_BASE_URL` override the file. Set `BEGIN_LLM_PROVIDER=off` to turn it off for one session.

The console log says which provider the officers are using when a battle starts.

## What the model sees

The officer's personality, their station, your rapport, the console command syntax, and a short factual summary of the battle: your ship's state, weapons, shields and power, the contacts on your sensors with their range and bearing, and the coach's notes. Never anything your side could not know.
