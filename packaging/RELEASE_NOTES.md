## What's new in 1.4

**Calm big fights.** In a crowded battle every ship's name now finds a clear place beside her, keeps clear of other names, hulls and cards, and stays on the same side as ships move. Names of distant ships fade when the map is busy, and the enraged-captain flames shrink to small dots, so the fight near you stands out. The map shows one card at a time: a proposal, the comms card while someone is talking, the mission card when it has news, or a subtitle. The others fold to a single line or wait in the log.

**Your officers speak.** Readbacks, reports, proposals and warnings are now spoken aloud through your computer's own voices (macOS, Windows or eSpeak NG on Linux, or Piper's neural voices if you set them up), and enemy captains answer hails in voices of their own. Each officer is cast to suit the part: Spock calm and exact, Worf deep and clipped, Geordi warm and quick, Seven cool and level, Chekov young and quick. These are castings, not impressions. It's off by default, so the bridge stays quiet until you want it otherwise. Settings, Officers' voices (or Esc, then Bridge voices, in battle, or `speak on`) turns it on, chooses what is spoken, sets the volume and pace, and recasts any officer. No two officers share a voice while your computer has enough to go round.

**The Shakedown Cruise.** A new first tour that teaches the ship one part at a time: helm and phasers with Spock, torpedoes with Worf, shields and power with Geordi, then your officers and their counsel. Each stop's officer talks you through it a step at a time, out loud and on a lesson card that ticks off what you've done.

**Ensign, Captain or Admiral.** Choose how hard the enemy fights, on the main menu or in Settings, Battle. Ensign brings about a third fewer enemy ships with slower, less able captains; Admiral brings a third more with sharper, quicker ones. Only the enemy changes: the Enterprise is a Dreadnought at every level, and a custom battle keeps the fleets you chose.

## What's new in 1.3

**The Borg.** A new enemy that can't be beaten by trading shots. Every weapon that lands teaches the whole hive, so phasers soon stop biting until you remodulate. Their hulls regrow and their drones beam aboard to take your crew. Scans find a cube's vinculum relay, then her shield harmonics, and torpedoes tuned to those harmonics pass straight through her shields. Destroy the relay and she falls asleep; hit her core then and she goes up in a chain reaction. Seven of Nine takes one duty at a time (tuning your shields against their transporters, surveying for harmonics, or watching your phasers), and away teams can take the Galileo across to a sleeping ship. There are three new battles (probe, sphere and cube) and a new tour, **The Collective**, where the hive remembers your weapons from one stop to the next.

**Guile, then power.** Once you have her harmonics, or a shield facing is down, an aimed salvo at one system (shields, warp, life support) wrecks it, wrecked systems mend slowly, and a broken drive or reactor can set off her core. Fired from cloak, it is how a single ship brings down a cube.

**The cloak refit and the plasma hunt.** On The Collective, the Enterprise can take a cloak. Under it she is a shimmering ghost who can fire and vanish again, and the enemy sees only the flash. A ship with a damaged warp drive leaves a rose-coloured plasma trail that any sensor can follow. `sweep` follows the trails, and Seven or Spock can program a torpedo that flies down one.

**Sweep and strike.** One order runs the whole hunt: `strike talon shields`, or just "Seven, sweep and strike the Talon's weapons". Seven tracks the trail, closes in and fires a seeker. When it hits, you have a six-second firing solution: the ship shows, cloak or no cloak, and every torpedo and phaser that bears goes into the system you named, again and again until it is out.

**Missions with real goals.** Battles can now ask more of you than winning: beam the crew off a crippled ship before her reactor fails, get a convoy to the shipping lane, or catch a runner before she escapes with her report. The enemy goes for whoever you are protecting. Border Patrol is rebuilt around three such missions, and Patrols can deal you one too.

**Counsel from your officers.** Press **O** in battle and Worf, Spock, Geordi and Seven each offer a plan for the fight in front of you, with live numbers and two to four orders you can see. Press 1 to 4 to follow one officer all the way, or click single steps to mix their advice. Aim them at a goal with `counsel disable the talon's engines` or "counsel kill all the Borg cubes". The plans change as the battle does, and none of this needs the AI model.

**Starfleet's assessment.** After each battle, a page tells you how it went: the mission, lives saved and lost, your conduct, the cost, a commendation when you earned one, and a word from each officer whose work showed. Before each stop of a tour, the Ready Room gives every officer's view of what lies ahead.

**All she's got.** Ask Geordi to "give me all she's got" (or type `boost`) and an engineering team keeps the warp drives from overheating for a while, so they run 40% longer at full warp. The cost is that other repairs go at half speed until the team is back. When the drives run hot, Geordi will offer it himself.

**Finding cloaked ships.** Torpedoes fired at a ship you can't see now get a report: a hit, a near miss, or no sign of her. A hit shows her long enough to aim. When an enemy cloaks, your science officer gives her last position, and "Seven, find the Talon" (or `hunt talon`) works the detectors until she shows, then makes her your target.

**The Captain's Manual.** A full manual, nine chapters on command, tactics and the crew, plus every help page and live tables of ships, torpedoes and orders. It is in the game under H, and as one book in `docs/MANUAL.md`.

**Shorter orders.** Shortened words now settle by the rest of the line, so `pu tal` pursues the Talon rather than asking whether you meant pulse.

**Everyday words, no model needed.** About sixty things a captain actually says now work with no language model: "red alert", "come about", "hard to port", "punch it", "attack the Gorkon", "get us out of here", "target the nearest enemy", "damage report", "zoom in", and "make it so" (or "aye") to take an officer's proposal, "not now" to turn it down. "Her", "them" and "the target" mean the ship you have targeted, or the nearest enemy. The manual's Orders in plain English page lists them under "Without a model".

**Command the fleet in plain words.** With no model, "all ships, attack the Gorkon", "fleet, form up on me", "squadron, hold fire" and "task force, report" reach every ally (`tell all ...` in the console), and an ally's name first speaks to her: "Yorktown, defend me", "Excalibur, fall back". "More power to the engines" is Geordi's boost, "divert power to the aft shields" reinforces that shield, and plain `reinforce` picks the one facing the enemy. "Give me warp 8", "ahead full", "lay in a course for the Gorkon" and "can you get the warp drive back?" work too.

**Calmer screens.** No word is drawn over another anywhere, at any window size. The log wraps a long report instead of cutting it, the map opens with the nearest enemy in view, ship names sit above every hull, the PAUSED banner keeps clear of the counsel, and Geordi stays quiet about a scratch and grows grave only below half hull. One stray Esc on the main menu no longer ends the game: it asks, and a second press quits. Settings sections answer the number keys.

**A Borg cube on the title screen.** Every few passes, the Enterprise on the main menu now meets a Borg cube that comes out of a green transwarp conduit, cuts at her shields, adapts to her phasers and breaks up under a heavier spread, taking turns with the Klingon who decloaks. Press **B** (or **K**) on the menu to call one for her next pass.

**Lean, steady model requests.** However long a battle runs, each request to the language model now stays the same small size: only the last few exchanges go, the oldest are dropped to fit a fixed budget, and the unchanging rules come first so Anthropic's prompt cache and Ollama can reuse them. On Ollama the game sets the context window itself (8,192 tokens unless you set `--llm context=`), so an overflowing prompt is never cut silently.

**Everything fits.** Every line of text now stays inside its panel and on the screen, on small windows as well as large ones. On short windows, the battle moves the Weapons and Target panels into the tabs at the bottom so nothing runs off the screen. The Ready Room fits a 1024×640 window too, and the counsel no longer sits under an officer's proposal on a small screen.

## What's new in 1.2

**Begin : Trek.** The title screen now carries the remake's own name; Begin is the original game it remakes.

**Settings in the game.** A Settings page on the main menu (S) changes everything you used to edit in the config folder: display, sound with a sample of each phaser and torpedo, the speed battles start at, the bridge style and its parts, speaking orders, the officers' language model and the character voice model (each with a Test button), and your officers' names, ranks, traits and how they speak. Each change is saved at once; in `officers.toml` only the line you change is written.

**Command from the bridge.** Every order you give is read back by the officer at that station ("Course 090, warp 6."), and officers speak in subtitles low on the map, with the log split into Bridge and Computer columns. Right-click a ship (or press E) for a command wheel; while you type, the battle eases to a quarter speed, the map shows a ghost of what Enter would do, and Tab finishes names. Officers now and then propose an order (Y makes it so, N belays it). `alert red`, `yellow` and `green` give a set of orders at once, `record` saves what you just did as a named order, the new Orders tab holds them all as cards, and `style` promises a way of commanding for a ribbon. Each officer's trust in you grows across battles, from Green to Veteran, and changes what they will do. None of it replaces anything: keys, clicks and the console work as before, and `hud bridge classic` turns it all off.

**Speak your orders.** Hold Right Alt (Option on a Mac), say the order, let go. The Mac's own recogniser, whisper.cpp on your computer, a whisper.cpp server or a cloud service hears it; the `voice` page picks one and tests it. The first time, your computer asks whether Begin may use the microphone.

**Patrols.** A new mode on the main menu (P): a fresh single battle each time, one of five situations (an ambush, a wolf pack, a second wave, an escort or an enemy flagship behind her screen) against a random enemy.

**Sharp on Retina and 4K.** The game now draws at your screen's real pixel density through the graphics card, so text, hulls and beams are crisp. Weapon fire lights the hulls near it, beams and blasts have a soft glow, and panels cast a soft shadow. The Display section of Settings (D) shows what is drawing and lets you choose; where the graphics card can't be used, the game draws as before.

**Officers of your own, and voices for the aliens.** The `officers.toml` file in your config folder can now give an officer a new name, rank, background, interests, quirks and lines of their own. An optional second language model can speak for the characters alone, for richer Klingon, Romulan and other alien speech (Settings → Character voices on the main menu, V).

**Tougher fleets.** The enemy fleets in the preset battles are larger again, so the Dreadnought has a real fight: an AI captain flying her wins about two battles in three. Map labels are easier to read, ships in close formation share one label, and a faint nebula drifts behind the stars.

**Klingons that look Klingon.** The battle cruiser, frigate and dreadnought are redrawn on the classic plan: a command pod on a long boom, a slim engine hull, and thin wings swept back to long nacelles. The escort is now a bird-of-prey, with a wedge head, broad wings and a disruptor cannon at each wingtip. Zoomed out, every ship is drawn as one clean, smoothed silhouette instead of a tangle of outlines, and a ship's speed line starts at her bow so it no longer runs through her.

**Big battles run faster.** Enemy captains decide exactly as before, but working out how to dodge torpedoes now takes half the time, so a 60-ship battle runs about twice as fast.

**Small fixes.** Ship names near the edge of the map stay on screen, the target and contact lists no longer spill out of their panels, and the helm officer doesn't repeat the incoming-torpedo warning every few seconds.

## What's new in 1.1

**Weapons you can read at a glance.** A phaser bank glows as it charges, then its beam races to the target and stops where the blow really landed: on the shield if it held, on the hull if it got through. A full-power volley is heavier than a weak or point-defense shot. Klingon and Orion disruptors fly as real bolts. Torpedoes are drawn each nation's own way (a turning photon star, a harsh Klingon flare, a wobbling Romulan plasma ball) and stay easy to find at any zoom, and a round heading for you is ringed with its fuse radius, or marked at the edge of the map when it's off screen.

**Hits you can feel.** The struck shield arc lights up, a facing that gives way bursts into sparks, breached hulls vent, system hits flash, and a heavy blow on your own ship jolts the map (`hud jolt off` turns that off).

**A fuller soundscape**, all synthesised by the game, and only when sound is on: phaser charge and ray, the torpedo tube, an incoming warning, shield, collapse and hull hits, a three-whoop red alert, lock and console tones, hail whistles, distant fire heard muffled, and a low ship's hum that follows your warp and ducks under the big moments (`sound hum off`, or `sound hum 0-100`).

**Tougher enemies.** The Enterprise is a Dreadnought from the start, and enemy captains now dodge torpedoes, fire snap shots, flee blasts and fight in their nation's style (Klingons charge, Romulans feint, Orions raid), with fleets sized to match. The HUD no longer overlaps PAUSED and RED ALERT, and drawing is faster.

## Download and play

Pick the file for your computer below. You don't need Python or anything else installed.

| Computer | File | How to start it |
|---|---|---|
| Windows 10 or 11 | `Begin-windows.exe` | Double-click it. |
| Mac with Apple Silicon (M1 or later) | `Begin-mac-apple-silicon.zip` | Double-click the zip, drag `Begin.app` into Applications, then open it. |
| Mac with an Intel chip | `Begin-mac-intel.zip` | The same as above. |
| Linux (64-bit) | `Begin-linux-x86_64.tar.gz` | Extract it, then run `./begin`. |

Not sure which Mac you have? Apple menu > About This Mac: "Chip: Apple M…" means Apple Silicon, "Processor: Intel" means Intel.

### The first time you open it

These builds aren't signed with a paid certificate, so your computer will be cautious the first time.

**Windows** may show "Windows protected your PC". Click **More info**, then **Run anyway**.

**macOS** may say Begin "can't be opened" or "Apple could not verify" it. Click **Done**, open **System Settings > Privacy & Security**, scroll down to the message about Begin and click **Open Anyway**, then confirm. On older macOS you can instead right-click `Begin.app` and choose **Open**. You only need to do this once.

### Your settings

The game makes a `Begin config` folder beside itself, holding plain text files you can edit (the **Open config folder** button on the main menu takes you there). Keep that folder with the game if you move it. On a Mac, open the game from Applications (or any folder of yours) rather than straight from Downloads, so it can save settings.

The officers' talking-AI is optional; the game plays fully without it. See the README in the `Begin config` folder to set it up.
