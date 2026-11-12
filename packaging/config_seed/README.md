# Begin config

This folder holds everything you set for Begin. The game made it beside itself the first time it ran, and it never keeps settings anywhere else on your computer. Every file here is plain text: open it with Notepad (Windows), TextEdit (Mac) or any text editor. The **Open config folder** button on the game's main menu brings you straight here.

You don't need to touch anything. The game saves your window, speed, sound and battle choices in `settings.json` by itself. The files below are for when you want more.

| File | What it holds |
|---|---|
| `settings.json` | Window size, speed, sound (`volume` 0 to 1, `muted`, `sounds`: which version of the phaser and torpedo sounds, a to d, and `hum`), how the game is drawn (`renderer` and `bloom`, set on the main menu's **Display** page), officer chatter, Custom battle choices, the officers' language model (`llm`) and an optional second one for character voices (`llm.character`), the Bridge setting (`bridge`), speaking orders (`voice`) and your career (`career`: each officer's trust in you and the ribbons you've earned). The game writes it; `settings.example.json` shows the layout. |
| `officers.toml` | Your officers, shaped however you like: name and rank, traits, how each one answers, a new persona or a background, interests and quirks, and their own lines for any moment. Copy `officers.example.toml` to `officers.toml` and edit it. |
| `orders.toml` | Your named tactical orders, run in battle with `execute order <name>`. Orders you `record` in battle are saved here too. Copy `orders.example.toml` to `orders.toml` to start. |
| `wheel.toml`, `alerts.toml` | Your own command wheel and alert conditions (`alert red`, `yellow`, `green`), if you want to change them: start from a copy of the game's own, in `src/begin/content/data/` on [GitHub](https://github.com/marlinspike/trek). Each step is a console line. |
| `phrasebook.json` | Plain words the language model worked out once, kept so they work at once next time. Delete a line to forget it. |
| `voice/` | For speaking orders: Whisper models downloaded from the voice page and the Mac speech helper. Safe to delete; they come back when needed. |
| `hails.toml` | Your own lines for enemy captains answering a hail, used when there is no language model. |
| `begin2.key` | Key macros, one per line, such as `F2 fire all torpedoes`. |
| `sounds/` | Your own sound effects as WAV files named for the sound they replace, such as `phaser.wav` (see `help sound` in the game). |
| `tours/` | Tours of duty in progress and their captain's logs. |
| `help/` | Manual pages of your own: a `.md` file here replaces the bundled page with the same name. |
| `logs/` | The language model's debug logs, only when you turn them on. Safe to delete. |

Quit the game before editing a file it writes (`settings.json`), or it may write over your change when it closes.

## Talking officers (optional)

The game plays fully without any of this: the officers use their written lines. To have them talk freely, install [Ollama](https://ollama.com), run `ollama pull lfm3` (or another small model), and put this in `settings.json` while the game is closed:

```json
"llm": {"provider": "ollama", "model": "lfm3", "think": false}
```

A second model can speak for the game's characters only, for richer Klingon, Romulan and other alien speech from enemy captains and more colour from the officers. Set it up on the main menu's **Character voices** page, or under `"character"` inside `"llm"`; the main model keeps reading your orders and judging hails.

Cloud models work too, with `"provider"` set to `anthropic`, `openai` or `openrouter` and that provider's model id. Their API keys are never stored here: they come only from the `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` or `OPENROUTER_API_KEY` environment variable.

## Moving the game

This folder belongs to the copy of the game beside it. If you move the game, move this folder with it to keep your settings. On a Mac, keep `Begin.app` and this folder together, for example both in Applications.
