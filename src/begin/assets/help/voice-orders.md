---
title: Speaking orders
category: Getting started
order: 6
aliases: voice, voice orders, speaking, microphone, mic, push to talk, whisper, whisper.cpp, speech, mac speech, dictation
summary: Hold Right Alt (Option), say the order, let go. Mac speech, Whisper on this computer, a Whisper server or the cloud.
see: bridge, console, plain-english, llm
---
Hold the push-to-talk key (**Right Alt**, Option on a Mac), say the order, and let go. A pill by the console shows the level while it listens. What was heard runs exactly as if you'd typed it, and the officer reads it back. If the console can't make sense of it and there's no language model to ask, the words wait in the console for you to fix: a misheard order is never guessed at.

`voice` opens the voice page: which engine hears you, whether it's ready, the push-to-talk key, and **Test** (three seconds of speech, then what was heard and how long it took).

| Engine | What it needs |
|---|---|
| Mac speech | a Mac. Begin builds a small helper the first time (Xcode's command line tools: `xcode-select --install`), and macOS asks once for Speech Recognition. It runs on the Mac, offline |
| Whisper on this computer | whisper.cpp's `whisper-cli` (on a Mac: `brew install whisper-cpp`) and a model: **Download** on the voice page fetches it into `config/voice/models` |
| Whisper server | a whisper.cpp server on this computer or the network (`whisper-server -m <model>`); `voice server 192.168.1.20:8080` |
| Cloud | an OpenAI-style transcription service; the key comes from `OPENAI_API_KEY`, never saved |

Chat models such as Ollama's don't hear speech. The engine only hears; the console, and your language model if you have one, understand.

| Command | What it does |
|---|---|
| `voice` | the voice page |
| `voice on\|off` | speaking orders on or off |
| `voice engine mac\|local\|server\|cloud` | which engine hears |
| `voice key right alt\|right ctrl\|right shift\|caps lock\|f13\|backslash` | the push-to-talk key |
| `voice model tiny.en\|base.en\|small.en\|medium.en` · `voice download` | the local Whisper model |
| `voice test` | hear three seconds and show what was heard |

Settings are kept in `config/settings.json`; models and the Mac helper in `config/voice/`.
