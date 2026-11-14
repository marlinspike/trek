---
title: Officers' voices
category: Getting started
order: 7
aliases: speak, aloud, spoken, officers' voices, bridge voices, text to speech, tts, piper, casting, voices aloud
summary: Your officers speak aloud, each in a voice cast for them. On by default; Settings or `speak` changes it.
see: bridge, voice-orders, sound, settings
---
Your officers speak aloud. Every order you give is read back in the voice of the officer who carries it out. Their reports, warnings and proposals are spoken too, and the ship's computer speaks its warnings. Enemy captains answer your hails in voices of their own. It's on from the first battle and uses the speech engine your computer already has: macOS's voices on a Mac, Windows' voices on Windows, and eSpeak NG on Linux. Subtitles still show every line, and the log still keeps every word.

One voice speaks at a time. A warning goes to the front and cuts short whatever routine line is being spoken. A routine line that has waited too long is no longer news, so it is dropped rather than read out late; when lines pile up in a busy fight, an officer's remark gives way before an answer to one of your orders, and only the newest warnings wait. A line said twice in a breath is spoken once. Figures in brackets, such as `(12,467 > 2,000)`, are for the eye and aren't read out. **M** hushes the bridge along with every other sound.

## Who sounds like whom

Each officer is cast from the voices your computer has, to suit the part as written:

| Part | Cast for |
|---|---|
| Spock | calm, exact, unhurried |
| Worf | deep, slow, clipped |
| La Forge | warm, quick, easy |
| Seven of Nine | cool, precise, level |
| Sulu | smooth, sure, steady |
| Chekov | young, quick, eager, Russian-accented where your computer has a Russian voice |
| The Doctor | brisk, dry, a little superior |
| Ship's computer | even, cool, unhurried |
| Klingon, Romulan and Orion captains, the Borg | by race: harsh and low, cold and silky, sly and fast, many voices as one |

These are castings, not impressions. No actor's voice is copied, only the qualities of the part: accent, pitch and pace. Each part lists the voices it would like best, and the first one your computer has is used. No two officers share a voice while your computer has enough to go round: the ship's computer is cast first, then each officer takes the first voice they asked for that nobody has yet. On a Mac with only the voices it ships with, for example, the computer is Samantha and Seven of Nine is Karen. When none of a part's voices is free, a voice of the right kind stands in, and each part's own pitch and pace keep two officers on the same voice sounding apart.

More voices make a better cast. On a Mac, open System Settings, then Accessibility, Spoken Content, System voice, Manage Voices, and add a few English voices (Evan, Nathan, Allison, Ava, Daniel) and Yuri for Chekov. On Windows, use Settings, then Time & language, Speech, Add voices. On Linux, install `espeak-ng`.

## Changing it

In **Settings** on the main menu (**S**, then Officers' voices), or in battle under **Esc**, then **Bridge voices**:

- **Officers speak**: on or off.
- **What they say**: *Everything*, *Orders and warnings* (readbacks, proposals and warnings), or *Warnings only*.
- **Enemy captains**: whether captains speak their hails.
- **Volume** and **Pace**.
- **Who sounds like whom**: ◀ ▶ recasts a part and plays a line in the new voice, **Hear** plays a line, and **Recast** goes back to the cast's choice.

From the console:

| Command | What it does |
|---|---|
| `speak` | opens the Bridge voices page |
| `speak on` · `speak off` | voices on or off |
| `speak all` · `speak orders` · `speak urgent` | what is spoken |
| `speak volume 70` · `speak rate 110` | loudness (0 to 100) and pace (70 to 140) |
| `speak captains on\|off` | enemy captains' voices |
| `speak hear worf` | a line in Worf's voice |
| `speak hush` | stops what is being said and what is waiting |

Everything is kept in `config/settings.json` under `"speech"`.

## Piper's voices

[Piper](https://github.com/rhasspy/piper) is a free speech engine that runs on your own computer, with neural voices that sound more natural than most system voices. To use it, install it (`pip install piper-tts`, or put the `piper` program in `config/speech/piper/`), then put a few voices in `config/speech/piper/`. Each voice is an `.onnx` file with its `.onnx.json` beside it, for example `en_US-ryan-medium`, `en_US-amy-medium` and `en_GB-alan-medium`. With the engine on **Best there is**, the game uses Piper when it finds both the program and a voice, and casts the officers from the voices you added. Piper can't change pitch, so its casting rests on the voice and the pace.
