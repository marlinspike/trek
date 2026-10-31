# config

Everything you set for the game lives in this folder. Only this README and the example files are in git; your own files stay on your machine.

| File | What it holds |
|---|---|
| `settings.json` | Window size, speed, sound (`volume` 0 to 1, `muted`, and `sounds`: which version of the phaser and torpedo sounds, a to d), officer chatter, Custom battle choices and the officers' language model. The game writes it; `begin --llm ...` edits the `llm` part. Copy `settings.example.json` to start one by hand. |
| `officers.toml` | Your officers' traits, a few words each ("dry wit", "coolly confident"), and each one's `response_style` (how they answer: length, tone, register). With a language model they shape how each officer talks. Copy `officers.example.toml` to start. |
| `orders.toml` | Your named tactical orders: a name and a list of console lines, such as `beta-1`. In battle, `execute order beta-1` runs them. Copy `orders.example.toml` to start; until you do, the examples are loaded. |
| `hails.toml` | Your own lines for enemy captains answering a hail, used when there is no language model. Same layout as `src/begin/content/data/hails.toml`: a `[klingon]`, `[romulan]`, `[orion]` or `[default]` table with any of its lines; yours replace the shipped ones line by line. |
| `orders.cache.json` | The game's own note of how the language model put your plain-English order steps into console commands, so it doesn't ask again. Safe to delete. |
| `sounds/` | Your own sound effects, as WAV files named for the sound they replace: `phaser.wav`, `torpedo.wav`, and the others listed in `help sound`. Each one replaces the game's own. |
| `begin2.key` | Begin 2.0 key macros, one per line, such as `F2 fire all torpedoes`. |
| `tours/` | Tours of duty. The game keeps each tour in progress here (`<tour>.json`) and its captain's log (`<tour>-log.md`: edit your entries between the `captain` markers and the game reads them back). Tours of your own go here too, as `.toml` files in the format of `src/begin/content/data/tours.toml`. |
| `help/` | Manual pages of your own. A `.md` file here replaces the bundled page with the same name; new files become new pages. |

API keys never go in here: they come only from environment variables (`ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `OPENROUTER_API_KEY`).

Set `BEGIN_HOME` to use a different folder. Older versions kept these files in `~/.begin-remake`. The first run brings them here, once: anything already in this folder wins, and settings missing from your `settings.json` (such as officer rapport) are filled in from the old one. The old folder is left alone, so you can delete it once you're happy.

Every officer's persona is yours to configure in `officers.toml`: their `traits`, their `response_style`, and optionally a `rapport_floor` (-1 to 1), the lowest their regard for you can fall however you treat them. Under `hidden` in `settings.json` the game keeps its record of officer rapport; anything else there from older versions is dropped the next time it runs.
