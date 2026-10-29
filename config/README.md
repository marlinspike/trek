# config

Everything you set for the game lives in this folder. Only this README and `settings.example.json` are in git; your own files stay on your machine.

| File | What it holds |
|---|---|
| `settings.json` | Window size, speed, officer chatter, Custom battle choices and the officers' language model. The game writes it; `begin --llm ...` edits the `llm` part. Copy `settings.example.json` to start one by hand. |
| `begin2.key` | Begin 2.0 key macros, one per line, such as `F2 fire all torpedoes`. |
| `help/` | Manual pages of your own. A `.md` file here replaces the bundled page with the same name; new files become new pages. |

API keys never go in here: they come only from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`).

Set `BEGIN_HOME` to use a different folder. Older versions kept these files in `~/.begin-remake`. The first run brings them here, once: anything already in this folder wins, and settings missing from your `settings.json` (such as officer rapport) are filled in from the old one. The old folder is left alone, so you can delete it once you're happy.
