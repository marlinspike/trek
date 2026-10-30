# config

Everything you set for the game lives in this folder. Only this README and the example files are in git; your own files stay on your machine.

| File | What it holds |
|---|---|
| `settings.json` | Window size, speed, sound (`volume` 0 to 1, `muted`), officer chatter, Custom battle choices and the officers' language model. The game writes it; `begin --llm ...` edits the `llm` part. Copy `settings.example.json` to start one by hand. |
| `officers.toml` | Your officers' traits, a few words each ("dry wit", "coolly confident"). With a language model they shape how each officer talks. Copy `officers.example.toml` to start. |
| `orders.toml` | Your named tactical orders: a name and a list of console lines, such as `beta-1`. In battle, `execute order beta-1` runs them. Copy `orders.example.toml` to start; until you do, the examples are loaded. |
| `orders.cache.json` | The game's own note of how the language model put your plain-English order steps into console commands, so it doesn't ask again. Safe to delete. |
| `begin2.key` | Begin 2.0 key macros, one per line, such as `F2 fire all torpedoes`. |
| `help/` | Manual pages of your own. A `.md` file here replaces the bundled page with the same name; new files become new pages. |

API keys never go in here: they come only from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`).

Set `BEGIN_HOME` to use a different folder. Older versions kept these files in `~/.begin-remake`. The first run brings them here, once: anything already in this folder wins, and settings missing from your `settings.json` (such as officer rapport) are filled in from the old one. The old folder is left alone, so you can delete it once you're happy.

