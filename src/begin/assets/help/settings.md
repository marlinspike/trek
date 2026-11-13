---
title: Settings
category: Game
order: 1
aliases: settings, options, preferences, config, configuration, setup, set up, menu settings
summary: Change the game's settings from the main menu: display, sound, battle, the bridge, speaking orders, language models and your officers.
see: display, sound, bridge, voice-orders, llm, crew
---
Choose **Settings** on the main menu (or press **S** there). The sections are down the left, numbered; click one, press its number (**1** to **9**), or move through them with **↑** and **↓**. **Esc** or **Back** returns to the menu.

Every change is saved the moment you make it, to the same plain text files the game has always read, so you can still edit them by hand: `config/settings.json` for everything except the officers, and `config/officers.toml` for them. A box you type in (a model's name, a server's address) keeps what you typed when you press **Enter**, **Tab** or click elsewhere; **Esc** puts back what was there. **Ctrl+V** (or **⌘V**) pastes.

- **Display**: the renderer (automatic, graphics card or software) and *Light and glow*. **D** on the main menu opens this section. See [[display]].
- **Sound**: sound on or off, the volume and the engine hum (drag the slider; **Hear it** plays a sample), and which version of the phaser and torpedo launch you hear: each letter plays it as you pick it. See [[sound]].
- **Battle**: the speed a battle starts at, your officers' chatter, and the map's jolt when the ship takes a heavy blow.
- **Bridge**: the bridge style (full, quiet or classic) and each of its parts. The same choices as `hud bridge` in battle. See [[bridge]].
- **Speaking orders**: on or off, what hears you (Mac speech, Whisper on this computer, a Whisper server or a cloud service, each with what it still needs), the push-to-talk key, the Whisper model and its download, and the server's address. Test the microphone in battle with `voice`. See [[voice-orders]].
- **Language model**: the provider (or Off), the model, an address for Ollama on another machine, thinking, plain English at the console, and the debug logs. **Test it** asks the model one question and shows its answer. Cloud keys are never kept in the config folder: the page says whether the environment has one. See [[llm]].
- **Character voices**: a second model for the game's characters, with its own provider, model and address, who it speaks for, which races' captains, and which officers use only it. **V** on the main menu opens this section.
- **Officers**: each officer's name, rank, traits and how they speak. The grey words are the game's own; click one to change it, and **As shipped** takes your change out again. Only the one line you change in `officers.toml` is written: your comments, personas, backgrounds and lines stay exactly as you wrote them. See [[crew]].
- **Files**: which of the config files are yours so far, your key macros, and **Open config folder**.

Battle settings changed in battle (the speed, **M** for mute, `hud bridge`, `voice`) are kept the same way and show here next time.
