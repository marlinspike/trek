# Licensing

This is a personal, non-commercial fan project. It isn't affiliated with or endorsed by Clockwork Software, the makers of *Begin*, or by the owners of *Star Trek*.

## Our code and writing

The source code, tests, tools, content files and documentation in this repository are released under the MIT License (see [LICENSE](LICENSE)). That includes:

- the manual pages in `src/begin/assets/help/`;
- the officers' lines and personas in `officers.toml`;
- the presets, hull shapes and everything else marked as a remake extension.

All of it is original writing for this project.

## Begin

*Begin: A Tactical Starship Simulation* and its manual are copyrighted by Clockwork Software. Neither the program nor the manual is included here.

- The manual was used as a reference for the rules. The copy in `reference/` is excluded from git by `.gitignore` and must not be committed or redistributed.
- No text from the manual is reproduced. Help pages, end-of-battle verdicts and messages are written in our own words.
- The ship, torpedo, probe and faction statistics in `content/data/classes.toml` and `ordnance.toml` are numeric facts about the original game.

## fireflyk64/begin

The game statistics and the decoded formulas tagged [R] come from [fireflyk64/begin](https://github.com/fireflyk64/begin), a reconstruction of begin2.exe, used at commit `0fdade8` under the BSD 2-Clause License. The data was taken by `tools/import_reference_data.py`, and the formulas were reimplemented in Python. Its notice:

```
BSD 2-Clause License

Copyright (c) 2026, fireflyk64

Redistribution and use in source and binary forms, with or without
modification, are permitted provided that the following conditions are met:

1. Redistributions of source code must retain the above copyright notice, this
   list of conditions and the following disclaimer.

2. Redistributions in binary form must reproduce the above copyright notice,
   this list of conditions and the following disclaimer in the documentation
   and/or other materials provided with the distribution.

THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE LIABLE
FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER
CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY,
OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE
OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
```

## Star Trek names

The factions, ship classes and the officers Spock, Worf, Scott and Seven of Nine come from *Star Trek*. Those names and characters belong to their owners, CBS Studios and Paramount. They appear here only in a free fan game. The officers' personas and lines are our own writing, not quotations.

## Fonts

The fonts in `src/begin/assets/fonts/` are:

- **Inter**, under the SIL Open Font License 1.1;
- **JetBrains Mono**, under the Apache License 2.0.

Both allow bundling with software. See [the fonts README](src/begin/assets/fonts/README.md) for the copyright notices.

## Dependencies

- pygame-ce is under the LGPL 2.1. It is installed from PyPI as a separate package, not bundled.
- The optional `anthropic` SDK is under the MIT License.
- Language models are reached only through the player's own accounts or a local Ollama server. Nothing is sent anywhere unless the player configures a provider.
