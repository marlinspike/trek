# BEGIN : TREK: The Captain's Manual

> This manual is built from the game itself: the same pages the in-game manual shows (press **H**), and tables drawn from the game's own data. When the game changes, so does this book. Regenerate it with `python -m begin.help.book`.

## Contents

**Part One: Command**

1. [Taking command](#topic-welcome-aboard)
2. [The powers of the galaxy](#topic-the-powers)
3. [Your crew](#topic-your-crew)
4. [How a battle works](#topic-how-battle-works)
5. [Giving orders](#topic-giving-orders)
6. [The arsenal](#topic-the-arsenal)
7. [The sword and the mind](#topic-sword-and-mind)
8. [Hidden depths](#topic-hidden-depths)
9. [Battles and campaigns](#topic-campaigns)

**Part Two: The ship's manual**

- Getting started: [Welcome aboard](#topic-index), [Keyboard and mouse](#topic-controls), [The command console](#topic-console), [Your first battle](#topic-first-battle), [Orders in plain English](#topic-plain-english), [The bridge](#topic-bridge), [Speaking orders](#topic-voice-orders)
- Coach: [Coach](#topic-coach), [Choosing weapons](#topic-weapons-guide), [Tactics](#topic-tactics)
- Helm: [Course and speed](#topic-helm), [Pursue and elude](#topic-pursue)
- Weapons: [Fire](#topic-fire), [Phasers](#topic-phasers), [Torpedoes](#topic-torpedoes), [Cease fire](#topic-ceasefire), [Probes](#topic-probes), [Lock and turn](#topic-lock), [Loading and autoload](#topic-loading), [Fire control and point defense](#topic-firecontrol), [Targeting](#topic-targeting), [Who fired what](#topic-weapon-colors)
- Defense: [Shields](#topic-shields)
- Sensors and status: [Status displays](#topic-status), [Chart](#topic-chart), [Display range](#topic-range), [Scan](#topic-scan), [Library computer](#topic-library)
- Ship systems: [Repair](#topic-repair), [Engine boost](#topic-boost), [Tractor beam](#topic-tractor), [Docking](#topic-dock), [Cloaking device](#topic-cloak), [Tachyon detector torpedo](#topic-tachyon), [Transporters and boarding](#topic-transport), [Deflector tachyon pulse](#topic-deflector), [Self-destruct and surrender](#topic-destruct)
- Allies: [Ally orders](#topic-tell), [Fleet and groups](#topic-fleet)
- Crew: [Bridge officers](#topic-crew), [Giving an officer the bridge](#topic-conn), [Talking to your officers](#topic-talking), [Disabling or taking out enemy ships](#topic-disable), [Officers and language models](#topic-llm), [Crew morale](#topic-morale), [Hailing enemy captains](#topic-hailing), [Counsel from the bridge](#topic-counsel), [Away teams and the shuttle](#topic-away-team)
- Game: [Time, pause and quitting](#topic-time), [Key macros](#topic-keys), [Settings](#topic-settings), [Named tactical orders](#topic-orders), [Alert conditions](#topic-alert), [Sound](#topic-sound), [After the battle](#topic-after-battle), [Command styles and trust](#topic-styles), [Missions](#topic-missions), [Tours of duty](#topic-tour), [Patrols](#topic-patrol), [Display and sharpness](#topic-display), [Fighting the Borg](#topic-borg), [Writing help pages](#topic-writing-help)

**Appendices**

- [Ship classes](#appendix-ships)
- [Torpedoes](#appendix-torpedoes)
- [Probes](#appendix-probes)
- [Phaser damage by range](#appendix-phaser-falloff)
- [Every order the console knows](#appendix-orders)

# Part One: Command

<a id="topic-welcome-aboard"></a>

## Taking command

*What BEGIN : TREK is, and how to read this manual.*

You command the Enterprise, a Federation Dreadnought, at the edge of known space. Around you is a living galaxy. Klingon captains fight for honour and close to point-blank range. Romulans strike from under their cloaks and are gone before you can answer. Orion pirates fight for profit and run when the profit runs out. The Borg do not fight like captains at all. On your bridge stand officers with minds of their own: Spock, Worf, Geordi La Forge and Seven of Nine, with Sulu, Chekov and the Doctor beside them.

BEGIN : TREK is a remake of *Begin*, a classic tactical starship simulation. Every Begin command still works as it was written. On top of Begin's battles the remake adds:

- a bridge crew you can talk to
- enemy captains you can reason with
- campaigns where your damage and your reputation follow you from one fight to the next
- the Borg

### The sword and the mind

There are two ways to win, and the best captains use both.

**The sword** is the ship. It means:

- phasers that hit hardest up close
- torpedoes that must be fired inside an envelope to hit at all
- six shields that each guard one side of the hull
- a power budget that cannot pay for everything at once

You win with the sword by choosing the range, turning a fresh shield to the enemy, aiming at the system that matters, and landing everything at once.

**The mind** is everything else. It means:

- reading an enemy captain's temper
- talking a beaten crew into surrender
- baiting their point defense with one torpedo before the salvo
- letting Seven study a Borg ship until she finds the one system that puts every drone aboard to sleep
- reading a cloaked ship's leaking warp plasma, then programming a torpedo to follow it home

Some battles can be won with the sword alone, at a cost. Against the Borg, power alone loses, but power through an opening that guile has made can tear a cube apart. The game is built so that thinking is always worth it.

### How to read this manual

**Part One, Command**, is about playing well. It covers:

- the powers you will meet
- the officers you command
- how a battle works underneath
- how to give orders
- the weapons
- tactics, and the moves that are not obvious

Read it before your first tour of duty and again after it. Things will mean more the second time.

**Part Two, the ship's manual**, is the reference: every command, by station. The same pages are in the game: press **H** in battle, or type `help <anything>`.

The tables in this manual come straight from the game's data, so the numbers are the numbers the game uses. Example commands are written as you would type them:

```text
help
coach
seven, what do you recommend?
```

If you have never played, start with [Your first battle](#topic-first-battle), or choose **Coach & training** on the main menu.

See also: [Your first battle](#topic-first-battle), [The powers of the galaxy](#topic-the-powers), [Your crew](#topic-your-crew), [The sword and the mind](#topic-sword-and-mind).

<a id="topic-the-powers"></a>

## The powers of the galaxy

*Who you will meet out there, how each of them fights, and what each will listen to.*

Five powers meet in this galaxy, and each fights in its own way. Knowing how an enemy thinks is half of beating it.

### The Federation

Your own side. Starfleet ships are balanced and well built, with sophisticated computers. The computer keeps tracking a contact your sensors have lost, plotting where it should be from its last course and speed. Starfleet helms are drilled in **evasive manoeuvres** (`evasive`), which no other power has.

Starfleet point defense is disciplined: one bank for each incoming torpedo, with the rest kept charged. Your crews start a fight in good spirits and are hard to shake. Federation captains fight with the same rules of engagement you do. They prefer to disable a ship rather than destroy it, and they rarely give up a ship. In a three-way fight, or with a side switched on the main menu, you may meet them as rivals.

### The Klingon Empire

Klingons fight up close. Their phasers are their main weapon, and many of their captains favour **the charge**:

1. a full-speed run to point-blank range
2. an alpha strike
3. a break away to recharge
4. the same again

Their crews start a fight in higher spirits than Starfleet's and hold under fire. Watching their allies die makes Klingon captains **angry**, not afraid. They fight harder and go after the ship that did it.

They almost never surrender. When beaten, a Klingon crew may ram you or blow up their own ship, so keep your distance from a dying Klingon. Their point defense is trigger-happy. Several banks fire at a single torpedo, which is exactly what makes them easy to **bait** (see [Disabling or taking out enemy ships](#topic-disable)).

A Klingon captain will not surrender to a demand. Your tactical officer may remind you that a way to **withdraw with honour** is another matter.

### The Romulan Star Empire

Romulans prefer not to be seen. Their ships carry **cloaking devices**, and their captains cloak to close in and to reposition. Many favour **the feint**: they turn and run when you close, often vanishing as they go, then turn back on their pursuer with a full spread.

Their **plasma torpedoes** home in on their target, but they weaken the further they fly. A Romulan wants to fire from close in, and you want to make every shot a long one.

Romulan crews are disciplined. Their point defense won't fall for bait, and their captains are the hardest of anyone to talk round at the start. They almost never surrender, and they are the most likely of all to destroy their own ship rather than lose it. The patrols rate Romulans the hardest enemy in the game.

To fight them, read [Cloaking device](#topic-cloak) first.

### The Orion Pirate Guild

Orions are fast, brittle and in it for the money. They fight in loose packs and favour **the raid**: dart in, fire one volley, and get out of reach before you can answer. Their ships are lightly built, and their crews start in the lowest spirits of any power and break quickly once the fight stops paying.

They are the readiest of all to surrender, and the easiest to frighten. A battered pack can often be talked out of the fight entirely. Their point defense is even more trigger-happy than the Klingons'.

### The Borg Collective

The Borg are not a navy, and none of the usual rules apply to them:

- They do not bargain, retreat or surrender.
- Every weapon that hurts them teaches the whole Collective to shrug it off.
- Their hulls grow back.
- Their drones beam aboard to make your crew into more drones.

Trading shots with the Borg loses. You win by learning them first and then striking hard. They have a whole page of their own: [Fighting the Borg](#topic-borg).

### Every power at a glance

#### United Federation of Planets

- **Ships:** Tug, Interceptor, Destroyer, Heavy Cruiser, Dreadnought, Tanker, Starbase.
- **Torpedoes:** Federation Mark 7, Federation Mark 8. **Probes:** Federation Probe X-2, Federation Probe Data-2.
- **How they fight:** they lean on their torpedoes; their helms are drilled in evasive manoeuvres.
- **Terms:** watching their allies battered makes them wary; at the start they are stubborn, and they rarely strike their colours. Crew spirits start at 80.

#### Klingon Empire

- **Ships:** Escort, Frigate, Battle Cruiser, Dreadnought, Outpost.
- **Torpedoes:** Klingon TX torpedo. **Probes:** Klingon Light Pak Probe, Dreadnought Killer (dink), Klingon Data Probe.
- **How they fight:** they lean on their phasers; many of their captains favour the charge: a point-blank run at full speed, an alpha strike, a break to recharge, and again.
- **Terms:** watching their allies battered makes them angry; at the start they are stubborn, and they almost never strike their colours. Crew spirits start at 85.

#### Romulan Star Empire

- **Ships:** War Eagle, Frigate, Bird of Prey.
- **Torpedoes:** Romulan Plasma Torpedo, Plasma X Torpedo. **Probes:** Romulan Pak Probe, Romulan version of Klingon Data Probe.
- **How they fight:** they lean on their torpedoes; many of their captains favour the feint: they turn and run when you close (cloaking if they can), then turn on the pursuer with a full spread; they cloak to close and to reposition.
- **Terms:** watching their allies battered makes them wary; at the start they are very stubborn, and they almost never strike their colours. Crew spirits start at 75.

#### Orion Pirate Guild

- **Ships:** Assassin, Raider, Saboteur, Anarchist, Armadillo.
- **Torpedoes:** Orion Bullet Torpedo, Orion Shield Auger. **Probes:** Klingon Light Pak Probe.
- **How they fight:** they lean on their phasers; many of their captains favour the raid: in, one volley, and out of reach before you can answer.
- **Terms:** watching their allies battered makes them frightened; at the start they are easily talked round, and they readily strike their colours. Crew spirits start at 60.

#### The Borg Collective

- **Ships:** Probe, Sphere, Cube.
- **Torpedoes:** Borg torpedo. **Probes:** none.
- **How they fight:** they lean on their phasers.
- **Terms:** none. The Collective never bargains, never retreats and never surrenders.

### How they see you

Enemy captains watch the battle as it happens. Every shield you collapse, every hull you breach and every ship of theirs destroyed or taken changes how the captains still fighting feel. Depending on their temper, it makes them **shaken** or **enraged**. On a tour of duty they also remember how you fought:

- Fire on a ship that surrendered and no one will surrender to you again.
- Lean on aimed fire and boarding parties and their captains grow wary.
- Run your magazines dry and they close in.

See [Hailing enemy captains](#topic-hailing) and [Tours of duty](#topic-tour).

See also: [Hailing enemy captains](#topic-hailing), [Fighting the Borg](#topic-borg), [Cloaking device](#topic-cloak), [Choosing weapons](#topic-weapons-guide).

<a id="topic-your-crew"></a>

## Your crew

*The officers on your bridge: who they are, what each does best, and how to command them.*

A captain is only as good as the bridge. Your officers can run their stations for you, take the whole ship, work on projects together, argue their case, and remember how you treated them. Each of them is a person, with traits, a temper and a way of speaking. Those change how they talk, never how well they do the job.

| Officer | Station | How they come across |
|---|---|---|
| **Commander Spock** | Helm; takes science for Seven of Nine when needed | precise and emphatic, dry wit, unflappable |
| **Lieutenant Worf** | Tactical | honour-bound, blunt, impatient for battle, fiercely loyal |
| **Lieutenant Commander La Forge** | Engineering | upbeat, technically fluent, born problem-solver, calm under pressure |
| **Seven of Nine** | Science | highly effective, efficient, coolly confident, ex-Borg precision |
| **Lieutenant Sulu** | Stands by; takes tactical for Worf when needed | unflappable, quietly confident, a duellist's patience |
| **Ensign Chekov** | Stands by; takes helm for Spock when needed | eager, quick, proud of where he comes from, young and brave |
| **The Doctor** | Sickbay | acerbic, brilliant, put-upon, secretly devoted to his patients |

### Who they are

**Commander Spock** runs the helm and advises on every station. He holds a careful, calculated range, quotes the odds, and keeps an eye on the damage. When a system is badly hurt he offers to direct the repair crews, and once you agree he sets the priority as the fight changes (`spock, manage repairs`). With the conn he fights like the logician he is. When Seven is away, he takes the science station, a little more slowly against the Borg.

**Lieutenant Worf** runs tactical: targets, phasers, torpedoes, probes and point defense. Given the conn, he closes fast and hits hard. He can `capture` a ship for you: he opens a hole in her shields, thins her crew and boards her. Against the Borg he is the one who takes the shuttle across ([Away teams and the shuttle](#topic-away-team)). He will remind you that a Klingon captain does not surrender to a demand.

**Lieutenant Commander Geordi La Forge** runs engineering: shields, reinforcing, repair priorities and the cloak. He tells you when the hull or the engines are in trouble, warns you when your own warp drive is venting a trail, and can put a team on the engines when you need **all she's got** ([Engine boost](#topic-boost)). Given the conn, he looks after the ship first.

**Seven of Nine** runs science. She scans everything, efficiently. Tell her what to knock out and on whom (`seven, disable their shields`) and she plans it and carries it out:

- She scans the target.
- She aims the phasers tight.
- She fires torpedoes in one close salvo fused to burst on a ring, so a dodge in any direction still meets a blast.
- Against a trigger-happy crew she baits their point defense first.

She and Spock build the [Tachyon detector torpedo](#topic-tachyon) detector and the [Deflector tachyon pulse](#topic-deflector) pulse that find cloaked ships, and the plasma-seeker that follows a leaking drive. Against the Borg she is indispensable. She knows the Collective from the inside: she tunes your shields against them, studies their ships, and finds the vinculum relay.

**Lieutenant Sulu** stands by and takes tactical when Worf is away or hurt. **Ensign Chekov** takes the helm when Spock moves to cover science.

**The Doctor** runs sickbay. He runs no station, but he is aboard in every battle:

- He mends an away team that comes back hurt and sends them back to duty.
- He studies the drones you rescue, which makes every later scan of the Borg go further.
- With Seven, he can inoculate the crew against assimilation (`design inoculate`).

### Handing over the work

| You say | What happens |
|---|---|
| `delegate tactical`, "Worf, take tactical" | that officer runs their station; you can still give any order yourself |
| `seven, take the bridge`, `conn spock` | one officer runs every station, in their own style |
| "I have the helm", `assume all`, `stand down` | the station, or everything, comes back to you |
| `seven, disable their shields`, `capture gorkon` | an officer takes on a whole job and reports as it goes |
| `spock, manage repairs` | Spock directs the repair crews |

Your own orders always come first. Anything you order overrides an officer for a few seconds, and then they carry on. Officers never retreat, surrender, self-destruct, beam across or give orders to your allies: those decisions are yours.

### Working together

Some things take two or three of them. Ask any of them in your own words ("Spock, there's a cloaked ship out there") or use `design`:

| Project | Built by | Ask for it with |
|---|---|---|
| Plasma-seeker torpedo | Seven of Nine and Spock | `design seeker` |
| Harmonic torpedoes | Seven of Nine, Worf, Spock and Sulu | `design harmonic` |
| Counter-nanoprobe inoculation | The Doctor and Seven of Nine | `design inoculate` |
| Computer lockout | La Forge, Seven of Nine and Spock | `design encrypt` |
| Link to the hive cut | Seven of Nine, Spock and La Forge | `design sever` |
| Deflector tachyon pulse | Spock and Seven of Nine | `design deflector` |
| Tachyon detector torpedo | Spock and Seven of Nine | `design tachyon` |

Each takes some cycles of work, and longer if the ship has lost crew. The officers tell you when it starts and when it is ready.

### Talking to them

Start a line with an officer's name and talk:

- "status" or "sitrep" gets a report on their station.
- "what do you recommend?" gets their best idea, with the command that carries it out.

They answer from what your sensors know, never more. Now and then an officer at a station you are running proposes an order ("Torpedoes inbound, Captain. Evasive manoeuvres?"). **Y** makes it so and **N** belays it. With a language model connected ([Officers and language models](#topic-llm)), they answer in their own words and never repeat a line. Without one, they use lines written for them. Either way, `crew chatter off` quiets them, though an officer working a job still says what they are doing.

### Counsel

Press **O** (or type `counsel`) and all four lay out a way forward at once, each from their own station: Worf the sword, Spock geometry and the mind, La Forge keeping the ship alive to win, Seven knowing before striking. Each plan is two to four console lines built from the live fight, and the panel is rebuilt as the fight changes. Go all in on one (**1** to **4**) or click single steps from several; both can win. Name a goal (`counsel disable all their engines`) and each plans toward it. The battle slows while you read; press **Space** first to stop it entirely. See [Counsel from the bridge](#topic-counsel).

### Trust and rapport

They remember. Thanks and taking their advice build **rapport**, and insults wear it down. Rapport colours how they speak to you. **Trust** grows as you fight together: for each proposal you accept, each battle won at their post, and each time they stand out in the debrief. Trusted officers propose even while you type. Veterans act on an urgent proposal themselves if you leave it unanswered. See [Command styles and trust](#topic-styles).

You can make any of them your own in `config/officers.toml`: their name, traits, way of speaking, interests and lines. See [Talking to your officers](#topic-talking).

See also: [Bridge officers](#topic-crew), [Giving an officer the bridge](#topic-conn), [Talking to your officers](#topic-talking), [Disabling or taking out enemy ships](#topic-disable), [Command styles and trust](#topic-styles).

<a id="topic-how-battle-works"></a>

## How a battle works

*What happens underneath: time, power, heat, shields, damage, crew, sensors and the end of a battle.*

Every battle runs on the same rules for every ship, yours and the enemy's. Nothing on the other side cheats, and nothing on yours is hidden from you. Learn these rules and you can read a fight before it turns.

### Time

A battle runs in **cycles**. At normal speed one cycle is one second, and everything is measured in cycles: reloads, torpedo flight, repairs, countdowns. Every battle begins **paused**. You can give orders, read displays and open this manual while paused, and the orders take effect when you resume. `time 0.25` to `time 4` slows or speeds the battle, and nothing about the outcome depends on the speed you play at.

The game is fully repeatable. The same starting position and the same orders always give the same result. A patrol's number, or a preset's seed, always gives the same battle.

### Movement

The helm takes a **course** (a compass bearing, 0 straight up the map) and a **warp**. One warp factor is 100 units of distance per cycle. Heavy ships turn slowly and light ships turn on a coin.

Your top speed is set by your class, by the health of your warp drives and by the power left over. A damaged drive slows you down before it fails.

**Heat.** Running above cruise warp heats the drives. Past their temperature limit they burn out for good, and only a starbase can rebuild them. Fight at the warp you need, not the warp you have, or ask Geordi for a team on the engines ([Engine boost](#topic-boost)).

**Leaving.** A ship that stays more than 60,000 units from every enemy for ten cycles has escaped the battle. An escaped ship is not lost.

### Power

Reactors make energy and batteries store it. Each cycle the energy goes out in a fixed order:

1. life support
2. shields
3. the cloak
4. the tractor beam
5. charging weapons: phasers first, then torpedo tubes

Warp draws on the same budget, so speed is paid for in shields and firepower. If what is left can't pay for every raised shield, **none of them hold** that cycle.

When power is tight, you have several options:

- Lower the shields that face away from the enemy.
- Slow down.
- Disable banks you don't need (`disable banks 3 4`). They keep their charge but stop drawing.

A ship whose power fails goes dark. Every side can see it, and her life support starts to fail, so her crew has moments left.

### Shields

Six shields each guard a 60° slice of the hull:

| Shield | Covers |
|---|---|
| 1 | the bow |
| 2 and 3 | the forward quarters |
| 4 and 5 | the aft quarters |
| 6 | the stern |

A hit is taken by the shield facing the attacker, and the others are untouched. A shield absorbs damage up to its strength, and each hit drains it by only a fraction of what it absorbed, so a strong shield can swallow whole volleys. A shield knocked down comes back within a few cycles. A shield **generator** destroyed by aimed fire leaves a permanent hole.

This is the heart of the fight: **turn a fresh shield toward the enemy, and make them hit a tired one.** `reinforce <n>` makes one shield lose strength at half the rate, at four times the energy cost.

### Damage

What gets past a shield strikes the **hull**, a pool of structure, and the **systems**, each placed at a real point on the hull. A hit from astern lands among the systems aft. Weapons are knocked out one mount at a time, drives slow the ship, and reactors cut the power. A ship can be crippled without being destroyed, and that is often the point.

Aimed fire (`target gorkon shields`, `aim life support`) sends what gets through toward the system you choose and does only about a third of the usual damage to the hull. A system knocked out by aimed fire takes her crew about three times as long to repair.

### Crew

Crew run the ship. Every hit that reaches the crew decks costs lives. Fewer crew means slower repairs, and below a tenth of the complement a ship can't repair at all. **Morale** is the crew's will (see [Crew morale](#topic-morale)): at 100 repairs run 25% faster and tubes load 15% faster, and at 0 the same amounts slower. An enemy crew in low spirits makes their captain readier to retreat or yield.

**Boarding.** When your shield facing a ship and at least one of hers are both down, your transporters can put a party aboard within 3,000 units. If her defenders fall below six while six or more of your boarders stand, she is yours. See [Transporters and boarding](#topic-transport).

### Repairs

Crews repair on their own, a little each cycle. `repair <system>` puts one system first: four times faster, and everything else at half speed. A **destroyed** system is rebuilt from nothing and takes the longest, and warp drives are the slowest of all. In battle the hull is patched at a quarter of the usual rate, and in space only up to 75%. A starbase does the rest, and repairs everything twice as fast while you are docked. See [Repair](#topic-repair) and [Docking](#topic-dock).

### Sensors

Each side sees the battle through its own sensors, pooled from every ship and data probe it has. What you see is what you know:

- **Contacts** appear as your sensors find them. A ship you haven't scanned shows as `#7` until a detailed `scan` identifies her.
- At the edge of sensor range a contact's position is hazy.
- A contact you have lost keeps its last known position. Starfleet computers keep plotting where it should be from its last course and speed.
- A **scan** shows her shields, systems, crew and loaded weapons, as of that moment. Your own hits keep you informed between scans: the log tells you how much a volley took off her shield.
- A **cloaked** ship can't be seen at all, except when it fires, when it is hit, when a tachyon burst lights it up, or when its leaking warp plasma gives it away. See [Cloaking device](#topic-cloak).

The enemy's AI captains see exactly this much of you, and no more.

### How a battle ends

A battle ends when only one side has ships still fighting. Ships stop fighting when they are destroyed, captured, surrendered or abandoned, or when they escape. When the last enemy is left helpless, the battle stays open for 60 cycles so you can board her.

Afterwards the **assessment** shows the score, each ship's record, and the officer who did the most for you. See [After the battle](#topic-after-battle).

See also: [Time, pause and quitting](#topic-time), [Shields](#topic-shields), [Repair](#topic-repair), [Crew morale](#topic-morale), [Scan](#topic-scan), [Status displays](#topic-status).

<a id="topic-giving-orders"></a>

## Giving orders

*Every way to give an order, from Begin's terse console to plain words, your voice, the wheel and battle plans written in advance.*

You can command the ship however suits the moment. All of these do the same things, so mix them freely:

- keys and the mouse
- a radial wheel
- Begin's console
- plain words
- an officer's name
- your voice
- a plan written before the battle

### Keys and the mouse

The fastest orders are single keys:

| Key | Does |
|---|---|
| **Tab** | targets the nearest enemy |
| **F** | fires phasers |
| **T** | fires torpedoes |
| **P** | fires probes |
| **W** and **S** | change warp |
| **A** and **D** | turn |
| **G** | raises or lowers every shield |
| **V** | cycles point defense |
| **X** | scans your target |
| **R** | cycles which of her systems you aim at |
| **Space** | pauses |

Right-click the map to steer toward a point, and Shift+right-click a ship to pursue her. Every key is listed in [Keyboard and mouse](#topic-controls).

Right-click a ship, or press **E** for your target, to open the **command wheel**: phasers, torpedoes, disable, close to, hail, board, elude, target. Every slice is a console line, and the log shows it, so the wheel teaches you the console as you use it. See [The bridge](#topic-bridge).

### The console

Press **Enter** and type. The console speaks Begin's language, and any word can be cut short as long as it stays unique. All of these fire every torpedo tube:

```text
fire all torpedoes
fir tor al
ft
```

Lists of mounts can be written `1 2 3`, `1,2,3` or `1-3`. Ships can be named by any unique start of their name (`pursue gor`), or by contact number (`target #7`). Filler words such as *the*, *to* and *at* are ignored. Separate orders with `;` to send them together. **Tab** finishes the word you are typing. While you type, the battle eases to a quarter speed and a faint line under the console says what Enter would do. See [The command console](#topic-console).

### Plain words

Many orders can simply be said:

- "hit their shields"
- "finish her off"
- "I'll take the helm"
- "all stop"
- "take a shuttle over to the cube"
- "look for exhaust"
- "program a torpedo to follow her"

The console knows these without any setup. With a language model connected ([Officers and language models](#topic-llm)), it understands nearly anything you type. It shows the console commands it chose, marked **≈**, and then runs them, so you learn the real syntax as you play. The model never surrenders, self-destructs or ends the battle on its own reading of your words. See [Orders in plain English](#topic-plain-english).

### Talking to an officer

Start a line with an officer's name: `seven, scan gorkon`, `worf, fire all torpedoes`, `spock, what do you recommend?`.

- Each officer carries out orders for their own station. Worf will fire but won't steer.
- Each answers questions about their station.
- Some jobs are whole tasks, such as `seven, disable their shields`, `worf, capture her` or `spock, manage repairs`.

See [Talking to your officers](#topic-talking) and [Your crew](#topic-your-crew).

### Your voice

Hold **Right Alt** (Option on a Mac), say the order, and let go. What was heard runs exactly as if you had typed it, and a misheard order is never guessed at. See [Speaking orders](#topic-voice-orders).

### Battle plans

A **named order** is a plan you write before the fight, as a list of steps. In battle, one word runs the whole list. "Their" and "the target" mean whichever ship you have targeted when the step runs, so one plan works against any enemy.

```text
beta-1
record strike
record stop
orders
```

`record` turns what you just did into a plan you can run again. **Key macros** (`key F2 fire all torpedoes`) and **alert conditions** (`alert red`) are plans too. See [Named tactical orders](#topic-orders), [Key macros](#topic-keys) and [Alert conditions](#topic-alert).

### When an order can't be carried out

The log says why: "Unable to comply: No phaser banks are charged." Officers read every order back ("Course 090, warp 6."), so if what you hear isn't what you meant, say it again. To stop everything at once, say `cease fire` (the guns) or `stand down` (the guns and every officer). See [Cease fire](#topic-ceasefire).

See also: [The command console](#topic-console), [The bridge](#topic-bridge), [Talking to your officers](#topic-talking), [Orders in plain English](#topic-plain-english), [Named tactical orders](#topic-orders), [Speaking orders](#topic-voice-orders), [Key macros](#topic-keys).

<a id="topic-the-arsenal"></a>

## The arsenal

*Phasers, torpedoes, probes, point defense and the special rounds your officers build, and when each one is the right tool.*

Every weapon has a range where it works and a range where it is wasted. Most of winning with the sword is knowing which is which, right now, against this target.

### Phasers: the knife

Phasers hit the instant you fire, but they are short-ranged, about 2,000 units for most ships. They weaken with distance: at three-quarters of their reach a hit is half as strong as at point-blank. They also weaken with **spread**:

- A narrow spread (`spread 10`) puts the whole charge on one ship.
- A wide one (up to 45°) is weaker, but it can catch several objects at once, including incoming torpedoes.

Each bank recharges from the ship's power after it fires.

Damage per bank for a Dreadnought (charge 10, range 2,000) before shields:

| Range | Spread 10 | Spread 20 | Spread 45 |
|---|---|---|---|
| 0 | 22 | 11 | 5 |
| 500 | 19 | 10 | 4 |
| 1,000 | 16 | 8 | 4 |
| 1,500 | 11 | 6 | 2 |
| 1,800 | 7 | 4 | 2 |

Banks locked on a target follow her. Others hold a fixed **mark** relative to your bow. A bank can be given a **role**: offense, defense (kept for point defense), or both.

### Torpedoes: the spear

A torpedo flies straight at a fixed speed and bursts when it passes within its **proximity** setting of a ship. Its warhead doesn't weaken with range, apart from plasma, which fades. Before it can burst it must fly far enough to **arm**, and its time fuse ends its flight. Together these set the **envelope**:

- **Minimum range** is the arming time multiplied by the closing speed.
- **Maximum range** is the arming time plus the time fuse, multiplied by the closing speed.

A ship charging at you shrinks the minimum. A ship running away stretches it. Fire inside the minimum and the torpedo passes straight through her unarmed. The [Coach](#topic-coach) works the envelope out for your current target.

**Proximity is a trade.** A blast fades to nothing at the edge of its reach, so a wide proximity catches a nimble ship but barely scratches her, while a tight one hits hard but needs good aim. The coach suggests a balance.

**Fans.** Tubes locked on a ship lead her. `fire all torpedoes spread 10` fans a salvo around the lead point. A fan only helps once its width at her range is greater than the proximity, and too wide a fan leaves gaps she can slip through. At 6,000 units a 10° fan covers about 1,050 units, enough to catch a sharp turn.

| Torpedo | Id | Warp | Warhead | Arms at | Reach | Max prox | Guidance | Reload | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Romulan Plasma Torpedo | `plasma` | 15 | 30 plasma (fades with distance) | 1,500 | 19,500 | 750 | homing | 6 c | Romulan Bird of Prey, Romulan War Eagle |
| Federation Mark 8 | `mk8` | 15 | 21.6 antimatter | 1,425 | 10,425 | 800 | straight | 4 c | - |
| Plasma X Torpedo | `xplasma` | 21 | 18 plasma (fades with distance) | 2,100 | 25,200 | 500 | homing | 5 c | Romulan Frigate |
| Borg torpedo | `bgt` | 24 | 18 antimatter | 1,440 | 18,240 | 600 | straight | 4 c | Borg Cube, Borg Probe, Borg Sphere |
| Federation Mark 7 | `mk7` | 30 | 14.4 antimatter | 1,200 | 19,200 | 800 | straight | 3 c | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon TX torpedo | `ktx` | 27 | 10 antimatter | 2,700 | 18,900 | 500 | straight | 3 c | Klingon Battle Cruiser, Klingon Dreadnought, Klingon Escort, Klingon Frigate |
| Orion Bullet Torpedo | `opbt` | 20 | 8 antimatter | 2,000 | 12,000 | 400 | straight | 3 c | Orion Anarchist, Orion Armadillo, Orion Saboteur |
| Orion Shield Auger | `oshb` | 20 | 8 shield-bore | 2,000 | 12,000 | 400 | straight | 5 c | - |

**Warheads.** **Antimatter** is the standard warhead. A **shield-bore** warhead loses less to the shield it strikes, but it does not damage the hull. **Plasma** homes in on its target but fades as it flies.

### Probes: the patient weapon

Probes are slow, but most of them home in on their target, and their warheads are large. A ship slower than the probe can't outrun it, which makes probes the weapon for bases, cripples and big cruisers. After launch you can steer one, re-target it or detonate it by its control code (`status probes` lists them).

**Data probes** carry little or no warhead, but they fly fast and see far. Wherever one flies, your whole side sees what it sees.

| Probe | Id | Warp | Warhead | Arms after | Time fuse | Reach | Max prox | Sensor | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Dreadnought Killer (dink) | `dnk` | 3.5 | 30 | 5 c | 12 c | 4,200 | 1,500 | 0 | Klingon Dreadnought, Klingon Frigate |
| Romulan Pak Probe | `rmpp` | 2 | 28 | 6 c | 20 c | 4,000 | 1,000 | 0 | Romulan Bird of Prey, Romulan Frigate |
| Federation Probe X-2 | `px2` | 2.5 | 25 | 5 c | 20 c | 5,000 | 1,200 | 0 | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon Light Pak Probe | `klpp` | 2 | 20 | 6 c | 20 c | 4,000 | 1,000 | 0 | Klingon Battle Cruiser, Klingon Escort, Orion Anarchist, Orion Armadillo |
| Klingon Data Probe | `kdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Romulan version of Klingon Data Probe | `rdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Federation Probe Data-2 | `pxd2` | 20.5 | 0 | 1 c | 30 c | 61,500 | 1,200 | 20,000 | - |

### Point defense: the shield you fire

Point defense uses idle phaser banks to shoot down incoming torpedoes and probes. Choose how much of your firepower it may take:

| Doctrine | It uses |
|---|---|
| off | nothing |
| conservative | reserved banks, against imminent hits |
| balanced | reserved banks, plus flexible banks against dangerous salvos |
| aggressive | any idle bank, against anything armed and in range |

Every power mans its point defense differently. Klingon and Orion crews are trigger-happy and pour several banks onto a single round. That is why one torpedo fired a second ahead of a salvo, the **bait**, strips their defense bare. Romulan and Starfleet crews answer one bank per round. See [Fire control and point defense](#topic-firecontrol) and [Disabling or taking out enemy ships](#topic-disable).

### The special rounds

Your officers can build rounds no armoury carries:

- **The tachyon detector** (`design tachyon`, Spock and Seven). A torpedo whose burst lights up every cloaked ship within 6,000 units for about 30 cycles. It reaches about 39,000 units. See [Tachyon detector torpedo](#topic-tachyon).
- **The deflector pulse** (`design deflector`). Not a round: the main dish set up to sweep a 60° cone ahead of your bow, out to 15,000 units. It is reusable every 30 cycles. See [Deflector tachyon pulse](#topic-deflector).
- **The plasma-seeker** (`design seeker`, Seven and Spock). A torpedo that flies a damaged ship's plasma trail, every turn she made, and homes on her at the end of it. See [Cloaking device](#topic-cloak).
- **Harmonic torpedoes** (`design harmonic`). Against a Borg ship whose shield harmonics Seven has learned, they pass straight through her shields. See [Fighting the Borg](#topic-borg).

### Other tools

| Tool | What it does | See |
|---|---|---|
| Tractor beam | holds a ship within 1,000 units, to drag an ally clear or pin an enemy for your torpedoes and boarders | [Tractor beam](#topic-tractor) |
| Transporters | board, move crew, or move yourself to another ship, within 3,000 units through lowered shields | [Transporters and boarding](#topic-transport) |
| Cloak | every Romulan class, and the Enterprise's refit in one tour; enemy sensors can't see you until you fire or are hit | [Cloaking device](#topic-cloak) |
| Self-destruct | a blast proportional to your power, felt by everyone nearby; abortable until the last five cycles | [Self-destruct and surrender](#topic-destruct) |

### Weapon colours

You can tell who is firing by the colour and shape of their fire:

| Nation | Phasers | Torpedoes and their blasts |
|---|---|---|
| Federation | —— steady beam | ◆ torpedo, ○ blast |
| Klingon | - - - string of bolts | ◆ torpedo, ○ blast |
| Romulan | —— steady beam | ◆ torpedo, ○ blast |
| Orion | - - - string of bolts | ◆ torpedo, ○ blast |
| Borg | ≈≈ cutting beam that drags across the hull | ◆ torpedo, ○ blast |
| Not yet identified | —— white beam | ◆ white |

See also: [Fire](#topic-fire), [Phasers](#topic-phasers), [Torpedoes](#topic-torpedoes), [Probes](#topic-probes), [Fire control and point defense](#topic-firecontrol), [Choosing weapons](#topic-weapons-guide).

<a id="topic-sword-and-mind"></a>

## The sword and the mind

*How to win: the principles that decide every fight, a playbook for each enemy, and the many ways a battle can be won.*

Every battle is decided by a handful of things: who chooses the range, which shields take the hits, whether fire lands together or piecemeal, and who knows more about the other. Get those right and the dice matter far less.

### The principles

#### Choose the range

The side that chooses the range usually wins. Look at your weapons and at hers, then decide where you want to fight:

- **Torpedo-heavy ships** want to stand off inside their torpedo envelope and outside her phasers.
- **Phaser-heavy ships** want to close fast and stay close, where every hit is strongest.

Use `pursue <ship> warp <w>` to hold a chase, `elude <ship>` to keep away, and `pursue <ship> at 9000` (or `elude <ship> at 9000`) to hold her at a chosen range: the helm closes when she is beyond it, opens when she is inside, and circles her in between. The [Coach](#topic-coach) tells you which side of each envelope you are on. Remember that her motion moves the envelope: a ship charging at you shrinks your minimum range, and a ship running away stretches it.

#### Fight with your shields

You have six shields, and she can hit only the one that faces her. When the forward shield weakens, turn so a fresh one takes the next volley. Then work her shields the same way:

- Keep hitting the face she shows you until it collapses.
- If she turns, go after the new face.
- `reinforce` the shield you will keep toward her.
- When power is tight, lower the shields facing away from every enemy, so the ones that matter hold.

#### Mass your fire

Shields absorb a volley and then recharge. Fire that arrives a little at a time is soaked up. Fire that arrives all at once breaks through:

- Fire the whole salvo, not a tube at a time.
- Let banks charge, then fire them together.
- Tell your allies to attack the same ship (`tell 1 attack gorkon`).

Against the Borg this matters doubly, because every hit teaches them. Potshots teach them for free.

#### Strip, then strike

A ship with no weapons can't hurt you, and a ship with no engines can't run. Once a shield is down, aim through it at what matters most right now:

| Aim at | When |
|---|---|
| **weapons** | she outguns you |
| **engines** | she is about to run |
| **shields** | you want a permanent hole, one her crew can't simply recharge |
| **life support** | you mean to take her |

A system knocked out by aimed fire stays out three times longer than one knocked out by a lucky hit.

#### Spend power on purpose

Warp, shields, cloak and weapons all draw on one budget. Racing in at top warp leaves less for your shields when you arrive. Fight at the speed you need, keep the drives below their limit, and remember that a burned-out drive is gone for the rest of the battle, and for the rest of a tour until a starbase rebuilds it.

#### Know before you commit

A scan tells you her shields, her damaged systems, her crew, and how many banks are charged and tubes loaded. A ship that has just emptied her tubes is a ship you can close on. Scans go stale, but your own hits keep you current: the log reports what each volley took off her shield. Use data probes to see past your own sensors.

#### Use your bridge

You can't watch everything, and you don't have to:

- Hand the helm to Spock while you fight the guns.
- Hand Seven a job: disable their shields, take out her torpedoes, find that cloaked ship.
- When the battle is too big, give an officer the conn and step in only where it matters.

When you aren't sure, ask the whole bridge at once: **O** opens the [Counsel from the bridge](#topic-counsel), four plans from four perspectives, each a few console lines you can run whole or a step at a time.

Your orders always come first. See [Your crew](#topic-your-crew).

#### Know when to stop

Not every fight should be fought to the end. A beaten crew can be talked into surrender, and a Klingon into withdrawing with honour. A ship that gets 60,000 units clear of every enemy for ten cycles escapes, and on a tour an escaped ship is a ship you still have. See [Hailing enemy captains](#topic-hailing).

### The playbooks

#### Against Klingons

They will come to you. Most Klingon captains charge: a run to point-blank range, a massive volley, a break to recharge, and then they come again.

- Meet the charge with a full torpedo salvo fired early, while they are still beyond your minimum range.
- Turn a fresh shield into the alpha strike.
- Punish the break with phasers as they turn away and show you a new shield.
- Their point defense is trigger-happy, so **bait** it: one torpedo first, the salvo a cycle later.
- Watching their friends die makes them angry, not afraid. Expect the survivors to come for you.
- Don't demand a surrender. Offer a way to **withdraw** with honour.
- Keep your distance from a beaten Klingon, who may ram or blow up the ship.

#### Against Romulans

They decide when you see them.

- **Make the plasma fly far.** Plasma homes in but fades as it travels, so open the range and keep it open. Every unit it flies is damage it loses.
- **Don't chase blindly.** The feint is a turn and a run, often under cloak, that ends with a full spread at the ship that followed. Pursue at an angle, keep a fresh shield toward where she will turn, and keep your tubes loaded for the moment she shows.
- **When she vanishes:** your science officer gives the last fix and heading. Say `hunt <ship>`, or burst a tachyon detector a little ahead of where she was going. At close range, turn your bow toward her and use the deflector pulse.
- **When she is hurt:** a damaged warp drive vents plasma at warp, cloak or no cloak. `sweep` finds the trail and a plasma-seeker follows it. See [Cloaking device](#topic-cloak).
- Their point defense is disciplined, so it won't take the bait. Use Seven's ring salvo instead ([Disabling or taking out enemy ships](#topic-disable)).

#### Against Orions

They are fast, brittle and not here to die.

- They raid: in, one volley, and out. Don't race after them and burn your drives. Hold a central position and let them come.
- Against fast ships, use the fastest torpedo you have, a wider proximity and a fan.
- **Aim at the engines** of a runner and the chase is over.
- They frighten easily. Once a few of them are battered, **hail** the rest: a surrender demand with fair terms often ends the fight without another shot.
- Their point defense is the most trigger-happy of all.

#### Against the Borg

Learn first, then strike hard. See [Fighting the Borg](#topic-borg) for the whole method. In short:

1. Keep the range open while Seven surveys the ship (`duty harmonics`).
2. Tune your shields before the drones come (`tune shields`).
3. Hold your fire until you can mass it, and `remodulate` when they adapt.
4. When Seven finds the vinculum relay, destroy it (`target cube relay`), or send Worf across to do it ([Away teams and the shuttle](#topic-away-team)).
5. While she sleeps, hit her warp core and stand well clear, or board her: plant charges, or steal her shield harmonics.
6. Then bring the sword. Aimed fire through her open shields **wrecks** what it hits: one full salvo into her shields, the next into her drives (`target cube propulsion`). Every drive you wreck may set off her core.
7. Cloak, and finish her through the holes. She can't beam to, or lock on to, a ship she can't see.

#### Against bases and outposts

A base can't move, so it can't dodge.

- Use the heaviest warhead and the slow, hard-hitting probes.
- Fight from outside its phaser reach: a Klingon outpost carries eight banks.
- Strip its screen of escorts first, so it can't be relieved.

#### Leading a squadron

Allies follow standing orders until you change them:

- `tell <ally> attack <ship>` concentrates fire.
- `escort` and `defend` keep a guard on a damaged ship, or on you.
- `run` and `withdraw` save a ship before she is lost.
- Group allies (`tell excalibur join 1`) and order the group by its number.
- A crippled ally can be towed to a starbase with `tow`. Docked, she can't be hit and repairs twice as fast.

See [Ally orders](#topic-tell).

#### Missions

A mission changes what winning means ([Missions](#topic-missions)):

- **Rescue.** The hunter goes for the stricken ship first, so kill or draw her off, then close to 3,000 and lower only the shield that faces the wreck. Keep the armoured side to the enemy, or have a wingman screen you.
- **Escort.** Get between the hunters and the freighter early; once she is under fire it is already late. Disabling a hunter's drives works as well as killing her.
- **Intercept.** Don't chase her stern. Lay a course that meets her (Spock's "Cut her off" works one out), and leave her escorts for later unless they stand in the way. Disabling her engines ends it as surely as destroying her.

### More than one way to win

The best battles are often won in ways the enemy didn't expect:

- **Take her instead of destroying her.** Open a hole in her shields, aim at her life support, then board her (`capture <ship>`). On a tour she joins your squadron for good.
- **Talk her out of the fight.** A shaken captain will often yield. A frightened Orion pack may simply leave. Offering their own prisoners back makes a captain far readier to withdraw.
- **Bluff, carefully.** A claim of strength works only if her scans of you don't give you away.
- **Taunt to draw her in.** An enraged captain closes on you, which is exactly what a phaser-heavy ship wants.
- **Change ships.** If the Enterprise is crippled but the fight isn't over, `beam` to an ally within 3,000 units and fight on from there.
- **Use the starbase.** In a defense with waves, dock damaged ships between waves. A docked ship can't be hit.
- **Hold her still.** A tractor beam pins a ship for your torpedoes and your boarders.
- **Write the battle plan before the battle.** A named order runs a whole manoeuvre with one word, and `record` saves a move that worked.

For the moves that aren't written on any button, read [Hidden depths](#topic-hidden-depths).

See also: [Tactics](#topic-tactics), [Hidden depths](#topic-hidden-depths), [The powers of the galaxy](#topic-the-powers), [Coach](#topic-coach).

<a id="topic-hidden-depths"></a>

## Hidden depths

*Things the game lets you do that no button tells you about, each with the order that does it.*

Everything here works in the game today. None of it is on a button, and most of it changes how a battle goes once you know it.

### Power and shields

- **Lower the shields facing away.** Raised shields cost energy every cycle. If you can't pay for all of them, *none* of them hold that cycle. When power is tight, `lower 4 5 6` keeps the forward shields solid.
- **Charge, then disable.** A disabled bank keeps its charge but stops drawing power. Charge every bank, disable the ones that don't bear (`disable banks 3 4`), and enable them when they do.
- **Reinforce the shield you will keep toward her**, not the one that is already failing. Reinforcing costs four times the energy and halves the drain, so it buys the most on a shield that is still strong.
- **The boost buys time, not speed.** Geordi's team doesn't raise your top warp. It lets you hold it 40% longer. Call it as a long run starts, not when the gauges are already red. `boost`

### Phasers and torpedoes

- **Phasers are point defense too.** A wide spread (`fire all phasers 45`) sweeps a cloud of incoming torpedoes out of the sky. Reserve a bank or two for it with `role banks 5 6 defense`.
- **A fan only helps when it's wider than the fuse.** At 6,000 units a 2° fan changes nothing, because the proximity fuse already covers that much. 10° covers a sharp turn. Too wide a fan leaves gaps between the torpedoes.
- **Bait the trigger-happy.** Klingon and Orion crews fire several banks at a single torpedo. Fire one first and the salvo a cycle later, while their banks recharge. `bait`
- **Fire early at a charging ship.** Her own speed shrinks your arming distance. Wait too long and your torpedoes pass straight through her unarmed.
- **Torpedoes still work against a ship you can't see.** Fired at a cloaked ship, they fly to her last known position, and the bridge tells you how each one ended.
- **Scans show what she has ready.** A scan counts her charged banks and loaded tubes. A ship that has just fired everything is the ship to close on.
- **Lay a probe field.** Fire probes on a set course ahead of an enemy fleet (`fire probes 1 2 course 180`) and detonate them by code when the fleet arrives (`detonate all`).
- **Probes don't give up.** A homing probe outruns any ship slower than itself. Against a crippled ship or a base, it can't be escaped.

### Aimed fire and taking ships

- **Aimed damage lasts.** A system knocked out by aimed fire takes her crew three times as long to repair.
- **A destroyed shield generator is a permanent hole.** A shield you knock down comes back within cycles. A generator destroyed by `aim shields` doesn't, and your transporters can beam through the hole.
- **An empty ship falls at once.** Aim at her life support until her crew is gone. A derelict falls to your boarders without a fight.
- **Spare her engines if you mean to keep her.** Warp drives are the slowest system to repair, and a destroyed one has to be rebuilt from nothing.
- **The last ship gets 60 cycles.** When the last enemy is left helpless, the battle stays open for 60 cycles so you can board her.
- **A surrendered crew doesn't resist.** Board a ship that has struck her colours with six or more and you lose no one, and her crew become your prisoners.

### The mind

- **Taunting is a lure.** An enraged captain closes on you and won't listen. That is exactly what a phaser-heavy ship wants. `hail gorkon <your taunt>`
- **A bluff can be read.** A claim of strength fails if they have scanned you and seen your damage, and they won't like being lied to.
- **Klingons will withdraw, not surrender.** Offer a way out with honour.
- **Prisoners are currency.** On a tour, hand them to Starfleet in the Ready Room for torpedoes and probes, and every 40 earns another reinforcement call. Or offer them back over a hail: a captain is far readier to withdraw for his own people.
- **Mercy travels and so does treachery.** Spare a ship that surrendered and later captains yield more readily. Fire on one and later captains fight to the end and disbelieve your terms.
- **Rally the crew when it counts.** A speech (`address crew ...`) lifts morale by up to 12. At 100, repairs run 25% faster and tubes load 15% faster. The crew needs 60 cycles before another speech helps.

### Cloaks and plasma

- **Aim ahead of a vanishing ship.** A cloaked ship keeps moving. Burst the tachyon detector a little ahead of her last fix, along her last heading.
- **Turn before you pulse.** The deflector pulse only looks ahead, a 60° cone from your bow.
- **A damaged drive gives anyone away.** A badly damaged warp drive vents plasma at warp, cloak or no cloak. `sweep` follows trails much further than usual, and `seeker` flies a torpedo down one.
- **It works against you too.** If Geordi says you are venting plasma, repair the drives or drop below warp 1, or every enemy sensor can follow you.
- **Under the refit cloak, move after every shot.** The enemy sees only the flash where you fired.

### The Borg

- **Potshots teach them for free.** Mass every volley.
- **Through the opening, aimed fire wrecks.** Once her shields are open to you (stolen or cracked harmonics, or a dead facing), a salvo aimed at one system wrecks it, and the drones are slow to mend it. `target cube propulsion`
- **Wreck her shields first.** A destroyed generator is a hole that stays open after the stolen harmonics run out, so every later salvo through it is a strike too.
- **A wrecked drive can take her core with it**, even with her hull untouched. Stand clear after a salvo into her drives.
- **Strike, cloak, strike.** A cube can't beam drones to a ship she can't see, or lock her beams on it. Under the refit cloak, all she can shoot at is your flash.
- **Each new frequency is learned faster than the last**, and least of all when Seven picks it. Let her take the phaser watch (`duty phasers`).
- **Stolen harmonics work on every Borg ship**, not just the one you stole them from, until the hive notices.
- **The away team is safe only while you keep hurting the hive.** Stop firing, or cloak, and the drones may notice the little ship. Each crossing in one battle is riskier than the last.
- **Bring a drone home.** A drone rescued from a dormant ship lets the Doctor make every later scan of the Borg go further.
- **A sleeping ship's core is a bomb.** Destroy her warp drive or reactor while she is dormant and she goes up in a chain reaction. Stand well clear.
- **When she wakes, the relay moves.** You have to find it again, so make the dormant window count.
- **On a tour, the hive remembers you.** Most of what it learned about your weapons is still known at the next stop, so remodulate early.

### The bridge

- **Orders work while paused.** Pause, think, give every order, then resume.
- **Typing slows the battle**, to a quarter speed, until you press Enter.
- **`chart from <ship>`** measures ranges and bearings from an ally or an enemy, not just from you.
- **Evasive manoeuvres beat aimed torpedoes.** Enemy rounds are aimed where you would be if you held course, so any turn as they launch makes them miss. `evasive`
- **Change ships to fight on.** `beam <ally>` moves you and your command, and your officers come with you.
- **Veteran officers act for you.** Once trust reaches Veteran, an urgent proposal you leave unanswered, such as evasive manoeuvres or shields up, is carried out.
- **Record what worked.** `record last 3 as strike` turns your last three orders into a named order you can run again with one word.

See also: [The sword and the mind](#topic-sword-and-mind), [Coach](#topic-coach).

<a id="topic-campaigns"></a>

## Battles and campaigns

*Every way to play: quick battles, patrols, the curated battles, and tours of duty where nothing resets.*

There are several ways to go into battle, and each asks something different of you.

### Quick battle

**Quick battle** on the main menu puts you straight into a fight against a random enemy. **Quick battle side** sets the power you command. It is the place to learn a ship, or to try a tactic you have just read about.

### Patrols

**Patrol** (or **P**) makes up a fresh single battle each time, as one of five situations:

- **an ambush**: a group either side of the patrol lane
- **a wolf pack**: many fast, light ships spread out
- **a second wave**: more ships drop in once the first are beaten
- **an escort**: you have wingmen, and they brought more
- **a flagship**: a heavy behind a screen that makes you pay for going straight at her

The enemy is sized against your flagship, so it is a fair fight, not an easy one. The same patrol number always gives the same patrol, so you can replay one that beat you. See [Patrols](#topic-patrol).

### The curated battles

Each of these was set up to teach something:

- **Border Incident.** The Enterprise meets four Klingon battle cruisers probing the Neutral Zone. Begin's classic duel, grown to face a Dreadnought.
- **Romulan Ambush.** The Enterprise and a destroyer escort answer a distress call. Three Birds of Prey and a frigate wait under cloak. Watch for plasma.
- **Pirate Hunt.** Run down an Orion raiding party before it scatters. Orions are fast, brittle and unpredictable.
- **Dreadnought Duel.** Two Klingon dreadnoughts, two battle cruisers and a frigate against yours. Manage your shields and your power budget.
- **Outpost Assault.** Break a Klingon outpost's defensive screen. The outpost cannot move but carries eight phaser banks.
- **Fleet Action.** Seven ships against ten. Your wingmen fight on their own; use 'tell <ship> attack <target>' to direct them.
- **Three-Way Standoff.** Federation, Klingon and Romulan ships meet over a disputed system. Everyone is hostile to everyone.
- **Starbase Defense.** Hold the line at the starbase against three Klingon waves: frigates, then three battle cruisers, then two dreadnoughts with their escort. Between waves, damaged ships can dock to repair (2.0 rules).
- **First Contact: a Borg Probe.** A lone Borg probe is surveying the sector. Small, but it learns: watch its adaptation, remodulate, and let Seven scan it.
- **The Sphere.** A Borg sphere and its probe. Tune the shields before the drones come, find the vinculum relay, and put her to sleep.
- **Wolf at the Door: the Cube.** A cube, with a task force to stop it. Power alone will cost you dearly: survey her, send Worf across, and strike while she sleeps.

### Tours of duty

A tour strings battles into a campaign, and **nothing resets between them**:

- Every ship keeps her damage, casualties, empty torpedo racks and morale from one fight to the next.
- The ships you capture join your squadron.
- A ship you lose is gone.
- If the Enterprise falls, or the Borg take her, the tour is over.

Between stops you sit in the **Ready Room**. An officer briefs you on the next stop, including what the enemy has learned about how you fight. You make the stop's decision there, such as a refit that costs time, or whether to break a treaty. Geordi shows how each ship will arrive after her crew patches her up on the way. You can call Starfleet for reinforcements from the Ready Room or in battle, and they come when the distance allows, not when you need them.

Your reputation travels ahead of you:

- Spare those who surrender and later captains yield more readily.
- Fire on a ship that struck her colours and the rest fight to the end.
- Lean on aimed fire and boarding and they grow wary.
- Against the Borg, the hive remembers your weapons from one stop to the next.

After every stop your officers write up their stations, each captain in the squadron reports on her ship, and your own entry is drafted for you to keep or rewrite. A tour ends as the story of the patrol you actually flew.

- **Border Patrol** (The Archanis sector). Patrol the Klingon border, deal with whatever you find, and fall back to Starbase 12 when the Klingons move on it. Six stops, about an hour. *Stops:* Orion raiders → A Klingon on the border → Frigates at Kessik → Romulan ambush → The scouting dreadnought → Starbase Defense.
- **Neutral Zone Watch** (The Romulan Neutral Zone). Four stops along the Neutral Zone. The Romulans cloak, strike and vanish; Starbase 47 is the line they must not cross. About forty minutes. *Stops:* Silence at Outpost 4 → Frigate screen → The Bird of Prey → The line at Starbase 47.
- **The Orion Run** (The Orion trade routes). A short hunt for an Orion raiding band: three stops, about twenty minutes. A good first tour. *Stops:* Raid on a convoy → Saboteurs → The Armadillo.
- **The Collective** (Beyond the Federation's edge). Something is taking whole colonies along the frontier and leaving nothing behind. Find it, learn it, and stop it before it reaches the core worlds. Four stops, about forty-five minutes. *Stops:* The empty colony → The sphere at the rift → The graveyard → The cube.

See [Tours of duty](#topic-tour). You can write your own tours in `config/tours/`.

### Command styles

Before a battle, `style <name>` promises to fight a certain way:

- **from the chair**: no station handed over
- **by the book**: every order by its words
- **silent running**: no hails, never above warp 5
- **green crew**: no proposals
- **iron captain**: the hull kept above 75%

Win keeping the promise and the ribbon is yours. See [Command styles and trust](#topic-styles).

See also: [Patrols](#topic-patrol), [Tours of duty](#topic-tour), [After the battle](#topic-after-battle), [Command styles and trust](#topic-styles).

# Part Two: The ship's manual

## Getting started

<a id="topic-index"></a>

### Welcome aboard

*How to use this manual, and where to start.*

This manual covers every command, how each weapon works, and how to win. Open it at any time with **H**, or by typing `help` or `man` in the console. To go straight to one command, type `help <command>`. Short forms work here too, so `help tor` opens the torpedo page.

> **Coach** The [Coach](#topic-coach) page reads the battle you are in and tells you what to do next: whether your target is inside your torpedo envelope, which torpedo and proximity setting suit it, and which shield to turn toward the enemy.

#### Start here

- [The captain's manual](#topic-welcome-aboard): the powers, your crew, how a battle works, and how to win, in nine chapters.

- [Your first battle](#topic-first-battle): a five-minute walkthrough.
- [Keyboard and mouse](#topic-controls): every key.
- [The command console](#topic-console): how commands are typed, shortened and combined.
- [Fire](#topic-fire): everything you can shoot, and how.
- [Choosing weapons](#topic-weapons-guide): torpedo and probe types compared, with live numbers.

#### What the remake adds

Begin's commands all work as written. On top of them:

- [Bridge officers](#topic-crew) who run stations for you, [take the whole bridge](#topic-conn), and [talk back](#topic-talking), with traits and a response style you can change.
- [The bridge](#topic-bridge): officers who read your orders back, a command wheel on every ship, proposals you accept with **Y**, and [orders you speak aloud](#topic-voice-orders).
- [Alert conditions](#topic-alert), [command styles and your officers' trust](#topic-styles).
- [Named tactical orders](#topic-orders): a battle plan written before the fight or recorded during it, run with one word.
- [Patrols](#topic-patrol) and [tours of duty](#topic-tour): a fresh mission each time, or battles linked into a campaign.
- [Hailing enemy captains](#topic-hailing), who can be talked into surrendering or leaving.
- [Missions](#topic-missions) with a goal beyond holding the field: rescue a stricken ship's people, get a convoy through, stop a runner.
- [Counsel from the bridge](#topic-counsel): press **O** and each officer lays out a plan from the live fight, or toward a goal you name.
- [Sharp drawing on Retina and 4K screens](#topic-display), with weapon light on the hulls.
- [Orders in plain English](#topic-plain-english) with a language model; exact commands and short forms like `tor al` always run at once.
- [Language models](#topic-llm), including an optional second model for character voices: richer Klingon, Romulan and other alien speech.
- [Hull repairs](#topic-repair) and an engineer who can direct the crews, [crew morale](#topic-morale) and `address crew`, and [evasive manoeuvres](#topic-helm).
- [Sound](#topic-sound) with a choice of phaser and torpedo sounds, or your own WAV files.
- [Starfleet's assessment](#topic-after-battle): the mission, lives, conduct and cost, a commendation when one is earned, and a line from each officer.
- The [Coach](#topic-coach), which also runs a training session from the main menu before your first battle.

#### Using this manual

- Type anywhere in this window to search. Press **Enter** to open the best match.
- Click a link to follow it, and press **Backspace** or **‹ Back** to return.
- Lines marked **›** are example commands. Click one to put it in the console, ready to edit and send.

```text
help fire
man tor
coach
```

#### Editing the manual

Every page is a Markdown file. You can change the wording, add tips, or write new pages without touching the code. The path of the page you are reading is shown in the bottom-right corner of this window.

- The bundled pages live in `src/begin/assets/help/`.
- To keep your own versions separate, put `.md` files in the project's `config/help/` folder (or in the folder named by `BEGIN_HELP_DIR`). A file there replaces the bundled page with the same name, and new files become new pages.
- Pages reload automatically when the files change.

The page format is described in [Writing help pages](#topic-writing-help).

<a id="topic-controls"></a>

### Keyboard and mouse

*Every key and mouse action in battle.*

#### Time

| Key | Action |
|---|---|
| **Space** | Pause or resume. Orders still work while paused. |
| **[** and **]** | Slower or faster: 0.25×, 0.5×, 1×, 2×, 4×. One cycle is one second at 1×. |

#### Helm

| Key or mouse | Action |
|---|---|
| **W** / **S** | Warp up or down by one |
| **A** / **D** | Turn 15° to port or starboard (hold **Shift** for 5°) |
| Right-click the map | Steer toward that point |
| **Shift** + right-click a ship | Pursue it |

#### Weapons and targeting

| Key or mouse | Action |
|---|---|
| Left-click a ship, or **Tab** | Select a target (**Shift+Tab** goes backwards) |
| **R** | Aim at a subsystem: propulsion, weapons, shields, power, sensors |
| **F** | Fire phasers |
| **T** | Fire torpedoes |
| **P** | Launch a probe at the target |
| **X** | Scan the target |
| **V** | Cycle the point-defense doctrine |
| **G** | Raise or lower all shields |

#### Bridge

| Key or mouse | Action |
|---|---|
| Right-click a ship, or **E** for your target | Open the command wheel. See [The bridge](#topic-bridge). |
| **1**–**8** with the wheel open | Pick a slice |
| **Y** / **N** | Make an officer's proposal so, or belay it |
| **Ctrl+Y** while typing | Accept the urgent proposal shown above the console |
| **O** | Open or close the counsel: each officer's plan from here. See [Counsel from the bridge](#topic-counsel). |
| **1**–**4** with the counsel open | Go all in on that officer's plan |
| **Tab** while typing | Finish a command, ship, officer or order name |
| Hold **Right Alt** (Option on a Mac) | Speak an order; let go to send it. See [Speaking orders](#topic-voice-orders). |

#### View

| Key or mouse | Action |
|---|---|
| Mouse wheel, **+** / **−** | Zoom (or type `range 8000`) |
| Drag, arrow keys | Pan the map |
| **C** | Centre on your ship and follow it |
| **Q** | Show phaser arcs |
| **I** | Damage view |
| **M** | Sound on or off. See [Sound](#topic-sound). |
| Mouse wheel over the log | Scroll the console log |

#### Console and help

| Key | Action |
|---|---|
| **Enter** or **/** | Open the command console. See [The command console](#topic-console). |
| **↑** / **↓** in the console | Previous and next commands |
| **H** | Open this manual |
| **F1** | Open this page |
| **F2–F8, F10–F12**, **Ctrl+letter** | Run a key macro. See [Key macros](#topic-keys). |
| **Esc** | Close the counsel, the open window or text display, or open the battle menu |

#### How much the panels show

The panels show what matters at a glance: warp, course, crew, hull, morale, and shield arcs coloured by strength. Hover over the Own ship panel and it shows every number: shield strengths, maximum warp, power in and out, the magazine. Numbers ease to their new value instead of jumping, and flash briefly when they change: brighter for a rise, warmer for a fall.

| Command | What it does |
|---|---|
| `hud detail` | always show every number |
| `hud simple` | back to the essentials (hover a panel for the rest) |
| `hud` | say which it is |

See also: [The command console](#topic-console), [Key macros](#topic-keys).

<a id="topic-console"></a>

### The command console

*How commands are typed, shortened and combined.*

Press **Enter** to open the console, type an order and press **Enter** again. Commands follow Begin's own wording, so a Begin captain can type what they always typed.

```text
helm 90 warp 4
fire all phasers spread 10
lock all tubes on gorkon
tell agena attack gorkon
```

#### Shortening words

Any word can be cut to a unique prefix, as in Begin. When a prefix fits several commands, the rest of the line settles it: `pu tal` pursues the Talon (a pulse takes no ship), while `pu` alone fires the deflector pulse. A prefix that still fits more than one is answered with the choices. These all fire every torpedo tube:

```text
fire all torpedoes
fir tor al
torp all
ft
```

If a prefix matches more than one command, the console says which ones it could mean (`lo` could be `lock`, `load` or `lower`).

#### Lists of mounts

Phaser banks, torpedo tubes, probe launchers and shields are numbered from 1. All of these forms work:

| You type | Means |
|---|---|
| `all`, `al` (or nothing) | every mount |
| `1 2 3`, `1,2,3`, `1 2 and 3` | those mounts |
| `1-3` | a range |

```text
fir tor 1,2,3
lock banks 1 2 and 3 on gorkon
lower shields 4-6
```

#### Ships and filler words

- Name a ship by any unique start of its name: `pursue gor`. An unidentified contact is `#` followed by its number, as shown on the map: `target #7`.
- Words like *the*, *to*, *at*, *on*, *with* and *of* are ignored, so `tell the agena to attack the gorkon` works.

#### Several commands at once

Separate commands with `;` to send them together. This is also how [key macros](#topic-keys) work.

```text
lock all banks on gorkon; fire all phasers spread 10
```

#### Results

- Orders are acknowledged in the log under the map, and rejected orders say why.
- Status commands such as `banks`, `tubes` or `chart` print a table. The latest table stays on the map and keeps updating until you press **Esc**. See [Status displays](#topic-status).

See also: [Fire](#topic-fire), [Keyboard and mouse](#topic-controls), [Key macros](#topic-keys), [Orders in plain English](#topic-plain-english).

<a id="topic-first-battle"></a>

### Your first battle

*A five-minute walkthrough of a one-on-one fight.*

Start a **Quick battle** from the menu. The battle begins paused, so take your time.

1. **Find the enemy.** Enemy ships are red on the map. Press **Tab** to target the nearest one. The Target panel shows its class, range and what you know about it.
2. **Get moving.** Press **W** a few times for warp 3 or 4, then right-click toward the enemy, or type `pursue <name>`.
3. **Start the clock.** Press **Space**. One cycle passes per second at 1×. Use **[** and **]** to change speed.
4. **Torpedoes first.** Torpedoes reach much farther than phasers, but they need room to arm. When the [Coach](#topic-coach) says the shot is on, press **T**.
5. **Close for phasers.** Inside phaser range, press **F**. Hits are far stronger up close. See [Phasers](#topic-phasers).
6. **Mind your shields.** Each of your six shields covers one 60° sector. When the one facing the enemy weakens, turn to bring a fresh one around. See [Shields](#topic-shields).
7. **Watch your engines.** Running above cruise warp heats the drives. Past the limit they take damage.

> **Training** Before your first battle, choose **Coach & training** on the main menu (or press **C**) for the same steps with the commands to type.

> **Tip** The panels keep to the essentials. Hover the mouse over the Own Ship panel for every number, or type `hud detail` to keep them all showing. See [Keyboard and mouse](#topic-controls).

> **Tip** Press **H** at any time and choose **Coach**. It reads the battle and suggests your next move, with the exact command to type.

```text
target gor
pursue gor warp 4
fire all torpedoes
fire all phasers spread 10
coach
```

See also: [Coach](#topic-coach), [Fire](#topic-fire), [Shields](#topic-shields).

<a id="topic-plain-english"></a>

### Orders in plain English

*With a language model set up, type orders in your own words and the console works out the commands.*

When a language model is set up (see [Officers and language models](#topic-llm)), you don't have to remember the console's wording. Type what you mean and the console works it out:

```text
turn hard right and go to warp 6
get the shields up and hit the klingon's engines
what's the best way to deal with a cloaked ship?
```

Each command the model chooses is shown in the log with a **≈** in front, then carried out exactly as if you had typed it, so you pick up the real syntax as you play:

```text
> get the shields up and hit the klingon's engines
  … interpreting
≈ raise all
≈ target gorkon propulsion
≈ fire all phasers
```

If what you said could mean more than one thing that matters, such as which of two enemy ships, the console asks instead of guessing. Just answer: "the closer one" or "gorkon" is enough, because it remembers what you were talking about. A question about the game gets a short answer, often with the command to use.

#### How it decides

The exact console always gets the first look, so anything typed in console syntax runs at once, with no wait. Only a line the console doesn't recognise goes to the model. Every command the model proposes is checked by the console before anything runs; if one is wrong, the model gets one try to fix it, and otherwise you see what went wrong and nothing runs.

The model never ends the battle, self-destructs, surrenders or changes ships on its own reading of your words. If it thinks you meant one of those, it shows the command and leaves you to type it.

Talking to an officer ("spock, ...") still goes to that officer, as before. The model can also pass a question on to an officer for you.

The exact console always wins, even while the computer is waiting for your answer to a question: a command it recognises, abbreviations included (`tor al`, `pha al`), runs at once and the question is dropped. Only a lone word or number, like `2` or `gorkon`, is taken as your answer.

The battle doesn't wait while the model thinks: a local model may take a few seconds, so pause first if you need time. While it works, the officers say their remarks as written rather than queueing at the model ahead of you. If it hasn't answered in 20 seconds the console gives up, says so, and runs nothing; type the command yourself, or check the model is running.

#### Switching it

| Command | Effect |
|---|---|
| `translate on` | the default: only lines the console doesn't recognise go to the model |
| `translate always` | every line goes to the model first, even exact commands (slower) |
| `translate off` | the console only accepts its own syntax |
| `translate` | says which of these is set |

Your choice is saved in `config/settings.json` (`"console"` in the `llm` section) when the battle ends. You can also set it from a terminal: `begin --llm console=always`.

#### What the model sees

Your words, the full console command list, and the same factual summary of the battle the officers get: your ship, your weapons and shields, the contacts on your sensors with their names, range and bearing, your allies and your officers. Never anything your side could not know.

See also: [The command console](#topic-console), [Officers and language models](#topic-llm), [Talking to your officers](#topic-talking).

<a id="topic-bridge"></a>

### The bridge

*Giving orders the way a captain does: officers read them back, a wheel on every ship, proposals you accept with Y.*

Every way of giving an order still works: keys, clicks, the console. The bridge adds to them.

#### Readbacks and subtitles

Every order you give through the console (and the wheel, a proposal or your voice, which all go through it) is read back by the officer at that station, in a sentence built from the order itself: *"Course 090, warp 6."*, *"Firing all phasers at the Hydra, aiming for her shields."* If what you hear back isn't what you meant, say it again.

Officers' words show low on the map, one voice at a time, with their station's mark: helm a chevron, tactical a diamond, engineering a hexagon, science a ring. The log keeps every word in two columns: **Bridge** (who said what) and **Computer** (everything else).

#### The command wheel

Right-click a ship (or press `E` for your target) and pick an order. Eight slices, always in the same places for an enemy: Phasers, Torpedoes, Disable, Close to, Hail, Board, Elude, Target. Rest on a slice with a `›` for its second ring. Keys `1`-`8` pick a slice too. Your own ships and your own ship have wheels of their own.

Every slice is a console line, and the log shows it, so the wheel teaches the console. Right-clicking empty space still steers; Shift+right-click still pursues. Make the wheel your own in `config/wheel.toml` (copy it from the game's `content/data/wheel.toml`).

#### While you type

The battle eases to a quarter speed while you type an order (**tactical focus**: an amber edge, the sound steps back), and runs again as soon as you press Enter, or after eight seconds without a key. Under the console, a faint line says what Enter would do, and the map shows a ghost of it: the course, the ship. `Tab` finishes the word you're typing: a command, a ship, an officer, a named order.

Point and say: with the mouse on a ship, "fire at **her**", "pursue **him**" or "scan **that one**" mean that ship. The log shows the line with her name in it.

#### Proposals

Now and then an officer at a station you're running proposes an order: *"Torpedoes inbound, Captain. Evasive manoeuvres?"* `Y` makes it so, `N` belays it, or let it lapse. While you type, only an urgent one shows, as a chip above the console: `Ctrl+Y`. They're rare: one at a time, an officer at most once a minute.

#### The Bridge setting

| Command | What it does |
|---|---|
| `hud bridge full` | everything above (the default) |
| `hud bridge quiet` | readbacks in the log only, subtitles only when urgent, no focus, no proposals |
| `hud bridge classic` | the console as it was: "acknowledged", nothing more |
| `hud wheel on\|off` · `hud focus slow\|pause\|off` · `hud proposals often\|rarely\|off` | one part at a time |
| `hud subtitles all\|urgent\|off` · `hud readbacks voiced\|log\|off` · `hud orders on\|off` · `hud preview on\|off` | |

The setting is kept in `config/settings.json`.

See also: [The command console](#topic-console), [Named tactical orders](#topic-orders), [Alert conditions](#topic-alert), [Command styles and trust](#topic-styles), [Speaking orders](#topic-voice-orders), [Bridge officers](#topic-crew).

<a id="topic-voice-orders"></a>

### Speaking orders

*Hold Right Alt (Option), say the order, let go. Mac speech, Whisper on this computer, a Whisper server or the cloud.*

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

See also: [The bridge](#topic-bridge), [The command console](#topic-console), [Orders in plain English](#topic-plain-english), [Officers and language models](#topic-llm).

## Coach

<a id="topic-coach"></a>

### Coach

*Reads the battle you are in and suggests what to do next, with the command for each step.*

The coach looks at the same information your sensors give you: your target's range, course and speed, your weapons and what they are loaded with, incoming fire, your shields, heat and power. It never peeks at anything your side could not know. Advice is listed most urgent first, and this page refreshes while it is open, so you can leave it up and watch the advice change as the fight moves.

Click a **›** line to put that command in the console. Nothing is sent until you press Enter.

> **Coach** You're not in a battle yet, so here is the training run. Once a battle starts, this space reads your fight instead: your target's range against your weapons' envelopes, the best torpedo and proximity setting, your shields, heat and power, with the command for each step.

##### Before you start
Every battle begins **paused**. Nothing moves until you press **Space**, so read the board first. **Enter** opens the console, **H** this manual and **F1** the controls. See [Your first battle](#topic-first-battle) for the full walkthrough.

##### 1. Find and target the enemy
Enemy ships are red. **Tab** targets the nearest, and the Target panel shows its class and range. In the console, the first few letters of a ship's name are enough (here, a Klingon called Gorkon):
```text
target gor
```

##### 2. Close the range
**W** and **S** change warp, and a right-click on the map sets your course. Or let the helm chase them:
```text
pursue gor warp 4
```

##### 3. Torpedoes at long range
Torpedoes reach far beyond phasers but need room to arm. When the coach says the shot is on, press **T**.
```text
fire all torpedoes
```

##### 4. Phasers up close
Inside phaser range press **F**. Phasers hit far harder the closer you are. See [Phasers](#topic-phasers).
```text
fire all phasers
```

##### 5. Keep a strong shield toward them
Six shields each cover 60°. When the one facing the enemy weakens, turn to bring a fresh one round. See [Shields](#topic-shields).

##### 6. Mind the engines and the power
Above cruise warp the drives heat up, and past the limit they take damage. For a long run, ask Geordi for all she's got and a team keeps them cooler for a while (see [Engine boost](#topic-boost)). Firing and shields drain the batteries.

##### 7. Dodge, and fan your shots
A Federation helm can jink out of the way of incoming torpedoes and then carry on with your course. Against a fast target, fan the salvo so a turn doesn't take it clear of every round. See [Course and speed](#topic-helm) and [Torpedoes](#topic-torpedoes).
```text
evasive
fire all torpedoes spread 10
```

##### 8. Let the crew help
Hand a station to its officer, or the whole bridge. Geordi La Forge can run the repairs, and a word from you lifts a shaken crew. See [Bridge officers](#topic-crew), [Repair](#topic-repair) and [Crew morale](#topic-morale).
```text
delegate tactical
geordi, manage repairs
address crew Steady. We have the better ship.
```

##### 9. Plan ahead
Write a named order before the fight in `config/orders.toml` and run it with one word. See [Named tactical orders](#topic-orders).
```text
orders
execute order beta-1
```

##### In the battle
Type `coach` or press **H** and pick **Coach**: this page then reads your actual fight and lists the most urgent thing first. Your officers help too. Try `spock, what do you advise?` (see [Talking to your officers](#topic-talking)).

#### Your weapons

> **Note** Start a battle to see the weapons of the ship you command.

#### How the coach thinks

- **Incoming fire comes first.** A torpedo or probe heading your way is the most urgent thing on the board, so point defense and shield facing are checked before anything else.
- **Every weapon has an envelope.** A torpedo is only useful between its *arming* range and its *maximum* range against the target's current motion, and both change as the target turns. The coach tells you whether your target is inside it, and how far to close or open the range.
- **The right warhead for the job.** Fast torpedoes suit fast or manoeuvring targets. Heavy warheads suit slow ships and bases. Shield-bore warheads ignore part of the shield, and plasma fades the further it travels. See [Choosing weapons](#topic-weapons-guide).
- **Proximity is a trade.** A wide proximity setting is more likely to explode near the target but does less damage. Tight settings hit hard but need good aim. Against a ship that is turning, open the proximity up.
- **Heat and power.** Running hot at high warp, or with too little power left for shields, gets flagged with the warp that fixes it.

Type `coach` in the console at any time to open this page. Before a battle, **Coach & training** on the main menu (or **C**) opens it with the training run; **Manual** (or **H**) opens the whole manual.

See also: [Choosing weapons](#topic-weapons-guide), [Tactics](#topic-tactics), [Torpedoes](#topic-torpedoes), [Shields](#topic-shields).

<a id="topic-weapons-guide"></a>

### Choosing weapons

*Torpedo and probe types compared, with live numbers from the game data, and how to pick between them.*

Each nation fields its own torpedoes and probes. They differ in four ways that matter in a fight: **speed** (how long the target has to dodge), **warhead** (how hard it hits), **range** (how long it flies before it fizzles), and **arming distance** (how far it must travel before it can explode). The tables below come straight from the game data, so they are always current.

#### Torpedoes

| Torpedo | Id | Warp | Warhead | Arms at | Reach | Max prox | Guidance | Reload | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Romulan Plasma Torpedo | `plasma` | 15 | 30 plasma (fades with distance) | 1,500 | 19,500 | 750 | homing | 6 c | Romulan Bird of Prey, Romulan War Eagle |
| Federation Mark 8 | `mk8` | 15 | 21.6 antimatter | 1,425 | 10,425 | 800 | straight | 4 c | - |
| Plasma X Torpedo | `xplasma` | 21 | 18 plasma (fades with distance) | 2,100 | 25,200 | 500 | homing | 5 c | Romulan Frigate |
| Borg torpedo | `bgt` | 24 | 18 antimatter | 1,440 | 18,240 | 600 | straight | 4 c | Borg Cube, Borg Probe, Borg Sphere |
| Federation Mark 7 | `mk7` | 30 | 14.4 antimatter | 1,200 | 19,200 | 800 | straight | 3 c | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon TX torpedo | `ktx` | 27 | 10 antimatter | 2,700 | 18,900 | 500 | straight | 3 c | Klingon Battle Cruiser, Klingon Dreadnought, Klingon Escort, Klingon Frigate |
| Orion Bullet Torpedo | `opbt` | 20 | 8 antimatter | 2,000 | 12,000 | 400 | straight | 3 c | Orion Anarchist, Orion Armadillo, Orion Saboteur |
| Orion Shield Auger | `oshb` | 20 | 8 shield-bore | 2,000 | 12,000 | 400 | straight | 5 c | - |

##### How to choose

- **Long range, slow target:** a heavy warhead. A base or a crippled cruiser cannot dodge, so put everything you have into the hit.
- **Fast or turning target:** the fastest torpedo you have, with a wider proximity. The less time it is in flight, the less the target can move.
- **Strong shields:** a shield-bore warhead. It loses less to the shield it strikes.
- **Close range:** watch the arming distance. A torpedo fired inside it flies straight through its target.
- **Plasma** steers toward its target, but its warhead weakens as it flies. Fire it from close in.

Change what a tube holds with `load` or `autoload`. See [Loading and autoload](#topic-loading).

```text
autoload tor all photon 300
load all tubes 250
```

#### Probes

| Probe | Id | Warp | Warhead | Arms after | Time fuse | Reach | Max prox | Sensor | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Dreadnought Killer (dink) | `dnk` | 3.5 | 30 | 5 c | 12 c | 4,200 | 1,500 | 0 | Klingon Dreadnought, Klingon Frigate |
| Romulan Pak Probe | `rmpp` | 2 | 28 | 6 c | 20 c | 4,000 | 1,000 | 0 | Romulan Bird of Prey, Romulan Frigate |
| Federation Probe X-2 | `px2` | 2.5 | 25 | 5 c | 20 c | 5,000 | 1,200 | 0 | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon Light Pak Probe | `klpp` | 2 | 20 | 6 c | 20 c | 4,000 | 1,000 | 0 | Klingon Battle Cruiser, Klingon Escort, Orion Anarchist, Orion Armadillo |
| Klingon Data Probe | `kdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Romulan version of Klingon Data Probe | `rdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Federation Probe Data-2 | `pxd2` | 20.5 | 0 | 1 c | 30 c | 61,500 | 1,200 | 20,000 | - |

##### How to choose

- Probes are slower than torpedoes, so they are best against targets that cannot outrun them: bases, damaged ships and big cruisers.
- Most probes home in on a ship. Others fly a set course and are good for laying a field ahead of a fleet, then setting off by code with `detonate`.
- A probe's timer decides how long it waits before it can be set off. Set it with `load launchers <list> <prox> time <t>`.

#### Phasers

Phasers hit instantly, but they lose power with distance and with spread.

Damage per bank for a Dreadnought (charge 10, range 2,000) before shields:

| Range | Spread 10 | Spread 20 | Spread 45 |
|---|---|---|---|
| 0 | 22 | 11 | 5 |
| 500 | 19 | 10 | 4 |
| 1,000 | 16 | 8 | 4 |
| 1,500 | 11 | 6 | 2 |
| 1,800 | 7 | 4 | 2 |

Fire at a narrow spread against one ship and a wide one against several objects, such as a cloud of incoming torpedoes. See [Phasers](#topic-phasers).

#### Ship classes

| Ship | Nation | Max warp | Phasers (range) | Tubes | Probes | Shields | Crew |
|---|---|---|---|---|---|---|---|
| Probe (`PR`) | Borg | 9 | 3 (2,400) | 2 × bgt | 0 × - | 6 × 150 | 260 |
| Sphere (`SP`) | Borg | 9 | 6 (2,600) | 4 × bgt | 0 × - | 6 × 240 | 1400 |
| Cube (`CU`) | Borg | 7 | 12 (2,900) | 6 × bgt | 0 × - | 6 × 420 | 9000 |
| Shuttlecraft (`SH`) | Federation | 5 | 0 (0) | 0 × mk7 | 0 × px2 | 6 × 25 | 8 |
| Tug (`TG`) | Federation | 4 | 0 (2,000) | 0 × - | 0 × - | 0 × 50 | 25 |
| Interceptor (`IN`) | Federation | 12 | 6 (2,000) | 1 × mk7 | 1 × px2 | 6 × 150 | 105 |
| Destroyer (`DE`) | Federation | 10 | 4 (2,000) | 4 × mk7 | 2 × px2 | 6 × 200 | 200 |
| Heavy Cruiser (`HC`) | Federation | 9 | 4 (2,000) | 6 × mk7 | 3 × px2 | 6 × 225 | 450 |
| Dreadnought (`DN`) | Federation | 9.5 | 6 (2,000) | 8 × mk7 | 4 × px2 | 6 × 250 | 500 |
| Dreadnought (cloak refit) (`DN`) | Federation | 9.5 | 6 (2,000) | 8 × mk7 | 4 × px2 | 6 × 250 | 500 |
| Tanker (`TN`) | Federation | 4 | 0 (2,000) | 0 × - | 0 × - | 6 × 50 | 20 |
| Starbase (`SB`) | Federation | 0 | 8 (2,000) | 0 × - | 0 × - | 6 × 950 | 12000 |
| Escort (`ES`) | Klingon | 11 | 4 (2,200) | 1 × ktx | 1 × klpp | 6 × 100 | 95 |
| Frigate (`FR`) | Klingon | 10.5 | 5 (2,200) | 2 × ktx | 2 × dnk | 6 × 175 | 175 |
| Battle Cruiser (`BC`) | Klingon | 10 | 5 (2,200) | 5 × ktx | 2 × klpp | 6 × 200 | 350 |
| Dreadnought (`DR`) | Klingon | 9 | 6 (2,200) | 8 × ktx | 4 × dnk | 6 × 225 | 500 |
| Outpost (`OP`) | Klingon | 0 | 8 (2,200) | 0 × - | 0 × - | 6 × 925 | 6000 |
| Assassin (`AS`) | Orion | 14 | 3 (1,800) | 0 × - | 0 × - | 6 × 100 | 45 |
| Raider (`RA`) | Orion | 12 | 5 (1,800) | 0 × - | 0 × - | 6 × 125 | 95 |
| Saboteur (`SA`) | Orion | 10 | 5 (2,000) | 1 × opbt | 0 × - | 6 × 175 | 110 |
| Anarchist (`AN`) | Orion | 10 | 5 (2,000) | 3 × opbt | 1 × klpp | 6 × 180 | 145 |
| Armadillo (`AR`) | Orion | 8 | 2 (2,000) | 2 × opbt | 1 × klpp | 0 × 180 | 45 |
| War Eagle (`WE`) | Romulan | 3.5 | 5 (2,500) | 1 × plasma | 0 × - | 6 × 400 | 115 |
| Frigate (`FR`) | Romulan | 8.25 | 4 (2,200) | 2 × xplasma | 2 × rmpp | 6 × 300 | 160 |
| Bird of Prey (`BP`) | Romulan | 6 | 3 (2,500) | 2 × plasma | 2 × rmpp | 6 × 325 | 275 |

See also: [Torpedoes](#topic-torpedoes), [Probes](#topic-probes), [Phasers](#topic-phasers), [Loading and autoload](#topic-loading), [Coach](#topic-coach).

<a id="topic-tactics"></a>

### Tactics

*General advice for winning fights, from range control to shield management.*

These are the basics in brief. The full guide is [The sword and the mind](#topic-sword-and-mind), with a playbook for every enemy, and [Hidden depths](#topic-hidden-depths) lists the moves no button tells you about.

#### Control the range

The side that chooses the range usually wins. Ships armed mainly with torpedoes want to stand off just inside their torpedo envelope, where enemy phasers cannot reach them. Ships with strong phasers want to close fast and stay close. Use `pursue <ship> warp <w>` to hold a chase, and `elude <ship>` to keep away. The [Coach](#topic-coach) tells you which side of each envelope you are on.

#### Turn your strongest shield toward the enemy

Your ship has six shields, each covering 60°. Damage to one shield does not touch the others, so when the forward shield is weak, turn so a fresh one faces the threat. A shield can be **reinforced** to lose strength more slowly, at four times the energy cost. See [Shields](#topic-shields).

#### Don't run hot

High warp heats your drives. A drive that climbs past its temperature limit burns out for good, and only a starbase can rebuild it. Fight at the warp you need, not the warp you have.

#### Mix your weapons

Fire torpedoes from range, then finish with phasers when the target's shields are down. Keep a phaser bank or two on **defense** so that point defense can shoot down incoming torpedoes. See [Fire control and point defense](#topic-firecontrol).

#### Aim at what matters

A ship with no weapons cannot hurt you, and a ship with no engines cannot run. Use `target <ship> weapons` or `target <ship> propulsion` to aim at a subsystem. See [Targeting](#topic-targeting).

#### Use your allies

Allies follow standing orders. `tell <ally> attack <ship>` concentrates fire, `tell <ally> escort <you>` keeps a guard close, and `tell <ally> run` saves a damaged ship. See [Ally orders](#topic-tell).

#### Know when to leave

A ship that stays more than 60,000 units from every enemy for ten cycles escapes the battle. A ship that escapes is not lost.

See also: [Coach](#topic-coach), [Choosing weapons](#topic-weapons-guide), [Shields](#topic-shields), [Course and speed](#topic-helm).

## Helm

<a id="topic-helm"></a>

### Course and speed

*Set your course in degrees and your speed in warp.*

The helm takes a **course** and a **warp**. Courses are compass bearings in degrees: 0 is straight up the map, 90 is to the right, 180 is down and 270 is to the left. Negative courses count the other way, so `-90` is the same as `270`.

```text
helm 90 warp 4
helm 45
warp 6
90 4
stop
```

- `helm <course>` turns without changing speed, and `warp <w>` changes speed without turning.
- Two bare numbers are read as course and warp, so `90 4` is short for `helm 90 warp 4`.
- `stop` (or `allstop`) brings the ship to a halt.
- The ship turns at its own rate, so a big course change takes a few seconds. Heavy ships turn slowly.

#### How fast can you go?

Every warp factor is 100 units of distance per cycle. Your top speed is limited by your class, by damage to your drives and by the power you have left over for shields and weapons. If you ask for more than you can reach, the helm tells you and uses the most it can.

Warp heats your drives. A drive that overheats burns out, so watch the temperature gauges on the engineering panel when you run at high warp. The [Coach](#topic-coach) warns you before that happens. When you need to run hard for a while, ask Geordi for all she's got: a team keeps the drives cooler for 30 cycles, at the cost of slower repairs. See [Engine boost](#topic-boost).

#### Evasive manoeuvres

Federation helms are drilled in evasive manoeuvres. Give the order and the helm keeps your course and warp but turns away from each torpedo that would hit. It is aimed where you would be if you held course, so turning as it is launched makes it miss. Once the torpedoes are clear, the helm comes back to your heading.

```text
evasive
evade
sulu, evasive manoeuvres
evasive off
```

While the order stands, a banner across the top of the map says so (amber while the helm is dodging), the **Course** line in the Own ship panel says "evasive", and the helm's dodge is drawn on the map like an officer's. Any navigation order you give yourself, such as `helm`, `warp`, `stop`, `pursue`, `elude` or `dock`, ends it. Klingon, Romulan and Orion crews don't have the drill. An officer flying the ship (see [Giving an officer the bridge](#topic-conn)) dodges torpedoes anyway.

#### Mouse and keys

- Right-click the map to steer toward a point.
- **W** and **S** change warp by one. **A** and **D** turn 15° (5° with **Shift**).

Starbases and other bases cannot move.

See also: [Pursue and elude](#topic-pursue), [Tactics](#topic-tactics), [Keyboard and mouse](#topic-controls).

<a id="topic-pursue"></a>

### Pursue and elude

*Let the helm chase a ship, keep away from it, or hold it at a range you choose.*

`pursue` hands steering to the helm computer, which keeps turning to intercept a ship. `elude` does the opposite: it keeps turning away from one.

```text
pursue gorkon warp 6
pursue gorkon
chase #3 8
elude gorkon warp 7
elude gorkon at 9000
pursue gorkon warp 6 at 4000
```

- The warp is optional. Without it, the ship keeps its current speed.
- The pursuit lasts until you give another helm order, such as `helm 90` or `stop`.
- You can name the ship, use its number from the [Chart](#topic-chart) with a `#` in front (`#3`), or type a unique part of its name.
- **Shift** + right-click a ship on the map also starts a pursuit.
- Add `at` and a range to hold her there instead: the helm closes when she is beyond it, opens the range when she is inside it, and circles her in between. `elude gorkon at 9000` keeps a heavy cruiser at torpedo range, outside her phasers, without running off the map. A bare number above 100 means a range too (`elude gorkon 9000`). The map line reads "holding at 9,000".

#### When to use which

Pursue a ship you want to keep inside your weapon range, especially one that is trying to run. Elude a ship that outguns you at close range, or a stream of incoming probes. Plain `elude` keeps running for as long as the order stands, and a ship far enough from every enemy has left the battle: when you mean to fight her at your range, not leave, give the range (`elude gorkon at 9000`). The officers' [Counsel from the bridge](#topic-counsel) does.

A runner on a set heading is better met than chased: a `helm` course that leads her, at your best warp, closes the distance a stern chase never will. Spock works one out in the counsel when there is a runner to stop (see [Missions](#topic-missions)). The [Coach](#topic-coach) says when the range is wrong for your weapons.

See also: [Course and speed](#topic-helm), [Tactics](#topic-tactics), [Ally orders](#topic-tell).

## Weapons

<a id="topic-fire"></a>

### Fire

*Everything you can fire: phasers, torpedoes and probes.*

Your ship can carry three kinds of weapon, and `fire` works for each of them. Not every ship has all three; the [Library computer](#topic-library) and the weapons panel show what yours has.

| Weapon | Range | Speed | Best for | Fire it |
|---|---|---|---|---|
| [Phasers](#topic-phasers) | short (about 2,000) | instant | close fights, stopping incoming torpedoes | `fire phasers`, **F** |
| [Torpedoes](#topic-torpedoes) | long (10,000–25,000) | fast, but they take time to arrive | hitting from outside phaser range | `fire torpedoes`, **T** |
| [Probes](#topic-probes) | medium | slow, but most of them home in | slow ships and stationary targets, big warheads | `fire probes at <ship>`, **P** |

#### Phasers

```text
fire phasers
fire all phasers 45
fire phasers 1 2 3 spread 10
phaser all 20
fp 1 2 s 10 at gorkon
```

- The number after the list is the **spread** in degrees, from 10 to 45. A narrow spread puts the whole charge on one ship. A wide one is weaker but can hit several objects, including torpedoes.
- Phasers fire where they point. Lock them on a ship with `lock banks on <ship>`, or select a target and they lock automatically. See [Lock and turn](#topic-lock).

#### Torpedoes

```text
fire all torpedoes
fire torpedo 1 2 3
fir tor al
torp 1
ft 1-3 at gorkon
```

- Tubes locked on a ship aim ahead of it, leading the target. A torpedo only explodes when it passes within its **proximity** setting of a ship, so a target that changes course can still dodge.
- Tubes reload by themselves after firing. Change the proximity or torpedo type with [load](#topic-loading) and `autoload`.

#### Probes

```text
fire probes at gorkon
probe all at gorkon
fire probes 1 2 course 180
fpr 1 at gorkon
```

- A probe's target or course is set at launch. Afterwards you can steer it, re-target it or blow it up by its control code. See [Probes](#topic-probes).
- Probe launchers must be loaded first. See [Loading and autoload](#topic-loading).

#### Aiming at a part of the ship

Add a subsystem to aim at part of the target: `propulsion`, `weapons`, `shields`, `power`, `sensors` (or `cloak`). Aimed shots trade some accuracy for a better chance of disabling that system.

```text
fire phasers at gorkon weapons
fire all torpedoes at gorkon propulsion
```

> **Coach** Not sure which weapon to use? Open the [Coach](#topic-coach). It checks your target's range against each of your weapons and tells you which shot is on.

See also: [Phasers](#topic-phasers), [Torpedoes](#topic-torpedoes), [Probes](#topic-probes), [Lock and turn](#topic-lock), [Choosing weapons](#topic-weapons-guide).

<a id="topic-phasers"></a>

### Phasers

*Short-range beams that hit instantly but weaken with distance.*

Phasers are beam weapons mounted in **banks**. A hit lands the instant you fire, but it weakens with distance and is useless beyond the bank's range, which is about 2,000 for most ships. After firing, a bank recharges by itself from the ship's power.

#### How hard they hit

A bank's hit grows with its charge, shrinks as the **spread** widens, and falls off with range: at three-quarters of maximum range a hit is only half as strong as at point blank. The shield facing the shot absorbs part of every hit.

Damage per bank for a Dreadnought (charge 10, range 2,000) before shields:

| Range | Spread 10 | Spread 20 | Spread 45 |
|---|---|---|---|
| 0 | 22 | 11 | 5 |
| 500 | 19 | 10 | 4 |
| 1,000 | 16 | 8 | 4 |
| 1,500 | 11 | 6 | 2 |
| 1,800 | 7 | 4 | 2 |

> **Tip** Use spread 10 against a ship. Use a wide spread to sweep incoming torpedoes, or several small targets, out of the sky.

#### Firing

```text
fire all phasers spread 10
fire phasers 1 2 3 spread 10
phaser all 45
```

#### Pointing the banks

Each bank covers an arc around its mount. Locked banks follow their target; others hold a fixed **mark**, an angle from your bow (0 is dead ahead, 180 is astern).

```text
lock banks on gorkon
lock all banks on gorkon
lock banks 1 2 and 3 on gorkon
turn banks to 180
turn banks 1 2 to 90
```

#### Charging, spread and roles

```text
disable banks 3 4
enable all banks
spread 20
role banks 5 6 defense
```

- **disable** stops a bank recharging, which saves power on a damaged ship. It keeps whatever charge it already has. **enable** resumes charging.
- **spread** sets the default spread used by **F** and by fire control.
- **role** reserves banks for point defense (`defense`), keeps them for attack (`offense`), or lets them do both (`flex`). See [Fire control and point defense](#topic-firecontrol).

#### Status

`banks` (or `status banks`) shows each bank's charge, whether it is locked or manual, its mark, its spread and its target.

```text
banks
```

See also: [Fire](#topic-fire), [Lock and turn](#topic-lock), [Fire control and point defense](#topic-firecontrol), [Shields](#topic-shields).

<a id="topic-torpedoes"></a>

### Torpedoes

*Long-range warheads with proximity fuses. Types differ in speed, punch and reach.*

Torpedoes are fired from **tubes**. They fly in a straight line at a fixed speed (plasma torpedoes home in) and explode when they pass within their **proximity** distance of a ship. Unlike phasers, their warhead does not weaken with range, apart from plasma, which fades as it travels.

On the map a torpedo is a pulsing point of light with a fading trail behind it, so you can see where a spread is heading at a glance.

#### The torpedo envelope

A torpedo is harmless until it has flown long enough to **arm**, and it self-destructs when its time fuse runs out. Together these set the band of ranges where a shot can work:

- **minimum range** = arming time × closing speed. Fire closer than this and the torpedo passes the target before it arms.
- **maximum range** = (arming time + time fuse) × closing speed.

The closing speed includes the target's own motion. A ship charging at you shrinks the minimum and stretches the maximum; a ship running away does the opposite. The [Coach](#topic-coach) works this out for your current target.

> **Tip** Torpedoes miss more often the farther they fly, because the target has longer to change course. The nearer half of the envelope gives the best hit rate.

#### Torpedo types

| Torpedo | Id | Warp | Warhead | Arms at | Reach | Max prox | Guidance | Reload | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Romulan Plasma Torpedo | `plasma` | 15 | 30 plasma (fades with distance) | 1,500 | 19,500 | 750 | homing | 6 c | Romulan Bird of Prey, Romulan War Eagle |
| Federation Mark 8 | `mk8` | 15 | 21.6 antimatter | 1,425 | 10,425 | 800 | straight | 4 c | - |
| Plasma X Torpedo | `xplasma` | 21 | 18 plasma (fades with distance) | 2,100 | 25,200 | 500 | homing | 5 c | Romulan Frigate |
| Borg torpedo | `bgt` | 24 | 18 antimatter | 1,440 | 18,240 | 600 | straight | 4 c | Borg Cube, Borg Probe, Borg Sphere |
| Federation Mark 7 | `mk7` | 30 | 14.4 antimatter | 1,200 | 19,200 | 800 | straight | 3 c | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon TX torpedo | `ktx` | 27 | 10 antimatter | 2,700 | 18,900 | 500 | straight | 3 c | Klingon Battle Cruiser, Klingon Dreadnought, Klingon Escort, Klingon Frigate |
| Orion Bullet Torpedo | `opbt` | 20 | 8 antimatter | 2,000 | 12,000 | 400 | straight | 3 c | Orion Anarchist, Orion Armadillo, Orion Saboteur |
| Orion Shield Auger | `oshb` | 20 | 8 shield-bore | 2,000 | 12,000 | 400 | straight | 5 c | - |

- **Warp** is the torpedo's speed: faster torpedoes arrive before the target can react, and reach farther.
- **Warhead** is the blast strength. Shield-bore warheads damage shields but not the hull.
- **Arms at** and **Reach** are the envelope against a stationary target.
- **Max prox** is the widest proximity fuse the type allows.
- **Reload** is how many cycles a tube takes to charge for the next torpedo.

#### Firing

```text
fire all torpedoes
fir tor 1,2,3
torp all
ft at gorkon
```

#### Loading, proximity and type

Tubes reload by themselves (**autoload**). Use `load` to change the proximity, `autoload` to change the torpedo type, and `unload` to empty a tube so it can be reloaded with new settings.

```text
load tubes prox 400
load tubes 1 2 350
autoload tor mk8
unload tubes 1 2
disable tubes 3 4
enable all tubes
```

> **Coach** A torpedo bursts the moment its target comes within the proximity distance, and its blast fades to nothing at the edge of its reach: 50 × the warhead (a little more for Federation designs), so 920 units for a Mark 7. At proximity 800 a Mark 7 bursts near that edge and barely scratches the target. At 460 it delivers about 70% of its punch, and at 200 nearly 90%. A wide proximity still catches nimble ships, so the [Coach](#topic-coach) suggests a setting that balances the two (half the blast reach at most).

#### Shields soak up hits

A shield facing the blast absorbs damage up to its strength before anything reaches the hull, and each hit drains it by only a fraction of what it absorbed. Heavy ships such as the Klingon Dreadnought have shields strong enough to swallow whole volleys. After each volley the log tells you what happened ("Hits on Wraith: 8, all absorbed (shield 1 now 87%)"). Keep hitting the same shield until it collapses, or turn to strike a weaker one; a `scan` shows them all.

#### Leading and dispersion

Tubes locked on a ship aim where it will be, using its speed and course. A **dispersion** angle fans a salvo around that point. Against a ship that is jinking, a fan gives one or two hits instead of a clean miss.

```text
lock all tubes on gorkon
lock tubes 1 2 on gorkon 0
lock all tubes on gorkon with a dispersion of 30
```

You can also fan a single salvo as you fire it, without changing the locks. The angle is the whole width of the fan, centred on the lead point, with the torpedoes evenly spaced across it:

```text
fire all torpedoes spread 10
fire tubes 1 2 3 4 at gorkon fan 20
```

Pick the angle with the proximity fuse in mind. Each torpedo already bursts anywhere within its proximity of the target, so a fan only helps once its width at the target's range is more than that. At 6,000 units, 2° spans only about 210 units, well inside a Mark 7's 800 proximity, so it changes nothing. 10° spans about 1,050 units and 20° about 2,100: wide enough to cover a sharp turn, with the torpedoes about 1.4° and 2.9° apart in an eight-tube salvo. Too wide a fan leaves gaps between torpedoes bigger than the proximity, and a target in a gap is missed by all of them.

#### Status

```text
tubes
```

The table shows each tube's charge, lock, mark, contents and proximity. A tube shown at 100% loads its torpedo on the next cycle.

See also: [Fire](#topic-fire), [Loading and autoload](#topic-loading), [Lock and turn](#topic-lock), [Choosing weapons](#topic-weapons-guide), [Coach](#topic-coach).

<a id="topic-ceasefire"></a>

### Cease fire

*Stop every weapon at once, and the officers with them; stand down takes every station back too.*

`cease fire` stops your ship's guns at once. It never waits on the language model, and it drops any line still being interpreted.

- Every officer's standing objective ends, such as Seven disabling their shields, and a bait volley about to follow its first torpedo is called off.
- Officers and the fire computer (assisted or automatic weapons) hold fire until you fire again yourself or say `open fire`.
- Point defense keeps shooting down incoming torpedoes.

```text
cease fire
hold fire
stop firing
open fire
```

You can say it to an officer too: `seven, cease fire`, `seven, stop firing` or `worf, hold fire`. A cease fire stops the guns only: if Spock is flying the ship, he keeps flying it.

Plain words work the same way, with or without an officer's name: `hold your fire`, `weapons cold`, `don't shoot`, `stop attacking`, `break off`, `disengage`, `leave them alone`, `never mind`. Punctuation doesn't matter (`Cease fire!`), and a cease fire can share a line with another order: `cease fire and take evasive action`. An officer's answer still on its way from the language model is dropped, so nobody starts shooting again after you said stop.

A new order to attack, such as `target their engines` after a cease fire, lifts the cease fire for that officer's work; you don't have to say `open fire` first.

#### Stand down

To stop an officer outright, tell them to stop: `spock, stop`, `spock, stand down`, `seven, belay that`, `seven, forget the shields` or `seven, stop disabling their shields`. Everything a cease fire does happens, and the officer hands back what they were running: their station, the bridge if they had it, and evasive manoeuvres. A helm that was chasing the enemy steadies on its present course.

To stop the whole bridge at once, say `stand down`, `everyone stop`, `all stations, stand down`, `stop everything`, `knock it off` or `belay all`. Every station and the bridge come back to you, and a running named order stops too.

```text
spock, stand down
seven, stop
stand down
everyone stop
belay all
```

Taking a station back with `assume <station>` (or `assume all`) also ends whatever that officer was working on, such as Seven disabling their shields, without holding your fire. `belay` on its own stops a running named order and ceases fire.

> **Note** A bare `stop` is all stop for the helm (warp 0), as in Begin. Say `stop firing` to stop the guns, or `stand down` to stop the officers. If an officer is still flying or working when you say it, the log tells you who.

See also: [Fire](#topic-fire), [Bridge officers](#topic-crew), [Named tactical orders](#topic-orders).

<a id="topic-probes"></a>

### Probes

*Slow, steerable warheads that home in. Controlled by code after launch.*

Probes are slow but smart. Most home in on a target, they can be steered or re-targeted after launch, and their warheads are large. A ship slower than the probe cannot outrun it. Data probes carry little or no warhead but extend your sensors.

| Probe | Id | Warp | Warhead | Arms after | Time fuse | Reach | Max prox | Sensor | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Dreadnought Killer (dink) | `dnk` | 3.5 | 30 | 5 c | 12 c | 4,200 | 1,500 | 0 | Klingon Dreadnought, Klingon Frigate |
| Romulan Pak Probe | `rmpp` | 2 | 28 | 6 c | 20 c | 4,000 | 1,000 | 0 | Romulan Bird of Prey, Romulan Frigate |
| Federation Probe X-2 | `px2` | 2.5 | 25 | 5 c | 20 c | 5,000 | 1,200 | 0 | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon Light Pak Probe | `klpp` | 2 | 20 | 6 c | 20 c | 4,000 | 1,000 | 0 | Klingon Battle Cruiser, Klingon Escort, Orion Anarchist, Orion Armadillo |
| Klingon Data Probe | `kdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Romulan version of Klingon Data Probe | `rdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Federation Probe Data-2 | `pxd2` | 20.5 | 0 | 1 c | 30 c | 61,500 | 1,200 | 20,000 | - |

#### Loading

Probe launchers do not need power to load or fire. When you load a launcher, its probe gets a **control code** such as `h01`, which you use to control it after launch.

```text
load launchers 1 prox 500 time 20
load all launchers 450 15
load probes 200 10
unload all launchers
launchers
```

- The first number is the **proximity** fuse and the second the **time** fuse in cycles.
- A launcher you unload stays empty until you load it again.

#### Launching

```text
fire probes at gorkon
probe all at gorkon
fire probes 1 2 course 180
```

#### Controlling probes in flight

`status probes` lists your active probes with their codes, courses, ranges and targets.

```text
status probes
turn probe h01 course 90
turn all probes to course 270
lock probe h01 on gorkon
lock all probes on gorkon
detonate h01
detonate all
```

> **Tip** If you know an enemy probe's control code, you can steer or detonate it too.

See also: [Fire](#topic-fire), [Loading and autoload](#topic-loading), [Choosing weapons](#topic-weapons-guide).

<a id="topic-lock"></a>

### Lock and turn

*Point banks and tubes at a ship, or at a fixed angle.*

Weapons fire in the direction they point. A **locked** mount follows its target. Tubes also lead it: they aim where the target will be when the torpedo arrives. Each mount can be locked on a different ship. If the target is destroyed, the mount returns to manual control.

#### Lock

```text
lock banks on gorkon
lock all banks on gorkon
lock banks 1 2 and 3 on gorkon
lock tubes on gorkon 0
lock tubes 4 5 on gorkon 24
lock all tubes on gorkon with a dispersion of 45
lock on gorkon
lock off
```

- The number after the ship in a tube lock is the **dispersion**: the angle a salvo fans out around the lead point.
- `lock on <ship>` locks phasers and tubes together. Selecting a target with a click or **Tab** does the same.

#### Turn

`turn` points mounts at a **mark**, an angle relative to your bow: 0 is dead ahead, 90 to starboard, 180 astern, 270 to port. A turned mount keeps that angle as the ship manoeuvres.

```text
turn banks to 180
turn all banks to 0
turn banks 1 2 to 90
turn tubes to 0
```

Probes are steered by course instead. See [Probes](#topic-probes).

See also: [Phasers](#topic-phasers), [Torpedoes](#topic-torpedoes), [Targeting](#topic-targeting).

<a id="topic-loading"></a>

### Loading and autoload

*Torpedo and probe loading, proximity and time fuses, and ordnance type.*

Torpedo tubes and probe launchers **autoload**: after firing, each reloads with the same settings. `load` sets the fuses and starts loading, `unload` empties mounts so new settings take effect, and `autoload` picks the ordnance type or switches automatic reloading off.

#### Torpedo tubes

```text
load tubes prox 500
load tubes 1 2 3 350
load all tubes prox 425
unload all tubes
```

#### Probe launchers

```text
load launchers 1 prox 500 time 20
load all launchers 450 15
unload launchers 2
```

#### Autoload

```text
autoload tor all mk8 400
al tor al mk7 1200
autoload probes 1 px2 300 20
al tor off
al tor now
```

The words after `autoload` are, in any order: the weapon (`tor` or `probe`), the mounts, the ordnance type, the proximity, a probe time fuse (`time 20`), `on`/`off`, and `now` to reload at once with the new settings.

> **Note** Proximity limits depend on the ordnance type. If you ask for more than a type allows, the order is refused and the limit is shown. See the tables in [Choosing weapons](#topic-weapons-guide).

See also: [Torpedoes](#topic-torpedoes), [Probes](#topic-probes).

<a id="topic-firecontrol"></a>

### Fire control and point defense

*Let the ship's computer fire for you, and defend against incoming torpedoes.*

The ship's computer can share the gunnery. It never overrides an order you give: a command from you always takes priority for several cycles.

#### Fire modes

| Mode | The computer… |
|---|---|
| **manual** | fires only when you order it |
| **assisted** | fires at *your* target when the shot is good |
| **automatic** | picks the nearest enemy if you have no target, and fires when the shot is good |

```text
mode phasers automatic
mode tubes 1 2 assisted
mode tubes manual
```

The **Mode** button in the weapons panel cycles these too. Autoload never fires anything; it only reloads.

#### Point defense

Point defense uses phaser banks to shoot down incoming torpedoes and probes. How far ahead the computer predicts, and how precisely it aims, depend on how advanced and how damaged your ship's computer is.

| Doctrine | Banks it uses |
|---|---|
| **off** | none |
| **conservative** | reserved banks only, against imminent hits |
| **balanced** | reserved banks, plus flexible banks against dangerous salvos |
| **aggressive** | any idle bank, against anything armed and in range |

```text
pd balanced
pd conservative reserve 5 6
role banks 1 2 offense
```

Press **V** to cycle doctrines, or right-click a bank in the weapons panel to reserve it.

See also: [Phasers](#topic-phasers), [Torpedoes](#topic-torpedoes).

<a id="topic-targeting"></a>

### Targeting

*Select a target, and aim at a part of it.*

Your target is the ship your weapons and the fire computer concentrate on. Click a ship, press **Tab**, or use `target`. On the map its brackets swing in and close on it, then pulse gently while the lock holds.

```text
target gorkon
target #7
target gorkon warp core
aim life support
aim hull
target off
```

#### Aiming at her systems

Add a system to aim at part of the target, or say `aim <system>` once she is targeted. You can aim at:

- **shields** (shield generators): a destroyed generator leaves a permanent hole in her shields, which your transporters can beam through.
- **warp core** (`power`, reactors and batteries): without power her shields fail, and then her life support.
- **life support** (`crew`, the crew decks): every aimed hit that lands kills a slice of her crew.
- **weapons**, **phasers**, **torpedoes**: her phaser banks and torpedo tubes.
- **engines** (`propulsion`, warp drives and impulse).
- **sensors** (sensors and computer), and **cloak**.

Press **R** to cycle through them, or click them in the Target panel. Aimed fire only works on hits that get through her shields, so knock the facing shield down first. Each hit that gets through goes for what you aimed at, keeps after a system it has already hurt, and does only about a third of the usual damage to her hull (a fifth when aimed at life support). Torpedoes carry your aim too, though a warhead is less precise than a phaser. A system knocked about by aimed fire takes her crew about three times as long to repair in space, so what you knock out stays out. A shot that misses its mark is a single stray hit somewhere else. Accuracy is best close in, with a narrow phaser spread (`spread 10`) and a fresh `scan`. Fire at the hull (`aim hull`) when you simply want her destroyed.

> **Tip** `capture <ship>` hands the whole job to an officer (see [Disabling or taking out enemy ships](#topic-disable)). To do it yourself: aim at her **shields** until a generator is destroyed, then at her **life support** until her crew is gone, and [board](#topic-transport) her. Spare her **engines** if you mean to keep her: warp drives are the slowest system to repair, and a destroyed one has to be rebuilt from nothing.

See also: [Lock and turn](#topic-lock), [Scan](#topic-scan), [Fire](#topic-fire).

<a id="topic-weapon-colors"></a>

### Who fired what

*Every race's phasers and torpedoes have their own colour, and a torpedo shot down looks different from one that hit.*

Each nation's weapons have their own colour on the map, so in a crowded fight you can tell at a glance whose beam that was and whose torpedoes are coming. They differ in shape as well, which tells them apart even if two colours look alike to you: Klingon and Orion disruptors fly as bright bolts one after another, and each nation's torpedoes look their own way in flight (a turning photon star for the Federation, a harsh flickering flare for the Klingons, a big wobbling ball of plasma for the Romulans, a flickering bolt for the Orions). A heavier warhead is drawn bigger and brighter.

#### Reading a shot

A phaser shot happens in steps, and each one tells you something. First the bank that's firing lights up, so you see which bank it is and which way it bears. Then the beam races out to the target. If the target's shield holds, the beam stops on the shield bubble and splashes across it. If it gets through, it reaches the hull, throws sparks, and gas vents from the breach. A full-charge, tightly focused shot is thicker and brighter than a weak one, and a point-defense shot is a thin, quick flick.

A shield facing that gives way bursts into sparks, and a system hit inside a ship shows as a small blast on her hull a moment later.

An enemy torpedo heading for one of your ships is ringed faintly with its proximity-fuse radius, so you can see how close is too close. If it's off the edge of the map, a red marker at the edge shows where it's coming from.

When your own ship takes a heavy blow the map gives a small jolt. `hud jolt off` keeps it still; `hud jolt on` brings it back.

| Nation | Phasers | Torpedoes and their blasts |
|---|---|---|
| Federation | —— steady beam | ◆ torpedo, ○ blast |
| Klingon | - - - string of bolts | ◆ torpedo, ○ blast |
| Romulan | —— steady beam | ◆ torpedo, ○ blast |
| Orion | - - - string of bolts | ◆ torpedo, ○ blast |
| Borg | ≈≈ cutting beam that drags across the hull | ◆ torpedo, ○ blast |
| Not yet identified | —— white beam | ◆ white |

A ship you haven't identified yet fires in plain white: identifying it with sensors also tells you its colours.

#### Hit or shot down?

- **A torpedo that went off where it was meant to** (on a ship, or where it was sent to burst) flashes white-hot in the middle and throws out a bright ring in its nation's colour, the size of its blast.
- **A torpedo shot down** by point defense or any other phaser fire gives a small grey star of debris and no flash. If it was already armed it still bursts, so a faint grey ring shows how far the blast reached, but it went off early, wherever the beam caught it.

So a salvo that reaches its target is a string of bright coloured rings around it, and a salvo the enemy's point defense stopped is a scatter of grey stars on the way in.

The colours are set per nation in `content/data/factions.toml` (`colors`: `phaser`, `torpedo`, `phaser_style` and `torpedo_style`), if you would like to change them.

See also: [Phasers](#topic-phasers), [Torpedoes](#topic-torpedoes), [Fire control and point defense](#topic-firecontrol).

## Defense

<a id="topic-shields"></a>

### Shields

*Raise, lower and reinforce your six shields, and keep a strong one facing the enemy.*

Your ship has six shields, each guarding a 60° slice around the hull. A hit is taken by the shield facing the attacker; the others are not touched.

| Shield | Faces |
|---|---|
| 1 | bow (straight ahead) |
| 2 | forward starboard (right) |
| 3 | forward port (left) |
| 4 | aft starboard |
| 5 | aft port |
| 6 | stern |

```text
raise all
lower 4 5 6
raise shields 1 2 3
shields
reinforce 1
reinforce off
```

- `raise` and `lower` take a list of shields or `all`. `drop` and `down` also lower; `up` also raises.
- `shields` alone (or `status shields`) prints each shield's state, strength and recharge rate.
- **G** raises or lowers every shield at once.

#### Energy

A shield that is up costs energy every cycle, and it recharges when it has been weakened. Power goes to warp and life support before shields, and if what is left cannot pay for every raised shield, **none** of them hold that cycle. When power is tight, lower the shields that face away from the enemy, or slow down.

#### Reinforcing

`reinforce <n>` makes one shield lose strength at half the rate when it is hit, at four times the energy cost. Only one shield can be reinforced at a time. Reinforce the one facing the enemy, then turn to keep it there. `reinforce off` ends it.

#### When shields must come down

Transporters cannot beam through a raised shield, so both your shield and the other ship's shield that face each other must be down. See [Transporters and boarding](#topic-transport).

Surrendering lowers every shield.

See also: [Fire control and point defense](#topic-firecontrol), [Tactics](#topic-tactics), [Transporters and boarding](#topic-transport), [Status displays](#topic-status).

## Sensors and status

<a id="topic-status"></a>

### Status displays

*Text readouts of your ship, weapons, shields and fleet, printed in the console.*

Status commands print a table in the console, in the style of Begin's text displays. The table stays on screen and updates live until you press **Esc** or type another command. Scroll the log with the mouse wheel.

| Command | Shows |
|---|---|
| `report` | Name, class, survivors, condition, course and warp (desired and current) and target |
| `damage` or `status` | Every system with its damage, from reactors to transporters |
| `banks` | Each phaser bank: charge, mark, lock, role and arc |
| `tubes` | Each torpedo tube: what it holds, proximity, charge and lock |
| `launchers` | Each probe launcher: probe type, proximity, timer and lock |
| `status probes` | Your probes in flight, with their control codes |
| `shields` | Each shield's state, strength and recharge rate |
| `fleet` | Your allies, their state and their standing orders |
| `group` | Which allies are in which numbered group |

`status` takes the name of any of these as a second word, so `status banks` is the same as `banks`. The short form `st` works too.

```text
report
damage
status tubes
banks
shields
fleet
```

#### The panels

The right-hand panels show the same information at a glance: the weapons panel lists every bank, tube and launcher; the engineering panel shows power, heat and damage. Press **I** for the damage view, which lays the damage out over a picture of your ship.

Scanning an enemy prints its damage table the same way. See [Scan](#topic-scan).

See also: [Scan](#topic-scan), [Chart](#topic-chart), [Fleet and groups](#topic-fleet), [Shields](#topic-shields).

<a id="topic-chart"></a>

### Chart

*A table of every ship you can see, with range, bearing, course and speed.*

`chart` prints a table of every ship and base you have on sensors: its name, warp, course, bearing, range, the mark (its bearing relative to your bow) and its class.

```text
chart
chart on
chart by distance
chart from gorkon
chart all
chart off
```

| Form | Effect |
|---|---|
| `chart` | Print the table once |
| `chart on` / `chart off` | Keep the table up and updating, or close it |
| `chart by name`, `by distance`, `by nation` | Sort order |
| `chart from <ship>` | Measure ranges and bearings from another ship instead of yours |
| `chart <ship> off` / `chart <ship> on` | Hide a ship from the table, or show it again |
| `chart all` | Show every ship, including hidden ones |

Ships you have not identified yet show as `#` followed by their contact number, such as `#7`. You can type that number in any command that takes a ship (`scan #7`, `target #7`), and a detailed [Scan](#topic-scan) identifies the ship.

See also: [Scan](#topic-scan), [Display range](#topic-range), [Status displays](#topic-status).

<a id="topic-range"></a>

### Display range

*Zoom the tactical map by setting how far it reaches.*

`range <distance>` sets how far the tactical map reaches from its centre, from 200 to 500,000 units. `range` on its own tells you the current setting.

```text
range 8000
range 40000
display 2000
range
```

- `display`, `zoom` and `scale` mean the same thing, and `scan <distance>` does too.
- The mouse wheel and the **+** and **−** keys zoom in steps. **C** centres the map on your ship.
- A useful rhythm: zoom out to 40,000 or more to find the enemy, then in to 5,000 to 10,000 for a gunfight.

The display range is only a view. It does not change what your sensors can see.

See also: [Chart](#topic-chart), [Scan](#topic-scan), [Keyboard and mouse](#topic-controls).

<a id="topic-scan"></a>

### Scan

*Take a detailed scan of a ship to learn its class and damage.*

`scan <ship>` points your sensors at one ship for a detailed scan. The scan identifies the ship and prints its damage table, so you can see which of its systems are hurt and pick your next target.

```text
scan gorkon
scan
scan #3
```

- `scan` alone scans your current target.
- The ship must be on your sensors and within detailed-scan reach, which is shorter than detection range. If it is too far, the reply tells you how close you need to be.
- Scanning one of your own ships shows its damage table straight away.
- **X** scans the current target.

`scan` followed by a distance, such as `scan 8000`, sets the [display range](#topic-range) instead, as in the original game.

Cloaked ships can't be scanned until they show themselves. See [Cloaking device](#topic-cloak).

See also: [Chart](#topic-chart), [Status displays](#topic-status), [Targeting](#topic-targeting).

<a id="topic-library"></a>

### Library computer

*Look up the specifications of any ship class, torpedo or probe.*

The library computer holds the specifications of every ship class, torpedo and probe in the game. Ask it about a subject and it prints the details in the console.

```text
computer ship klingon d7
computer ship federation
computer torpedo photon
computer probe
library torpedo
```

- `computer ship <nation> <class>` shows one class. Leave the class out to list every class of that nation.
- `computer torpedo <type>` and `computer probe <type>` show one weapon. Leave the type out to list them all.
- Any unique beginning of a name works, so `computer ship fed` lists the Federation classes.

The [Choosing weapons](#topic-weapons-guide) shows the same weapon numbers side by side in tables.

See also: [Choosing weapons](#topic-weapons-guide), [Scan](#topic-scan).

## Ship systems

<a id="topic-repair"></a>

### Repair

*Tell your damage-control crews which system to fix first.*

Your crew repairs damaged systems on its own, a little each cycle. `repair <system>` tells them to put that system first: it is repaired four times faster, and everything else at half speed. `repair all` spreads the work evenly again.

```text
repair shields
repair drives
repair phasers
repair all
```

| System words | |
|---|---|
| `reactors`, `batteries` | power |
| `drives` (or `warp`, `engines`), `impulse` | movement |
| `phasers` (or `banks`), `tubes` (or `torpedoes`), `launchers` (or `probes`) | weapons |
| `shields`, `sensors`, `computer`, `transporters`, `tractor`, `cloak` | everything else |
| `hull` | the hull itself (see below) |

#### What limits repair

- Repairs go faster with a full crew. A ship that has lost most of its crew repairs slowly, and below a tenth of its crew it cannot repair at all.
- While an engineering team is on the engines (the [engine boost](#topic-boost)), every repair but the drives' own runs at half speed.
- A **destroyed** system is rebuilt by the crew in space, from 100% down, so it takes the longest. At a starbase every repair runs twice as fast. See [Docking](#topic-dock).

#### The hull

The crews patch the hull as well as the systems. They work slowly in battle, at a quarter of the usual rate, while the ship has been hit in the last 15 cycles or an enemy ship is within 12,000. Out of the fight, a full crew patches about 0.4% of the hull every cycle. In space they can only bring it back to 75%; a starbase restores the rest, and quickly (see [Docking](#topic-dock)). `repair hull` makes the hull the priority.

#### Letting an officer direct repairs

Spock keeps an eye on the damage. When a system is badly hurt, or the hull drops past another quarter, he tells you what needs fixing and offers to direct the crews. Say yes in your own words, or use the console:

```text
spock, manage repairs
repair auto spock
repair manual
```

While he directs them he picks the priority as the fight changes: engines if the ship can't move, the shield facing the enemy, the weapons, power, then a badly holed hull. He says where he sends them. Any `repair <system>` you give yourself takes the crews back, as does "spock, I'll handle repairs" or `repair manual`.

#### Seeing what is being repaired

In the Own ship panel, the dots on the ship diagram are its systems, placed where they sit in the hull. The big ones are reactors and warp drives, and the small ones are batteries, phaser banks, torpedo tubes, probe launchers, sensors and the rest. Each is coloured by health: teal is intact, amber damaged, red badly damaged and grey destroyed. Systems under repair have a pulsing ring, thick for the current priority. Hover over a dot to see what it is. The **Repairs** line counts the jobs under way and shows the priority, and who sets it; **Hull** says "under repair" while it is being patched. The damage screen (`I`, or click the diagram) shows the same, with a legend.

Check progress with `damage`. See [Status displays](#topic-status).

See also: [Status displays](#topic-status), [Docking](#topic-dock), [Targeting](#topic-targeting).

<a id="topic-boost"></a>

### Engine boost

*Ask engineering for all she's got: a team keeps the drives cooler so you can run hard for longer, at the cost of slower repairs.*

When you know you need to run the engines hard, to close on a fleeing ship or to get clear of one, ask your chief engineer for **all she's got**. He puts an engineering team on the warp drives. For the next **30 cycles** the drives heat up more slowly, so they run **40% longer** before they overheat.

The team has to come from somewhere. While it is on the engines, **every other repair runs at half speed**, the hull included. Repairs to the drives themselves carry on as normal. Nothing else changes: the drives don't run hotter afterwards, and there is no cool-down. When to call it, and when to send the team back, is your choice.

#### Asking for it

Say it to Geordi in your own words, or use the console:

```text
geordi, give me all she's got
geordi, boost the engines
la forge, squeeze more out of the warp drive
boost
```

Other ways of saying it work too: "everything you've got", "put a team on the engines", "keep the engines from overheating", "run the engines hard", "I need more from the engines". If you say it to another officer, engineering still answers: it's their team.

When the drives are heating towards their limit and you are running engineering yourself, Geordi may offer: *"The drives are running hot, Captain. Want me to put a team on them?"* Press **Y** to make it so.

#### Ending it early

```text
geordi, back to repairs
end the boost
boost off
```

Otherwise the team works its 30 cycles and Geordi tells you when they are back on repairs. If every warp drive is lost, the team goes back at once.

#### Seeing it

In the Own ship panel, while the team is on the engines:

- the **Drives** label turns the light blue of the repair crews, and a thin line of the same colour under the heat bars runs down with the time the team has left;
- the **Repairs** line reads *slowed*, with *team on engines* when there is room.

Hover over the drives for the cycles left. The heat bars themselves rise more slowly while it lasts.

> **Tip** The boost buys time, not speed. It doesn't raise your top warp: it lets you hold it. Call it as you start a long run, not when the gauges are already red.

See also: [Repair](#topic-repair), [Course and speed](#topic-helm), [Status displays](#topic-status).

<a id="topic-tractor"></a>

### Tractor beam

*Grab a ship within 1,000 units and drag it along with you.*

A tractor beam locks onto a ship within 1,000 units and pulls it along as you move. Use it to drag a crippled ally out of a fight, or to hold an enemy still for your torpedoes and boarding parties.

```text
tractor gorkon
tractor off
release
```

With an enemy targeted, the **Tractor** button in the Target panel does the same, and becomes **Release** while the beam holds. The panel tells you when the target is inside tractor range. On the map the beam is a pale blue band between the two ships.

- Only ships fitted with a tractor beam can use one, and it must be working.
- The beam costs energy every cycle you hold it.
- How firmly it holds depends on your tractor's strength against the other ship's mass, and weakens with distance. A heavy ship, or one more than 1,250 units away, breaks free.
- Damage to the tractor, or running out of power, drops the beam.

Allies can tow for you: `tell <ally> tow <ship> to <base>` drags a ship to within 3,000 units of a base and lets it go, close enough to dock. See [Ally orders](#topic-tell).

See also: [Docking](#topic-dock), [Ally orders](#topic-tell), [Transporters and boarding](#topic-transport).

<a id="topic-dock"></a>

### Docking

*Dock at a friendly base to repair faster, rebuild destroyed systems and shelter from fire.*

Ships can dock at a friendly base that has docking bays. Fly within 1,000 units and give the order.

```text
dock starbase 12
undock
dock off
```

From the screen: select the base in the **Fleet** tab (click it on the map) and press **Dock**, which becomes **Undock** while you are aboard. A docked ship is labelled *docked* on the map.

#### While you are docked

- Repairs run twice as fast, destroyed systems included.
- Your crew does not draw on your own life support.
- Weapons and explosions cannot reach you: the base shelters you.
- You move with the base, and you cannot escape the battle on your own.

The base's bays hold a limited mass of ships. If they are full, you have to wait for someone to leave.

#### Allies and bases

- `tell <ally> dock <base>` sends an ally to dock, and `tell <ally> undock` brings it out.
- A base you command can bring a ship aboard with `tell <base> recover <ship>`, and push one out with `tell <base> eject <ship>`.

If a base is destroyed, every ship docked in it is cast loose.

See also: [Repair](#topic-repair), [Tractor beam](#topic-tractor), [Ally orders](#topic-tell).

<a id="topic-cloak"></a>

### Cloaking device

*Hide your ship from enemy sensors, at the cost of energy, until you fire or are hit.*

Every Romulan ship carries a cloaking device, and so does the Enterprise after her refit in one tour. While it runs, enemy sensors can't find the ship at all.

```text
cloak on
cloak off
decloak
```

- `cloak` and `cloak on` engage it; `cloak off`, `decloak` or `uncloak` drop it.
- The cloak costs energy every cycle. If power runs out, it fails.
- **Firing gives you away.** For about a cycle after you fire a phaser or launch a torpedo or probe, the enemy can see you. Being hit shows you for about three cycles.
- Damage to the cloaking device switches it off, and a damaged cloak can't be engaged until it is repaired.

#### Hunting a cloaked ship

When an enemy that can cloak vanishes at close range, it has almost certainly cloaked, and it has not gone far. Your science officer says so, with its last fix and heading, and calls it again when it shows (it fires, is hit, or is lit up). Watch for the moment it fires, and have tubes ready. Wide-spread phasers and torpedoes with a big proximity are your best chance.

The simplest way is to ask for it by name:

```text
seven, find the talon
hunt talon
where is the talon?
hunt off
```

- `hunt <ship>` (or `find`, `locate`, or telling an officer to find her) sets your science officer looking. They set up the tachyon detector and the deflector, burst the detector where she should be by now, and keep at it until she shows. Then she is your target, so you can fire at once. Nothing else is fired, and a hunt doesn't lift a cease fire.
- With no ship named, they look for the target you lost, else the nearest ship that has cloaked.
- `where is <ship>?` gives the last fix without starting anything. `hunt off` calls the search off.

Torpedoes still work against a ship you can't see. Fired at her, they fly to her last known position, and the bridge tells you how each shot ended: a hit (and she shows for a moment), a burst with nothing in reach, a round shot down, or a fuse run out with no sign of her.

Better still, ask Spock and Seven for a [Tachyon detector torpedo](#topic-tachyon) detector torpedo. Its burst lights up cloaked ships long enough to target them. At short range, a [Deflector tachyon pulse](#topic-deflector) pulse ahead of the bow does the same job without using a tube.

#### Plasma trails

A warp drive that is badly damaged vents plasma while the ship is at warp, and **any** ship's sensors can follow it, cloak or no cloak. A cloaked ship with a leaking drive shows on your map as an **exhaust contact**: a fading rose-coloured wake that ends in a soft, wavering ring where she probably is. It is a rough fix, give or take 700 units, and it never shows her clearly.

It works both ways. If your own drives are hurt, Geordi warns you that you are venting plasma. Repair the drives, or drop below warp 1, and the trail goes cold.

```text
sweep
sweep talon
design seeker
seeker talon
```

- `sweep` (or "Seven, look for exhaust") has your science officer follow plasma much further than usual for a while and report every trail found. `sweep <ship>` looks for one ship's.
- `design seeker` has Seven or Spock build a **plasma-seeker** torpedo. `seeker <ship>` fires it into her trail, and `seeker` alone fires down the nearest one. The torpedo flies the trail itself, every turn she made, and homes on her at the end of it. If the trail goes cold first, it bursts where the trail ends.

#### The Enterprise's refit cloak

In the tour, the Enterprise can be refitted with a cloak built from Romulan salvage and made to fire through. When she cloaks, enemy sensors lose her at once, with no lingering track to follow. She can fire without lifting the cloak: the enemy sees the flash where the shot came from and nothing more, so move after every shot. A damaged warp drive still gives her away.

See also: [Tachyon detector torpedo](#topic-tachyon), [Deflector tachyon pulse](#topic-deflector), [Scan](#topic-scan), [Chart](#topic-chart), [Tactics](#topic-tactics).

<a id="topic-tachyon"></a>

### Tachyon detector torpedo

*Spock and Seven build a one-off torpedo whose burst lights up cloaked ships.*

Your sensors can't see a cloaked ship at all. When you think one is out there, Spock and Seven of Nine can work together on a torpedo that carries a tachyon emitter instead of a warhead. Where it bursts, the particles scatter off any cloaked hull nearby and outline it for about 30 cycles, long enough to target it and fire.

#### Asking for one

Talk to either of them, in your own words or the console:

```text
spock, there's a cloaked ship out there
seven, can you build a tachyon detector?
design tachyon
```

They take about 20 cycles with a full crew (longer if the ship has lost crew). When it is ready, the round goes into one tube (an empty one if possible; a torpedo already in that tube goes back to the magazine), and they tell you which.

#### Firing it

```text
tachyon 45 8000
tachyon gorkon
tachyon
```

- `tachyon <bearing> <range>` bursts it at that point, which is what you want when you only have a guess.
- `tachyon <ship>` bursts it at a ship's last known position, which works well for a ship that just vanished.
- A bare `tachyon` aims at your current target's last position.

The burst lights up every cloaked ship within 6,000 units, and the round can reach about 39,000 units. It does no damage. Once it is fired, the tube goes back to loading ordinary torpedoes, and you can ask for another detector.

#### Where to aim

A ship that cloaks keeps moving, so aim a little ahead of where it vanished along its last heading. The science officer reports the last fix when a contact is lost. If you have ships in a fleet, only your ship needs to burst it: every ship on your side sees what the particles reveal.

See also: [Cloaking device](#topic-cloak), [Bridge officers](#topic-crew), [Torpedoes](#topic-torpedoes), [Talking to your officers](#topic-talking).

<a id="topic-transport"></a>

### Transporters and boarding

*Beam crew between ships, send boarding parties, or move your command to another ship.*

Transporters reach 3,000 units. Every beam needs a clear path: **your shield facing her must be down** (lower it with `lower`), and **at least one of her shields must be down**, either destroyed or under 5%.

```text
beam excalibur
beam excalibur 20
board gorkon
board gorkon 30
```

From the screen: the **Board** button in the Target panel sends the default party to your target, and the panel says whether it is inside transporter range. In the **Fleet** tab, **Beam 20** sends 20 crew to the selected ally, and **Take command** moves you aboard it. A ship with enemy boarders on it shows their number in red under its name.

#### Changing ships

`beam <ally>` moves you and your command to one of your own ships within range. Your old ship carries on under an AI captain. Do this when your flagship is crippled but the fight is not over.

#### Moving crew

`beam <ally> <count>` sends that many of your crew to an ally, to replace its losses.

#### Boarding

`board <ship>` sends a boarding party onto an enemy. Without a number, it sends a sensible party for your transporters and crew. Each cycle the boarders fight the defending crew. Each nation fights boarding actions with different skill. If the defenders fall below six while six or more boarders still stand, the ship is **captured** and joins your side. If the boarders are wiped out, the attack fails.

#### Taking a ship

`capture <ship>`, or "Worf, capture the Votek", has an officer do all of this for you (see [Disabling or taking out enemy ships](#topic-disable)). By hand:

1. `target <ship>`, `spread 10`, and close in. `aim shields` and fire until one of her shield generators is destroyed. That hole stays open; a shield you merely knock down comes back within a few cycles.
2. `aim life support` and keep firing. Her crew falls quickly, and her hull holds. When it is gone she is adrift (derelict) with her shields down.
3. `lower`, then `board <ship>`. A derelict falls to your boarders at once. A ship with crew left fights them first.
4. She is yours: a prize crew holds her, and a captain from among them takes her helm. `beam <ship> 60` sends her more crew, since repair crews only work once she has a tenth of her complement. `beam <ship>` takes you aboard to command her yourself, and `repair <system>` sets the repair priority.

If the ship you left helpless is the last enemy, the battle stays open for 60 cycles so you can board her. Her crew can rebuild even destroyed systems, but that takes longest, and warp drives are the slowest of all to repair, so choose what you shoot.

Allies can board for you with `tell <ally> board <ship> <count>`. See [Ally orders](#topic-tell).

See also: [Shields](#topic-shields), [Ally orders](#topic-tell), [Tractor beam](#topic-tractor).

<a id="topic-deflector"></a>

### Deflector tachyon pulse

*Spock and Seven set the deflector dish up to sweep a cone ahead of the ship and expose cloaked ships.*

Spock and Seven of Nine can reconfigure the main deflector dish to emit tachyons. Once it is set up, each pulse sweeps a cone ahead of your bow and shows every cloaked ship inside it for 20 cycles, long enough to target it and fire.

#### Setting it up

```text
seven, use the deflector to find them
spock, can you set up a tachyon pulse?
design deflector
```

They need about 12 cycles with a full crew. The dish stays set up for the rest of the battle.

#### Pulsing

```text
pulse
seven, pulse
```

- The pulse covers 60° centred on your heading, out to 15,000 units. Turn the bow toward where you think the enemy is before you pulse.
- Each pulse takes 40 energy from the batteries and the dish needs 30 cycles to recharge.
- The cone shows briefly on the map, and a message says how many cloaked ships it found.

#### Pulse or torpedo?

The [Tachyon detector torpedo](#topic-tachyon) detector torpedo reaches much further (about 39,000 units) and covers a full circle around its burst, but it takes a tube and has to be built again for every shot. The deflector pulse is quick and reusable, but it is short-range and only looks ahead. If an officer has the bridge (see [Giving an officer the bridge](#topic-conn)), Spock and Seven use whichever fits.

See also: [Tachyon detector torpedo](#topic-tachyon), [Cloaking device](#topic-cloak), [Giving an officer the bridge](#topic-conn).

<a id="topic-destruct"></a>

### Self-destruct and surrender

*Blow up your own ship on a countdown, or surrender it.*

#### Self-destruct

`self destruct <cycles>` starts a countdown. When it reaches zero, your ship explodes, and the blast damages every ship nearby, friend or foe. The more power your ship had, the bigger the blast.

```text
self destruct 10
abort
```

- `abort` (or `self destruct abort`) stops the countdown, but only while more than five cycles remain. After that, nothing can stop it.
- The last five cycles are announced to everyone, so enemies may try to get clear.
- Beam to an ally first if you want to keep fighting. See [Transporters and boarding](#topic-transport).

#### Surrender

`surrender` lowers every shield and gives up the ship. A surrendered ship takes no further part in the battle, and it counts against you in the assessment.

```text
surrender
```

See also: [Transporters and boarding](#topic-transport), [Tactics](#topic-tactics).

## Allies

<a id="topic-tell"></a>

### Ally orders

*Give standing orders to the other ships in your fleet, one at a time or by group.*

`tell <ally> <order>` gives one of your ships a standing order. Allies keep following their orders until you change them, and they report back in the console. `order` means the same as `tell`. Wherever an order names a ship, `me` means your own.

```text
tell excalibur attack gorkon
tell excalibur escort enterprise at 2000
tell excalibur defend me
tell 1 attack gorkon
tell excalibur hold fire
tell excalibur run
tell excalibur report
```

An ally carries several orders at once: one **movement** order, a **target**, **hold fire** or **open fire**, a **weapon** preference and a **group**. A new movement order replaces the old one, but leaves the target alone, and so on.

#### From the screen

Click an ally on the map, or its row under **Contacts**, to open the **Fleet** tab beside the map. It shows that ally's mission and has a button for the common orders: escort me, defend me, attack my target, hold or open fire, run, withdraw, stop, cancel, dock at the nearest base, disengage, release a tow, and report. The **1**, **2** and **3** buttons put the ally in a group, or take it out again. Use **‹** and **›** to step through your allies.

On the map, each ally's mission is written under its name. A faint blue dashed line runs to the ship it is escorting, defending or towing, and a red one to its ordered target. The selected ally is marked with blue corners.

#### Combat orders

| Order | Effect |
|---|---|
| `target <enemy>` | Shoot at this ship when it can, but keep its current movement order |
| `attack <enemy>` | Go after this ship and fight it, dropping the movement order |
| `torpedo <enemy>`, `phaser <enemy>`, `probe <enemy>` | Attack it, favouring that weapon |
| `hold fire` / `open fire` | Stop firing, or start again |
| `disengage` | Forget the ordered target |

#### Movement orders

| Order | Effect |
|---|---|
| `escort <ship> [at <range>]` | Stay with a friendly ship (3,000 units unless you say) |
| `defend <ship>` | Stay close to a friendly ship and fight whatever threatens it |
| `approach <ship> [<range>]` | Close to a range of any ship and hold there (2,000 unless you say) |
| `course <c>` or `hold course` | Fly a set course |
| `run` | Get away from the enemy at full speed |
| `withdraw` | Pull back out of the fight and wait in reserve |
| `stop` | Come to a halt |
| `cancel` | Drop the movement order and go back to fighting on its own |

#### Ship handling orders

| Order | Effect |
|---|---|
| `dock <base>` / `undock` | Dock at a friendly base, or leave it. See [Docking](#topic-dock). |
| `tractor <ship>` / `release` | Grab a ship in a tractor beam, or let it go. See [Tractor beam](#topic-tractor). |
| `tow <ship> to <base>` | Drag a ship to a base |
| `board <enemy> <count>` | Close in and send a boarding party. See [Transporters and boarding](#topic-transport). |
| `recover <ship>` / `eject <ship>` | Bases only: bring a ship into the bays, or push it out |

#### Groups

Put allies in numbered groups, then order the whole group by its number.

```text
tell excalibur join 1
tell lexington join 1
tell 1 escort enterprise
tell excalibur leave
group
```

#### Checking on allies

`tell <ally> report` prints that ship's report, with its current mission. `fleet` lists every ally with its state and orders. See [Fleet and groups](#topic-fleet).

Allies are captained by the AI. Each captain has a personality, so some press an attack harder than others, and a badly damaged ship may break off even without an order.

See also: [Fleet and groups](#topic-fleet), [Tactics](#topic-tactics), [Docking](#topic-dock), [Tractor beam](#topic-tractor), [Transporters and boarding](#topic-transport).

<a id="topic-fleet"></a>

### Fleet and groups

*See every ship under your command, its state and its standing orders.*

`fleet` lists every ship under your command with its state, where it is, and its mission: the standing orders it is following, such as `Escort Enterprise at 3,000` or `Hold fire`. An ordered target is shown in brackets.

`group` lists the numbered groups and which allies are in each one.

```text
fleet
group
status fleet
tell 1 report
```

The table stays up and updates live until you press **Esc** or type another command.

To change what an ally is doing, see [Ally orders](#topic-tell).

See also: [Ally orders](#topic-tell), [Status displays](#topic-status), [Chart](#topic-chart).

## Crew

<a id="topic-crew"></a>

### Bridge officers

*Hand a station to its officer, take it back, and hear what your crew thinks.*

Four officers run the stations on your bridge. Each one can run their **station** for you, so you can concentrate on the decisions that matter. Three more stand by: Sulu takes tactical when Worf is away, Chekov takes the helm when Spock covers science, and the Doctor runs sickbay. See [Your crew](#topic-your-crew).

| Station | Officer | Runs |
|---|---|---|
| Helm | Commander Spock | course and speed: closing, opening the range, weaving |
| Tactical | Lieutenant Worf | targets, phasers, torpedoes, probes, point defense |
| Engineering | Lieutenant Commander Geordi La Forge | shields, reinforcing, repair priorities, cloak |
| Science | Seven of Nine | scanning the target and every other contact |

```text
delegate tactical
delegate helm science
delegate all
assume helm
assume all
crew
```

- `delegate <station>` hands a station to its officer. `assume <station>` takes it back and ends anything that officer was working on. `all` covers every station.
- "I have nav", "I have weapons" (or fire, phasers, torps), "I have shields", "I have sensors" or "I have the conn" takes that station (or every station) back. Taking the helm or the weapons back also ends any attack an officer is running, such as Seven disabling their shields.
- `stand down` takes every station and the bridge back at once and holds fire; `spock, stand down` (or just `spock, stop`) does it for one officer. See [Cease fire and stand down](#topic-ceasefire).
- The **Crew** tab, beside **Contacts** and **Fleet** under the weapons, shows who runs each station. Click **Captain** / **Officer** to switch, or click an officer's name to speak to them.
- `crew` lists your officers, who is running what, and how each of them feels about you.
- To let one officer command the whole ship, say "Seven, take the bridge". See [Giving an officer the bridge](#topic-conn).
- To have Seven knock out an enemy's shields, phasers or torpedoes, say "Seven, disable the Klingons' shields". See [Disabling enemy systems](#topic-disable).

#### You stay in command

- Anything you order yourself overrides the officer for a few seconds, then they carry on from where you left them.
- Officers never pick a target when you have chosen one. They only choose when you have none.
- Officers never retreat, surrender, self-destruct, beam across or give orders to allies. Those decisions are yours.
- If you beam to another ship, your officers come with you. Their stations go back to you until you hand them over again.

Each officer has a personality. Worf is aggressive and closes for the kill; Spock holds a careful range; Geordi spends repair effort where it matters most; Seven scans everything, efficiently.

#### Chatter

Your officers comment on the battle: Worf when torpedoes go out, Geordi when the hull or the engines are in trouble, Seven when new contacts appear. `crew chatter off` quiets them, and `crew chatter on` brings them back.

To ask them questions or give them orders in plain words, see [Talking to your officers](#topic-talking).

See also: [Giving an officer the bridge](#topic-conn), [Talking to your officers](#topic-talking), [Officers and language models](#topic-llm), [Keyboard and mouse](#topic-controls).

<a id="topic-conn"></a>

### Giving an officer the bridge

*Let Spock, Seven, Worf or La Forge command the whole ship, and take it back whenever you like.*

Any of your officers can take command of the whole ship. They run every station at once, with their own personality, while you watch, step in on the decisions you care about, or take the bridge back.

```text
seven, take the bridge
spock, you have the conn
conn worf
I have the bridge
conn captain
```

- **Giving it:** tell an officer to take the bridge (or the conn, or command), or type `conn <officer>`.
- **Taking it back:** say "I have the bridge" (to anyone, or to nobody in particular), type `conn captain`, or click the banner at the top of the map.
- While an officer has it, a banner across the top of the map says who, and the **Crew** tab shows them in command of every station.

#### Who fights how

The officer in command uses their own judgement and temperament: Worf closes fast and hits hard, Spock keeps a careful, calculated range, Geordi looks after the ship first, and Seven is efficient and relentless. They pick a target only when you haven't, and they never retreat, surrender or self-destruct.

Spock and Seven will also go after cloaked ships on their own: if an enemy vanishes, they build a [Tachyon detector torpedo](#topic-tachyon) detector and fire it where the ship should be.

#### Flying the ship

An officer at the helm, whether they have the conn or just the helm station, flies like a captain who wants to live:

- **Dodging torpedoes.** Enemy torpedoes fly straight at where your ship would be if it held its course. The moment a salvo is launched, the helm works out where each round will pass under a spread of possible turns and speeds, using your ship's real turn rate and acceleration, and takes the one that makes them miss. A big ship at high warp turns slowly, so it can't dodge everything, but in test battles it cut the share of enemy torpedoes that hit by a quarter to over a third.
- **Flying for Seven.** When Seven is working on an objective (see [Disabling or taking out enemy ships](#topic-disable)), the helm sets up her shots: with a salvo loaded it brings the ship just inside torpedo range and outside the enemy's phasers, and keeps the strongest shield toward the enemy. A faster enemy that is already close can't be held off, so then the helm fights it head on rather than show it the stern.
- Otherwise the officer closes and fights as an AI captain would.

#### Seeing what they are doing

While an officer has the conn or the helm, or is working an objective, a panel at the top left of the map shows each of them: their job, what they are doing right now ("Evading 4 torpedoes, coming to 229 warp 6", "Salvo of 8 on a ring around Wraith") and how the job stands ("Wraith 3/6 shields out, weakest up 15%"). On the map, the helm's chosen course is a dashed arrow (amber while dodging, with the torpedoes being dodged marked in red), Seven's target is bracketed with what she is after, and her last salvo's ring of bursts fades out over a few seconds.

They also say what they are doing as each step starts, even with chatter off, and when the job is finished Seven sums up what it took.

#### Stepping in

You are still the captain. Any order you give, such as `target gorkon`, `helm 90 warp 6` or `fire all torpedoes`, overrides the officer for a few seconds, then they carry on from there. To keep one station for yourself, `assume <station>` takes it back while the officer keeps the rest. When you take the bridge back, the stations go back to whoever ran them before.

See also: [Bridge officers](#topic-crew), [Talking to your officers](#topic-talking), [Tachyon detector torpedo](#topic-tachyon).

<a id="topic-talking"></a>

### Talking to your officers

*Ask an officer for a report or advice, or give an order in plain words.*

Start a line with an officer's name (a comma after it is optional, and the first few letters will do, as in `sev status`), or use `ask`:

```text
spock, what do you recommend?
worf, status
geordi, take engineering
seven, scan gorkon
worf, fire all torpedoes
ask spock how do we beat this ship
```

- Officers answer to their name, rank-free nicknames (`geordi`, `seven`) and their station (`tactical, status`).
- **Reports.** "status", "report" or "sitrep" gets a report on that officer's station.
- **Advice.** "what do you recommend?", "advice" or any other question gets that officer's best idea for their stations, with the command to carry it out. Spock advises on everything.
- **Orders.** Any console command works, as long as it belongs to that officer's station: Worf will fire, Geordi will raise shields, but Worf won't steer.
- **Stations.** "take the helm", "take over" or "you have the conn" delegates the officer's station; "I have the helm" or "I relieve you" takes it back.
- **Stopping.** "stop", "stand down", "belay that", "break off", "forget the shields" or "stop disabling their shields" stops that officer at once: weapons hold, objectives end, and their station (and the bridge, if they have it) comes back to you. "everyone stop" or a bare `stand down` does it for the whole bridge. See [Cease fire and stand down](#topic-ceasefire).

#### Rapport

Each officer remembers how you treat them, from one battle to the next. Thanks and taking their advice build rapport; insults wear it down. `crew` shows each officer's mood. Rapport colours how they speak to you, and later parts of the game will draw on it.

#### Offline and LLM answers

Without any setup, officers answer from what your sensors know: reports, the [Coach](#topic-coach)'s advice for their station, and their own lines. To have them answer in their own words, connect a language model: see [Officers and language models](#topic-llm). Either way they only know what your side knows.

#### Traits, and never the same line twice

Each officer has a few **traits**, words on how they come across: Spock is "precise and emphatic, dry wit, unflappable", and Seven is "highly effective, efficient, coolly confident, ex-Borg precision". With a language model, the traits colour everything an officer says. Their remarks during the battle are written fresh each time, in their voice, from what is happening, and the model is shown what they said lately so it doesn't repeat itself. Two battles never sound the same. Traits change how an officer talks, not how well they fight. Without a model, officers use their written lines.

Each officer also has a **response style**: how they answer when the model writes their words, such as length, tone and register. Worf's is "terse, clipped reports; few words and no pleasantries" and Seven's is "factual, crisp, coolly confident".

Make the officers your own in `config/officers.toml` (copy `config/officers.example.toml`). Anything you write there wins, officer by officer and key by key; anything you leave out stays as the game ships it:

```toml
[worf]
traits = ["honour-bound", "blunt", "quietly proud of his captain"]
response_style = "short soldier's reports, a growl when it goes badly"
interests = ["cooking for the crew", "Klingon opera"]
quirks = ["judges a battle the way he judges a meal"]

[worf.lines]
idle = ["I have made rokeg blood pie for the crew. You will find it... honourable."]
victory = ["Victory. Tonight, the crew eats well."]
```

Everything you can set:

- `name` and `rank`: who they are on your bridge. A renamed officer answers to the new name in the console.
- `aliases`: more names to address them by.
- `traits` and `response_style`, as above.
- `persona`: a whole new character brief for the model, in place of the game's.
- `background`, `interests` and `quirks`: added to the brief. Interests show most in **quiet moments**: when no enemy is in sight and the bridge has been silent a while, an officer now and then says something off duty.
- `[<officer>.lines]`: their own lines for any moment, which work with or without a model. `idle` lines are the quiet-moment ones; the other moments (`greeting`, `target`, `victory`, `hull`, and the rest) are listed in `src/begin/content/data/officers.toml`.
- `rapport_floor`, from -1 to 1: the lowest their regard for you can fall, however you treat them.

The game passes what you write to your model as you wrote it, and none of it changes how well an officer does the job.

Officer lines are in `src/begin/content/data/officers.toml`. Edit them, change a personality, or swap in a different officer for a station.

See also: [Bridge officers](#topic-crew), [Officers and language models](#topic-llm), [Coach](#topic-coach).

<a id="topic-disable"></a>

### Disabling or taking out enemy ships

*Ask Worf or Seven to knock out the shields, phasers, torpedoes, engines or sensors of one ship or several, to take ships out altogether, or to capture one, and she works out how.*

Tell Seven what you want knocked out, and on whom. She makes a plan, carries it out, reports each ship as its systems go down, and tells you when the job is done or can't be done.

```text
seven, disable the Klingons' shields
seven, knock out Gorkon's torpedoes
seven disarm them
seven, take out the Wraith
worf, capture the Votek
disable gorkon zantha phasers
target their shields
take out their engines
target all their torps
destroy wraith
disable off
```

"Take out", "destroy" or "finish off" without naming any systems means the whole ship: she keeps at it until it is gone.

#### Just that system, and then she is spared

Disabling means just the system you named. "Target their shields", "target her shields", "take out their shields", "hit their shields", "bring down their shields" and "disable their shields" all mean the same: focus fire on the shields until they are out, then stop. A slip of the keyboard is fine ("target thier sheilds"). "Target all their shields" does it to every enemy, one after another, and "target the other ship's shields" to the enemy you haven't targeted.

Name two systems and both are done in turn: "target their shields and engines". The ship is spared only once the last of them is out.

- Torpedoes tear the hull as well as the systems, so once her hull is half gone the officer uses aimed phasers only.
- When the job is done, the ship is **spared**: nobody else on the bridge, and not the fire computer, shoots at her again. The officer tells you so. Your aim goes back to the hull, which is always the default.
- To finish her, fire on her yourself, or say `target their hull`, `destroy her` or `open fire`.
- A ship you named (`target gorkon shields`) or `aim shields` only sets your own aim; nobody is given the job.

- **What:** shields, phasers (or disruptors), torpedoes (tubes), weapons (phasers and torpedoes), engines, sensors or the cloaking device.
- **Whom:** ship names, a race ("the Klingons", "the Romulans"), or "all" / "them". With no ship named, she takes your current target, or every enemy if you have none.
- **Stop:** `disable off`, or "Seven, cancel that". A new order about the same systems replaces the old one.
- Typed without an officer's name, the console gives the job to your weapons officer (Worf). Name an officer to give it to them instead: `seven, disable their shields`. `disable tubes 1 2` still switches off your *own* tubes; it only means the enemy's when you name a ship, a race, or a system your tubes don't have.

#### How she does it

- **Scans** each target to see what is working, and to know when the job is done.
- **Aims phasers** at the chosen systems, focused tight for accuracy, whenever banks are charged and bear.
- **Torpedoes come as one full salvo from close range,** just outside the distance they need to arm. The enemy's point defense gets little time to react and has too many rounds to stop. Seven fuses each round to burst on a ring around where the target will be, with the proximity fuse set tighter than usual, so a dodge in any direction still lands inside a blast.
- **Two ships close together** get a salvo burst between them, so one volley hits both.
- **Bait.** Against a trigger-happy defense she fires one torpedo first. Their point defense pours several phaser banks onto it, and the rest of the salvo arrives a second later while those banks are still recharging. Klingon and Orion crews fall for it, and so does any crew that has lost a lot of people (a scan tells her). Disciplined Romulan and Federation crews send one bank per torpedo and keep the rest charged, so against them she uses the ring burst instead.

- **She says what she is doing** as she goes, the activity panel at the top left of the map shows her current step and the scan results, and when the job is done she sums up what it took: "That took 8 bait volleys, 2 salvos, 80 torpedoes in all, 3 phaser volleys and 8 scans, in 66 seconds." See [Giving an officer the bridge](#topic-conn) for how an officer at the helm flies to give her the shots.

#### Capturing a ship

"Capture the Votek", "seize her" or "take her intact" (or `capture votek`) asks the officer to take the ship and keep her. They go about it in three stages, and say which one they are on:

1. **Open a shield.** Aimed phasers and torpedoes on her shield generators until one of her shields is down. Torpedoes stop once her hull is half gone, so she isn't blown apart.
2. **Thin her crew.** Phasers only, aimed at her life support, through the open shield. They steer to keep that gap toward us when we are close, unless you are flying yourself.
3. **Board.** Once 60 or fewer of her crew are left, they hold fire, close to transporter range off her open side, lower our facing shield just while each boarding party beams across, and raise it again. The job is done when she joins our side.

Fly close, or give Spock the helm (`conn spock` or `delegate helm`): the officer working the order only steers once she is close, and won't chase her across the map. Klingons are fanatical and may ram or blow themselves up when beaten, so watch the range. `capture off` cancels.

#### Baiting yourself

```text
bait
bait gorkon
```

`bait` fires one torpedo at your target (or the ship you name) and every other loaded tube a cycle later.

#### How enemy point defense behaves

Every ship's point defense depends on who is manning it. Its race sets its discipline, from the trigger-happy Klingons and Orions to the careful Romulans and Starfleet. Crew losses slow its reactions, spoil its aim and erode its discipline, and a damaged sensor array or computer makes it react late. Every round in a salvo counts: a disciplined crew answers a salvo of seven with up to seven banks.
- **A target that cloaks** is hunted with the [Deflector tachyon pulse](#topic-deflector) pulse or the [Tachyon detector torpedo](#topic-tachyon) detector.
- When a target's hull gets low she stops using torpedoes on it, because the job is to disable the ship, not destroy it.

She doesn't steer. Keep the ship within torpedo range (about 3,500 to 7,500 units) and ideally phaser range, or hand the helm to Spock (`delegate helm`). Your own orders still come first: anything you fire or target yourself overrides her for a few seconds.

A system counts as knocked out when it is damaged at all, because a damaged system stays off line until it is fully repaired. Weapons count as disabled when every phaser or tube is off line; shields when at least two thirds of the generators are. Enemy crews do repair, so act on her report quickly.

See also: [Bridge officers](#topic-crew), [Targeting](#topic-targeting), [Giving an officer the bridge](#topic-conn), [Deflector tachyon pulse](#topic-deflector).

<a id="topic-llm"></a>

### Officers and language models

*Let your officers answer in their own words through Anthropic, OpenAI, OpenRouter or a local Ollama model.*

The game is complete without a language model: officers answer offline. If you connect one, every question you put to an officer goes to the model with that officer's personality and a summary of what your ship knows. When you give an order, their answer can include commands, which go through the console like anything you type and are only carried out for that officer's stations. When you ask a question, any commands in the answer are only suggestions: they appear under the reply for you to type, and nothing is carried out.

The same model also lets you type orders at the console in plain English: see [Orders in plain English](#topic-plain-english).

Requests run in the background, so a slow or failing model never stalls the battle. If a request fails, the officer answers offline and says why.

#### Setting it up

The easiest way is the main menu's **Settings** page, under **Language model**: pick the provider, type the model's name, and press **Test it** to see an answer (see [Settings](#topic-settings)). From a terminal, `begin --llm` saves the same `llm` section of `config/settings.json` in the project folder, and `--llm-test` asks Spock one question to prove it works:

```
begin --llm provider=ollama model=lfm3 think=off
begin --llm-test
```

`--llm-test` prints the provider, the model, whether thinking is on, how long the answer took, the raw reply, and what Spock would say. `--llm provider=off` switches the model off again, and `--llm think=` (nothing after the `=`) removes a setting.

You can also edit the file by hand, or use environment variables. Keys are read only from the environment and are never saved.

```
"llm": {"provider": "anthropic", "model": "<model id>"}
"llm": {"provider": "ollama", "model": "lfm3", "think": false}
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
- `think` (Ollama) turns a local reasoning model's thinking on or off: `true` or `think`, `false` or `nothink`, or a level such as `low`, `medium` or `high` for models that offer levels. Leave it out to use the model's own default. Thinking makes answers slower but sometimes better; for chat during a battle, off is usually the better choice. The model's reasoning is never shown, only its answer. If a model cannot think, Ollama refuses `think: true`, and the officer's error message says so.
- `console` decides what you type at the console goes to the model: `on` (the default: only lines the console doesn't recognise), `always`, or `off`. See [Orders in plain English](#topic-plain-english).
- `timeout` is how many seconds to wait for an answer: 120 by default for Ollama, since a local model may need loading first, and 45 for the others. `max_tokens` caps the length of an answer.
- The environment variables `BEGIN_LLM_PROVIDER`, `BEGIN_LLM_MODEL`, `BEGIN_LLM_BASE_URL` and `BEGIN_LLM_THINK` override the file. Set `BEGIN_LLM_PROVIDER=off` to turn it off for one session.

The console log says which provider the officers are using when a battle starts.

#### A second model for character voices

A second model can speak for the game's characters while the first keeps the jobs that follow rules. It suits a model that is better at staying in character, or at alien languages: Klingon captains who use tlhIngan Hol, Romulans who are coldly formal. Set it up on the main menu's **Settings** page, under **Character voices** (or press **V** on the main menu): its model, who it speaks for, and a **Test it** button. It is kept in `config/settings.json` under `llm`, and a terminal works too:

```
begin --llm character.provider=ollama character.model=<model> character.for=captains,taunts
begin --llm-voice-test klingon
```

```
"llm": {"provider": "ollama", "model": "lfm3",
        "character": {"provider": "ollama", "model": "<model>", "for": ["captains", "taunts"],
                      "factions": ["klingon"],
                      "notes": {"klingon": "Use a few words of Klingon, each followed by its meaning."}}}
```

- `for` is any of `captains` (answering a hail), `taunts` (an enemy calling you), `officers` (answering you), `chatter` (their remarks) and `log` (the captain's log). Left out, it is `captains` and `taunts`.
- `factions` and `officers` narrow it (left out: everyone). `notes` adds a line to a faction's or officer's prompt, or to everyone's with `"*"`.
- `only` pins characters (officer ids, or a faction for its captains) to the second model: everything they say goes there, whatever `for` says, and if it fails they answer offline instead of through the main model. The page's **Only this model** buttons set it for each officer.
- `enabled: false` keeps the settings and lets the main model speak for everyone. `--llm character=off` removes it.
- Plain-English orders, named orders and judging your speeches always stay with the main model. If the second model fails, the main one answers that line, so nobody goes silent.
- Its requests appear in the debug logs under its own model name.

#### What the model sees

The officer's personality, their station, your rapport, the console command syntax, and a short factual summary of the battle: your ship's state, weapons, shields and power, the contacts on your sensors with their range and bearing, and the coach's notes. Never anything your side could not know.

See also: [Talking to your officers](#topic-talking), [Bridge officers](#topic-crew), [Orders in plain English](#topic-plain-english).

<a id="topic-morale"></a>

### Crew morale

*Every crew has spirits that rise and fall with the fight, and a word from the captain can lift them.*

Every ship's crew, yours and the enemy's, has **morale** from 0 to 100. It starts at the race's usual level and moves with the fight:

| Lowers it | Raises it |
|---|---|
| hull damage and crew lost | damage you deal to enemy hulls |
| a system destroyed, a shield collapsing | an enemy ship destroyed or surrendering (most for the ship that did it) |
| a friendly ship lost | repairs completed, the hull patched |
| | your address to the crew |

Out of the fight (no hits for 15 cycles and no enemy within 12,000) it drifts back to the usual level.

Races take it differently. Starfleet crews start at 80 and are hard to shake. Klingons start at 85 and hold under fire, losing little to damage. Romulans start at 75. Orion pirates start at 60 and break quickly once the fight stops paying.

#### What it does

Morale is the crew's will, not its numbers: losing crew already slows repairs and weakens the ship. So its effect is modest. At 50 it does nothing. At 100, repairs run 25% faster, torpedo tubes load 15% faster, and point defense and aimed fire are 15% better. At 0 they are the same amounts worse. Enemy captains with a shaken crew retreat sooner and surrender more readily, and a keen crew keeps them in the fight longer.

#### Seeing it

The Own ship panel shows it beside your crew count ("steady 62"), and the Bridge crew tab shows it with an **Address crew** button. Hover over either to see what it is doing right now. `morale` lists every ship on your side. Spock tells you when the crew's spirits shift sharply, and suggests a word from you when they are low.

#### Addressing the crew

```text
address crew This ship has never lost a fight. Hold together and we bring her home.
rally the crew: steady, people, we have them
```

A speech lifts morale by up to 12 points. With a language model set up (see [Officers and language models](#topic-llm)), it judges how rousing your words are for the moment and Spock tells you how the crew took them; a flat or rude speech does little. Without one, any speech counts as an ordinary good one (8 points). The crew needs a minute (60 cycles) before another speech does any good.

See also: [Bridge officers](#topic-crew), [Repair](#topic-repair), [Status displays](#topic-status).

<a id="topic-hailing"></a>

### Hailing enemy captains

*Open a channel to an enemy captain: demand surrender, tell them to leave, threaten, bluff or just talk.*

Every enemy ship has a captain with a mind of their own, and you can talk to them.

    hail gr'oth Lower your shields and prepare to be boarded. Your crew will be treated well.
    hail all Leave this sector and we will hold our fire.
    hail                       (opens a channel to your current target)
    open a channel to the Gr'oth
    worf, hail the Klingons

Your words are read for what they ask. You can **demand surrender**, tell them to **withdraw**, **threaten** them, **bluff** (claim strength or help you don't have), **taunt** them, or **just talk**, and a hail that asks nothing still tells you their state of mind. Offering fair terms (prisoners treated well, safe passage, a way out with honour) makes a demand more persuasive. Insults make it less so.

#### What decides the answer

The game decides, not the words alone. Each enemy captain has a **temper** and an **obstinacy**, rolled around their race's values:

| Race | Watching their allies battered makes them | At the start they are |
|---|---|---|
| Klingon | angry: they fight harder and go after the ship that did it | stubborn |
| Romulan | wary | very stubborn |
| Orion | frightened | easily talked round |

Every shield you collapse, every torpedo into an ally's hull, and above all every ship of theirs destroyed or taken, is watched by the captains still fighting. Depending on temper it makes them **shaken** or **enraged**, and every loss wears down their obstinacy, so even a stubborn captain comes round once they have seen enough. Their own damage, their crew's [morale](#topic-morale) and the odds as they see them count as well.

A shaken captain retreats sooner and yields more readily. An enraged one closes on you, refuses to listen, and may cut the channel. Anger cools with time; fear lingers.

A **bluff** works only if their scans don't show it up: if they have scanned you and your hull is battered, they will know, and they won't like being lied to.

#### Surrender, and what comes after

A captain who surrenders **lowers their shields and powers down their weapons**. Then it is your choice:

- keep firing, and every hit goes straight into the hull; or
- beam a party of **six or more** across (`beam <ship> <crew>`, or `worf, capture her`). A surrendered crew does not resist: you take the ship without losing anyone, and her crew are held as **prisoners of war**. `prisoners` shows who you hold.

Fire on a ship that has surrendered and every enemy captain who sees it will trust you less. Their next surrender will be much harder to get, and the angry ones will fight to the end.

A captain who agrees to **withdraw** holds fire and leaves the field. Fire on them and the agreement is off.

#### The comms panel

When you hail a ship, or a captain hails you, the comms card shows who is on the channel, their mood, and the last few words exchanged. Enemy ships whose captain you have heard from carry a small mood mark on the map: a red flame when enraged, amber when shaken, blue when wavering, and a white flag once they have surrendered.

Your science officer reads each answer for you ("They are close to giving way, Captain"), and your tactical officer tells you what a surrender or withdrawal means for your next move.

#### With and without a language model

Without a model, your words are sorted by keywords and the enemy answers with lines written for their race and mood. You can change or add lines in `config/hails.toml`; see the bundled `hails.toml` for the layout. With a model ([LLM](#topic-llm)), the model plays the enemy captain. It reads your actual words, judges how persuasive they are, and answers in character, knowing their losses and their mood. Captains also hail you in their own words when what they have seen changes their mind. The model never decides the outcome. It writes both a yes and a no, and the battle picks which one is said.

#### On a tour of duty

Word travels ahead of you. Ships that surrendered to you and were spared, and ships you let withdraw as agreed, make later captains readier to yield; ships you fired on after they had yielded make later captains fight to the end and disbelieve your terms. The briefing in the Ready Room tells you what the enemy has heard.

Prisoners stay in your brig from one stop to the next. In the Ready Room, **Hand over prisoners** passes them to a Starfleet transport, which leaves torpedoes and probes, and every 40 prisoners earns another reinforcement call. Or keep them, and offer them back over a hail ("leave now and we will return your people"): a captain is far readier to withdraw for that, and the prisoners are beamed back to their ship when they agree.

See also: [Crew morale](#topic-morale), [Transporters and boarding](#topic-transport), [Bridge officers](#topic-crew), [Officers and language models](#topic-llm).

<a id="topic-counsel"></a>

### Counsel from the bridge

*Each officer's way forward from here, built from the live fight: go all in on one, or take a step from each.*

Press **O** (or type `counsel`) and your officers each lay out a way forward from where the fight stands now. The panel opens over the left of the map and is rebuilt about once a cycle while it is open, so what they say changes as the battle does.

    counsel                              (each officer's plan for the fight, or the mission)
    counsel destroy the gr'oth           (each officer's way to that goal)
    counsel kill all the borg cubes
    counsel disable all their engines
    counsel capture the mugger
    counsel survive
    counsel general                      (back to the whole fight)
    counsel off

#### Four perspectives

Every officer reads the same picture: our ship in full (shields facing by facing, power, tubes, banks, drives, damage, the crew), every contact as sensors, scans and our own hits have shown her, both sides' torpedo envelopes and phaser ranges, cloaked ships and plasma trails, the Borg's adaptation and Seven's survey, the mission, and what Starfleet can still send. They value different things:

| Officer | Perspective | What they reach for |
|---|---|---|
| Worf (Sulu standing in) | **The sword** | Mass fire on the most dangerous ship, a full salvo into a Klingon's charge, baiting trigger-happy point defense, a prize when one is hurt, killing whatever hunts the ship we protect, running down a runner |
| Spock (Chekov at the helm) | **Geometry and the mind** | The range where our envelope beats hers, the freshest shield toward the enemy, evasive manoeuvres, drawing a group apart, opening the range on plasma, hailing a captain who is close to giving way, putting the ship between a hunter and her prey |
| La Forge | **Keep her alive to win** | Power, shields and repairs, the drives, saving torpedoes, Starfleet's reinforcements, pulling a hurt ally back, the cloak, lowering a shield and beaming people across |
| Seven of Nine (Spock when she is away) | **Know, then strike precisely** | Scanning the threat, disabling exactly the system that decides the fight, finding cloaked ships, the fanned salvo against disciplined point defense, every Borg duty |

Each plan is a title, the reason in a sentence or two with the live numbers, and two to four steps. Every step is a console line, and only lines the console would accept right now are offered.

#### All in, or a bit of each

**All in** (or **1** to **4** while the panel is open) runs every step of that officer's plan and closes the panel. Click a single step to run just that one: take Worf's target, Spock's helm and La Forge's shield. Each plan is a coherent way to fight the next stretch, and so is a careful mix.

#### Aiming the counsel at a goal

Give the counsel a goal and each officer plans their way to it. `counsel destroy the gr'oth`: Worf masses fire on her, Spock brings us round to her weakest shield, La Forge keeps the tubes and the shield toward her up, and Seven scans her or opens a permanent hole in her shields. `counsel disable all their engines`: Seven sets about it ship by ship, Worf aims every weapon at her drives, Spock holds us in the band where torpedoes burst cleanly, and La Forge keeps the tubes loaded. Name ships, classes or nations ("the cubes", "the Klingons", "all of them"). When the goal is done, the counsel says so and goes back to the whole fight. The goal shows at the top of the panel; × clears it.

#### Time

Reading counsel steps the battle back, like typing an order: it eases to a crawl (or stops, with `hud focus pause`) while the panel is open, and runs at your speed again when you go all in, close it, or after twenty seconds. Press **Space** first if you want the whole board frozen while you think.

#### Before the battle

On a tour, the Ready Room has your officers' view of the next stop, two sentences each, from what the tour knows: Worf on the force to beat and where to strike, Spock on how their navy likes to fight and the geometry of the mission, La Forge on how the squadron will arrive and whether to take a refit or call Starfleet, and Seven on what the sensors can and cannot tell us yet.

#### Holding a range

When an officer says to fight a ship at our range, the step is a hold-range order such as `elude gorkon at 9000`: the helm keeps her near that range rather than running off the map (see [Pursue and elude](#topic-pursue)).

See also: [Bridge officers](#topic-crew), [Missions](#topic-missions), [Coach](#topic-coach), [Hailing enemy captains](#topic-hailing), [Disabling or taking out enemy ships](#topic-disable), [The sword and the mind](#topic-sword-and-mind).

<a id="topic-away-team"></a>

### Away teams and the shuttle

*Send Worf (and Seven) across to a Borg ship by shuttle, give them a task, and hail them to change it or call them home.*

The Borg ignore what doesn't threaten them, and a shuttlecraft doesn't. While the Enterprise keeps them busy, Worf can fly across, latch onto the hull and go aboard.

```text
away cube relay
away cube harmonics with seven
away sphere weapons
worf, take a shuttle to the cube and put them to sleep
```

**Tasks:**

- `relay` puts out the vinculum relay, so her drones go dormant.
- `harmonics` steals the Collective's shield harmonics. Seven must go. For a while every weapon you have passes through their shields on every Borg ship, and they learn nothing from it. After several salvos they notice, and you can do it again.
- `weapons` wrecks her weapons. They regenerate, but slowly.
- `charges` plants charges. Get clear: they go off soon after the team leaves.
- `survey` scans her from the inside, which gives you her harmonics and her weak point at once.
- `rescue` brings a drone home. This only works while she is dormant. The Doctor learns from them, and every later scan of the Borg goes further.

**Keep them busy.** The team is safe only while the ship that sent them keeps hurting the hive. If you go quiet (you stop firing, or you cloak), the drones may notice the little ship. Each crossing in one battle is riskier than the last, because they start watching for small craft.

**Hail the shuttle** at any time. It is on the map, marked with its name.

```text
hail galileo come back
hail shuttle disable their weapons
recall
```

A team that is caught is never lost. They beam out, hurt, and the Doctor keeps them in sickbay for a while. Their stations don't go empty: Sulu takes tactical for Worf, Spock takes science for Seven, and Chekov takes the helm Spock leaves.

Against a **dormant** ship within transporter range the team can beam straight across (`away cube charges beam`).

See also: [Fighting the Borg](#topic-borg), [Hailing enemy captains](#topic-hailing), [Bridge officers](#topic-crew), [Transporters and boarding](#topic-transport).

## Game

<a id="topic-time"></a>

### Time, pause and quitting

*Pause the battle, speed it up or slow it down, or end it.*

The battle runs in **cycles**. At normal speed one cycle is one second, and everything in the game is measured in cycles: reload times, torpedo flight, the self-destruct countdown.

```text
pause
resume
time 2
time 0.5
quit
```

- `pause` freezes the battle. You can still type orders, read displays and open this manual; they take effect when you resume. **Space** toggles pause.
- `resume` (or `go`) starts it again.
- `time <x>` sets the speed: `0.25`, `0.5`, `1`, `2` or `4`. **[** and **]** step through the same speeds. Slow time down for a tricky moment; speed it up for a long approach.
- `quit` ends the battle and goes to the assessment.

The battle is fully repeatable: the same starting position and the same orders always give the same result, whatever speed you play at.

See also: [Keyboard and mouse](#topic-controls), [Key macros](#topic-keys).

<a id="topic-keys"></a>

### Key macros

*Bind a function key or Ctrl+letter to one or more console commands.*

`key <key> <commands>` binds a key to console commands. Pressing the key runs them as if you had typed them. Separate several commands with `;`.

```text
key F2 fire all torpedoes
key F3 fire all phasers 10; fire all torpedoes
key ^r raise all; reinforce 1
key F4
key
```

- Keys you can bind: **F2** to **F8**, **F10** to **F12**, and **Ctrl+letter**, written `^a` to `^z`. **F1** opens the manual and **F9** the debug view, so those two are taken.
- `key <key>` with no commands clears that key. `key` alone lists your bindings.
- Bindings are saved, so they are there next time you play.

#### Keeping a key file

You can also write your bindings in a text file called `begin2.key` in the project's `config/` folder, one per line, in the same form as the command: `F2 fire all torpedoes`. They are loaded when the game starts.

#### Text mode

The original game could switch to a text-only display. This remake always shows the tactical map, so `text` just says so. The status commands print the original text displays in the console instead. See [Status displays](#topic-status).

For the fixed keyboard shortcuts, see [Keyboard and mouse](#topic-controls).

See also: [Keyboard and mouse](#topic-controls), [The command console](#topic-console).

<a id="topic-settings"></a>

### Settings

*Change the game's settings from the main menu: display, sound, battle, the bridge, speaking orders, language models and your officers.*

Choose **Settings** on the main menu (or press **S** there). The sections are down the left; click one, or move through them with **↑** and **↓**. **Esc** or **Back** returns to the menu.

Every change is saved the moment you make it, to the same plain text files the game has always read, so you can still edit them by hand: `config/settings.json` for everything except the officers, and `config/officers.toml` for them. A box you type in (a model's name, a server's address) keeps what you typed when you press **Enter**, **Tab** or click elsewhere; **Esc** puts back what was there. **Ctrl+V** (or **⌘V**) pastes.

- **Display**: the renderer (automatic, graphics card or software) and *Light and glow*. **D** on the main menu opens this section. See [Display and sharpness](#topic-display).
- **Sound**: sound on or off, the volume and the engine hum (drag the slider; **Hear it** plays a sample), and which version of the phaser and torpedo launch you hear: each letter plays it as you pick it. See [Sound](#topic-sound).
- **Battle**: the speed a battle starts at, your officers' chatter, and the map's jolt when the ship takes a heavy blow.
- **Bridge**: the bridge style (full, quiet or classic) and each of its parts. The same choices as `hud bridge` in battle. See [The bridge](#topic-bridge).
- **Speaking orders**: on or off, what hears you (Mac speech, Whisper on this computer, a Whisper server or a cloud service, each with what it still needs), the push-to-talk key, the Whisper model and its download, and the server's address. Test the microphone in battle with `voice`. See [Speaking orders](#topic-voice-orders).
- **Language model**: the provider (or Off), the model, an address for Ollama on another machine, thinking, plain English at the console, and the debug logs. **Test it** asks the model one question and shows its answer. Cloud keys are never kept in the config folder: the page says whether the environment has one. See [Officers and language models](#topic-llm).
- **Character voices**: a second model for the game's characters, with its own provider, model and address, who it speaks for, which races' captains, and which officers use only it. **V** on the main menu opens this section.
- **Officers**: each officer's name, rank, traits and how they speak. The grey words are the game's own; click one to change it, and **As shipped** takes your change out again. Only the one line you change in `officers.toml` is written: your comments, personas, backgrounds and lines stay exactly as you wrote them. See [Bridge officers](#topic-crew).
- **Files**: which of the config files are yours so far, your key macros, and **Open config folder**.

Battle settings changed in battle (the speed, **M** for mute, `hud bridge`, `voice`) are kept the same way and show here next time.

See also: [Display and sharpness](#topic-display), [Sound](#topic-sound), [The bridge](#topic-bridge), [Speaking orders](#topic-voice-orders), [Officers and language models](#topic-llm), [Bridge officers](#topic-crew).

<a id="topic-orders"></a>

### Named tactical orders

*Write a sequence of orders before the battle, give it a name, and run it with one command.*

A named order is a short battle plan you write before the fight: a name and a list of steps. In battle, one command runs the whole list.

| Command | What it does |
|---|---|
| `execute order beta-1` | run the order called beta-1 (`execute beta-1` and `exec beta-1` work too) |
| `beta-1` | the same, by name alone |
| `orders` | list your named orders and their steps |
| `belay` | stop the order that is running; steps already run stay done |

Starting another order belays the one running.

#### Writing them

Orders live in `config/orders.toml`. Copy `config/orders.example.toml` to start; until you do, the examples are loaded so you can try them.

```toml
[beta-1]
note = "Turn away, fan the torpedoes, let Spock fight while Seven goes for their shields"
steps = [
    "helm 180 speed 5",
    "fire all torpedoes spread 10",
    "wait 2",
    "spock, you have the conn",
    "seven, disable their shields",
]
```

Each step runs as if you typed it at the console, so anything the console takes works: helm and weapons orders, shields, orders to allies (`tell agena attack the target`) and orders to your officers (`worf, fire all phasers`, `spock, manage repairs`). An officer only does what their station allows, as when you speak to them yourself.

Steps run in the order written, and later ones can undo earlier ones: a helm order ends evasive manoeuvres, so put `evasive` after the course you want (the helm goes back to that course once the torpedoes are past).

`wait N` holds the order for N cycles of battle time before the next step. While the game is paused, the wait doesn't run down.

**"their", "the target" and "the enemy"** mean whichever ship you have targeted when the step runs, so one order works against any enemy. Target something first, or include a `target` step.

A name is letters, digits, `-` and `_`. An order can't run another order.

#### Plain English

Steps don't have to be in console syntax. With a language model set up (see `help llm`), a step the console doesn't recognise, such as "come about and run", is put into console commands when the battle starts, checked against the console, and remembered in `config/orders.cache.json` so later battles don't need the model for it. Each step the model translates is shown as it runs, so you can see what it made of your words.

Without a model, write steps in console syntax. Either way, a step that won't work is reported in the log when the battle starts, not halfway through the fight, and is skipped if you run the order anyway.

#### Example: a 10° torpedo fan

`fire all torpedoes spread 10` fans a full salvo 10° wide, so an enemy that turns away still meets a torpedo. At ordinary torpedo ranges a spread of only a degree or two adds little, because the 800-unit proximity fuses already cover that much. See `help torpedoes`.

#### Recording an order

You don't have to write an order out. `record strike` starts a recording (● REC shows at the top of the map); fight as you would, and `record stop` saves what you did as the order `strike` in `config/orders.toml`. Displays and repeats are left out, and pauses of two cycles or more are kept as `wait N`. `record off` throws the recording away, and `record last 3 as strike` saves the last three orders you gave. With no name, the order gets one: alpha-1, bravo-1 and so on.

#### The Orders tab

The Orders tab beside Contacts, Fleet and Crew holds every named order as a card, with the key that runs it if one does. Click a card to run it, right-click to see its steps. Key macros (`key F5 ...`) are listed there too.

#### Remembered phrasing

When the language model works out what plain words meant, the game remembers it in `config/phrasebook.json`, and the same words work at once next time, with or without the model. Delete a line from that file to forget it.

See also: [The command console](#topic-console), [Orders in plain English](#topic-plain-english), [Bridge officers](#topic-crew), [Key macros](#topic-keys).

<a id="topic-alert"></a>

### Alert conditions

*alert red, yellow or green: a set of orders at once, and the condition shown on the map.*

`alert red` runs every line of the red condition at once, as if you had typed them, and shows **CONDITION RED** at the top of the map. The tactical officer reads it back.

| Command | Out of the box |
|---|---|
| `alert red` | raise shields all · pd balanced · autoload torpedoes on |
| `alert yellow` | raise shields all · pd conservative |
| `alert green` | lower shields all · pd off |
| `alert` | the condition now, and what each one does |

Make them your own: copy `content/data/alerts.toml` to `config/alerts.toml` and change the steps. Any console line works, including an order to an officer ("geordi, manage repairs").

The red border the panels take on in a fight is the ship's own red alert, and comes and goes by itself.

See also: [Named tactical orders](#topic-orders), [The bridge](#topic-bridge), [Shields](#topic-shields).

<a id="topic-sound"></a>

### Sound

*Soft synthesised sound for what you can see happen, with a volume setting and a mute key.*

The battle has synthesised sound, and each sound tells you something you might not be looking at:

| You hear | It means |
|---|---|
| a beam (phasers) or buzzing bolts (disruptors) | a bank fired; a full-charge shot sounds heavier than a weak one, a point-defense flick lighter still |
| a mechanical knock under the launch | a torpedo left its tube |
| a rising, rushing whoosh | an enemy torpedo is closing on one of your ships: turn now |
| a bright ring that thins as the facing weakens | a shield turned a blow |
| a falling crackle | a shield facing gave way |
| a metallic crunch over a low boom | a blow got through to a hull; deeper for a big one |
| warheads going off, ships breaking up, a cloak's airy sweep | what it sounds like |
| a two-tone whoop, three times | your ship has gone to red alert |
| a clean rising pair of notes | you locked a new target |
| a soft chirp, or a low double tone | an order was taken, or "unable to comply" |
| a short whistle up, or down | a hail channel opened, or closed |
| a low engine hum | the ship herself, under everything, rising with her warp and dipping under a big blast |

A blow from a phaser is heard when the beam gets there, not when the bank fires. The game makes every sound itself when it starts.

You hear only what you can see. Each sound comes from where it happened on the map: from the left or right of the view, quieter and duller when it is off at the edge, and silent when it is far away.

| Command | What it does |
|---|---|
| `M` | sound on or off |
| `sound off`, `sound on` | the same, from the console |
| `sound 40` | set the volume, 0 to 100 |
| `sound` | say what the sound is set to |
| `sound phaser a` | use version a of the phaser (a, b, c or d), and play it |
| `sound torpedo b` | use version b of the torpedo launch |
| `sound hum off`, `sound hum on`, `sound hum 20` | the ship's engine hum: off, back on, or how loud (a share of the volume) |

The phaser comes in four versions. **a**, **b** and **c** are rays: noise fed round a tuned feedback loop so the beam sings at one steady pitch and sizzles while it fires (a is a single piercing tone, b is higher and shimmers, c is the ray over d's buzz). **d**, the standard one, is a harsh square-wave buzz.

The torpedo launch does too. **a**, **b** and **c** are energy pulses: a bright burst that drops fast from high to low and rings away (a is the plain pulse, b winds up first and has d's thump under it, c is short and sharp). **d**, the standard one, is a deep "thoom" with a falling whoosh.

##### Your own sounds

Put a WAV (or OGG) file in `config/sounds/` and it replaces the game's own: `phaser.wav`, `torpedo.wav` (or `launch.wav`), and also `pulse`, `blast`, `fizzle`, `shield`, `breakup`, `cloak`, `alert`, `thunk`, `incoming`, `collapse`, `hull`, `lock`, `confirm`, `deny`, `hail_open`, `hail_close` or `hum` (the hum loops). They are read when a battle starts, and they stay on your machine (git ignores everything in `config/`). Delete the file to go back to the made sound.

The volume, whether it's muted and the versions you picked are saved in `config/settings.json` (`volume`, 0 to 1, `muted`, `sounds`, such as `{"phaser": "b", "torpedo": "a"}`, and `hum`, 0 to 1). Without an audio device the battle is simply silent.

See also: [Keyboard and mouse](#topic-controls), [Time, pause and quitting](#topic-time).

<a id="topic-after-battle"></a>

### After the battle

*Starfleet's assessment of the battle (mission, lives, conduct, cost, a commendation), and the full record behind it.*

When the battle ends, **Starfleet's assessment** opens over the map: the battle as Starfleet Command will read it.

- **The headline** answers the mission when there was one ("Everyone aboard the Aldren is safe."), else who holds the field. Under it, how the battle went in the field.
- **Mission**: how it ended, with the people saved on a rescue.
- **Lives**: people rescued, our crew lost (or "no one of ours lost"), and the enemy's crews spared (surrendered, taken prisoner, allowed to withdraw on terms) and lost.
- **Conduct**: surrenders accepted, prisoners taken, truces kept, and any fire on a ship that had struck her colours.
- **Cost**: the flagship's hull, torpedoes left, systems down, ships lost.
- **Commendation**: at most one, and only for something specific. The **Karagite Order of Heroism** for bringing every soul off a stricken ship, most of them beamed across while the enemy was still fighting (people taken off after the battle don't count toward it); the **Palm Leaf of Axanar Peace Mission** for winning while sparing those who yielded; the **Grankite Order of Tactics** for a decisive victory against several ships that left your ship sound.
- **The bridge**: a line from each officer whose work showed, in their own manner.
- **What follows**: who escaped and what they will report, what the enemy will remember of your conduct, and on a tour, what the mission's result changes.

**Details** opens the full record.

At the top of the details is the result and how decisive it was, the score and how many cycles it took. Below that is your ship's record: hull, crew, morale, phaser hits, torpedoes that hit, damage dealt and taken, and kills.

**Standout officer** names the officer who did the most for the ship, from the ship's own records: the orders they gave that were carried out, the objectives they saw through (Seven's `disable` and `destroy` work), and the projects their station finished. It says nothing about how well you did as captain; the score does that.

Then each side's losses, and a line for every ship: damage dealt and taken, phaser hits, torpedoes and point-defense intercepts.

**Review the field** closes the assessment so you can look over the map, and **Return to menu** ends the battle. Your volume, mute and sound choices are saved on the way out.

#### During the battle

The panel borders pulse red while your ship is at **red alert**: hit in the last few cycles, or with an enemy within 12,000. A two-tone whoop sounds three times when it starts. The borders pulse for a few seconds, then settle to a steady red edge for the rest of the fight. A ship below half hull sheds sparks: always yours, and an enemy's only once a scan has shown the damage, so the map never gives away what your sensors don't know.

See also: [Missions](#topic-missions), [Counsel from the bridge](#topic-counsel), [Bridge officers](#topic-crew), [Crew morale](#topic-morale), [Time, pause and quitting](#topic-time).

<a id="topic-styles"></a>

### Command styles and trust

*Promise a way of commanding before the battle and win keeping it for a ribbon. Officers' trust grows with you.*

#### Command styles

Before the battle starts, promise one with `style <name>`; win keeping it and the ribbon is yours. `style` lists them, with the ribbons you've earned.

| Style | The promise |
|---|---|
| `style chair` | **From the chair**: win without handing a station or the conn to an officer |
| `style book` | **By the book**: every order by its words (console, wheel, proposal, voice); no fire, helm or warp keys, no steering clicks |
| `style silent` | **Silent running**: no hails, never above warp 5 |
| `style green` | **Green crew**: no proposals, no station or conn handed over |
| `style iron` | **Iron captain**: win with the hull above 75% |

The style shows at the top of the map, and "broken" if it is. Ribbons are kept between battles.

#### Trust

Each officer's trust in you grows as you fight together, and stays with you between battles and tours. It is shown in the Crew tab.

| Level | From | What it changes |
|---|---|---|
| Green | 0 | |
| Steady | 10 | their proposals wait a little longer for your answer |
| Trusted | 30 | they may propose while you're typing (a chip, `Ctrl+Y`) |
| Veteran | 70 | an urgent proposal you leave unanswered (evasive, shields up) they carry out themselves |

An officer earns 2 for each proposal you make so, 2 for each battle won at their post (3 if you'd handed them the station), and 4 for standing out in the debrief. Belaying a proposal costs nothing: you decide.

See also: [Bridge officers](#topic-crew), [The bridge](#topic-bridge), [After the battle](#topic-after-battle).

<a id="topic-missions"></a>

### Missions

*Battles with a goal beyond holding the field: rescue a crippled ship's people, get a convoy through, stop a runner.*

Some battles carry a mission. The battle still ends the old way, when one side holds the field; the mission is a second question it answers, and Starfleet's assessment judges both. The mission card at the top right of the map shows the goal and how it stands, and the ship it is about is marked on the map.

#### Rescue

A ship of ours is crippled and drifting, with people aboard and her reactor failing (the card counts down the cycles). To take them off, bring a ship of ours within transporter range (3,000) and **lower the shield facing her**: transporters cannot beam through a raised shield. A Dreadnought's eight transporter rooms take about ten people a cycle. The people you rescue ride in the ship that took them off, and if she is lost they are lost with her. When the enemy is beaten, whoever is still aboard is taken off after the battle.

That makes a rescue the mind against the sword: you must turn a lowered face to the stricken ship and an armoured face to the enemy, or have a wingman screen you. One enemy ship (the hunter) goes for her from the start. Saving three in four counts as a success; saving everyone under fire can earn the **Karagite Order of Heroism**.

    lower 5                  (the shield facing her, by number)
    reenforce 2              (the shield facing the enemy)

#### Escort

A freighter or tanker sails for a point at her own speed, and she cannot fight. Hunters go for her. Get her there and she goes to warp; if she is destroyed or taken, the mission fails. Close up on her before the hunters do, and kill or disable them first.

#### Intercept

One enemy ship, the runner, makes for the edge of the sector with her report. She must not escape: destroy her, cripple her drives so she can't move, or make her surrender. She still fires when she can, and her friends will try to buy her the time.

She carries the news, not a fight: laden and nursing her drives, she makes only part of your best warp (`runner_pace`, 0.6 by default). She is already out on the flank when the battle starts, and her friends stand between you and her. A stern chase gives her the lead she started with; a course that leads her meets her. Spock works one out in the counsel ("Cut her off"), and Worf locks on once she is in reach, not before, so your weapons stay on the ships that are.

    counsel disable the runner's engines
    helm <intercept course> warp 9.5
    pursue <runner> warp 9.5

#### Wards don't hold the field

The ship you protect is not a fighting ship: she doesn't keep a battle going, can't escape by distance, and isn't counted among a tour stop's friends.

#### Failing a mission

A failed mission doesn't end a tour. It shows in Starfleet's assessment, in the log, and in what happens later: on the Border Patrol, a frigate whose report gets through brings one more Klingon to Starbase 12, and the Aldren's survivors and the Tamar Kessel's cargo are only yours if you save them.

#### Writing your own

A tour stop or a preset can carry a mission (see [Tours of duty](#topic-tour)):

    [tour.stop.mission]
    kind = "rescue"            # or "escort" (with to = [x, y]) or "intercept" (with runner, heading, runner_pace)
    ward = "federation.de"
    ward_name = "Aldren"
    at = [-1500, -3500]
    people = 120
    deadline = 200
    hunters = 1
    flag = "survey-team-saved" # set on the tour when it succeeds
    calls = 1                  # Starfleet reinforcement calls earned
    resupply = 0.5             # torpedoes restored to the squadron

Patrols include three mission situations: a distress call, a convoy and a runner.

See also: [Counsel from the bridge](#topic-counsel), [Transporters and boarding](#topic-transport), [After the battle](#topic-after-battle), [Tours of duty](#topic-tour), [Patrols](#topic-patrol), [Battles and campaigns](#topic-campaigns).

<a id="topic-tour"></a>

### Tours of duty

*Linked battles with a squadron you choose: damage, crews, torpedoes and prizes carry from one stop to the next.*

A tour of duty is a patrol of several stops, each one a battle. Open one from the main menu (**Tour of duty**, or **T**).

Your squadron carries everything that matters from one fight to the next: hull and system damage, casualties, torpedoes and probes fired, morale, and the ships you take as prizes. Shields, batteries, heat and positions start fresh each time. A ship that is destroyed, abandoned, surrendered or boarded is gone for the rest of the tour. If the flagship is lost, the tour is over; at a starbase, so is losing the starbase. Against the Borg, if their drones take the flagship, the tour ends there.

#### The squadron

Before the tour you choose the escorts that sail with the flagship. Each class costs its mass from the tour's fleet budget, so one heavy cruiser costs about as much as two destroyers and an interceptor. The flagship herself, the Enterprise, is a Dreadnought and costs nothing.

#### The Ready Room

Between stops you are in the Ready Room, over the patrol chart.

- **The briefing.** The officer who knows the threat best tells you what to expect, and what the enemy has learned about you so far. Fight with aimed fire and boarding parties and their captains grow wary; run your magazines low and they close in.
- **Your officers' view.** Worf, Spock, La Forge and Seven each give two sentences on the next stop: the force to beat and where to strike, how that navy likes to fight and the geometry of any mission, how the squadron will arrive and whether a refit or a call to Starfleet is worth it, and what the sensors can and can't tell us yet. See [Counsel from the bridge](#topic-counsel).
- **Your decision.** Some stops ask you to choose, for example whether to put in for a refit. A refit makes every ship good, but the enemy uses the time too.
- **The squadron.** Each ship as Geordi expects her to arrive. On the way, crews repair systems and patch hulls (to 75% at most; a starbase does the rest), and a supply ship tops up the magazines. **Keep at base** leaves a ship behind to be refitted; she misses the next fight.
- **Request reinforcements.** Starfleet sends a ship. Called from the Ready Room, she meets you at the stop, or partway into the fight if the trip is short. Each tour allows only a few calls.

#### In battle

| Command | What it does |
|---|---|
| `request reinforcements` | ask Starfleet for a ship (`reinforcements` works too). The map shows her ETA; she drops out of warp behind your starbase or your ship, away from the enemy |

Starbase battles come in **waves**: when you beat one, the next drops out of warp after a lull. Use the lull to dock damaged ships ([Docking](#topic-dock)). The battle is not over while more attackers are coming.

A reinforcement and any prize you take join your squadron for the rest of the tour.

#### The captain's log

After each stop your officers write up their stations, each captain in the squadron reports on their own ship, and the captain's entry is drafted for you. Click it to rewrite it: your words are kept as written. With a language model configured ([Officers and language models](#topic-llm)), the officers rewrite their entries in their own voices while you read.

The log is also kept as Markdown in `config/tours/<tour>-log.md`. Edit the captain's entries there between sessions and the game reads them back. At the end of the tour you get a rating: stops won, kills and prizes, ships lost and crews brought home.

#### Your own tours

Write your own in `config/tours/<anything>.toml`, in the same format as the shipped ones (`src/begin/content/data/tours.toml`): the stops, their briefings, the enemies, any choices and waves. A tour with the same id as a shipped one replaces it.

#### The Collective

The Borg tour plays by a few rules of its own. The hive remembers your weapons from one stop to the next: most of what it learned of your phasers and torpedoes it still knows, so remodulate early. Seven, in turn, reads them faster each time. Before the third stop you decide whether to keep the Treaty of Algeron or let Spock and Geordi fit the cloak they built from Romulan salvage. With the cloak, you can fire from under it ([Cloaking device](#topic-cloak)), but every time you call for reinforcements, Starfleet asks why the flagship is cloaked. The question goes in the log.

See also: [After the battle](#topic-after-battle), [Bridge officers](#topic-crew), [Docking](#topic-dock), [Fleet and groups](#topic-fleet).

<a id="topic-patrol"></a>

### Patrols

*A random mission each time: an ambush, a wolf pack, a second wave, an escort or a flagship and her screen.*

A patrol is a single battle, made up fresh each time you start one from the main menu (**Patrol**, or **P**). Every patrol is one of five situations, against an enemy picked at random, and the briefing at battle stations tells you which:

- **Ambush**: two groups waiting either side of the patrol lane. Turn to face one and the other is on your stern.
- **Wolf pack**: many light ships, fast and spread out. Thin them out before they swarm you.
- **Second wave**: a patrol, and more on the way. The second group drops out of warp when the first is beaten, or soon anyway.
- **Escort**: you have wingmen this time, and the enemy has brought more to match. Direct them with `tell <ship> attack <target>`.
- **Flagship**: an enemy heavy and her escorts. The heavy is the prize, and her screen makes you pay for going straight at her.

The enemy is sized against your flagship, so a patrol is a fair fight, not an easy one: an AI captain flying the Enterprise wins about seven in ten. Romulans, with their cloaks and plasma, are the hardest.

Each patrol has a number (shown in its title). The same number always gives the same patrol: `begin --patrol 1234` starts it again. The side you command is the one set by **Quick battle side** on the main menu.

See also: [Tours of duty](#topic-tour), [Fleet and groups](#topic-fleet), [Tactics](#topic-tactics).

<a id="topic-display"></a>

### Display and sharpness

*How the game is drawn: sharp on Retina and 4K screens through the graphics card, with weapon light that falls on nearby hulls and a soft glow round it.*

Open **Settings** from the main menu and choose **Display** (or press **D** on the main menu) to see how the game is being drawn and to change it.

**Renderer** has three choices:

- **Automatic** (the default) uses the graphics card when it can. On a high-density screen, such as a Mac's Retina display, a 4K monitor or Windows set to 150% or 200%, the game is then drawn at the screen's real pixel density, so text, hulls and beams are crisp rather than stretched. If OpenGL 3.3 isn't available, or OpenGL would be drawn on the processor (as in a virtual machine), it uses pygame's own drawing instead.
- **Graphics card** always uses OpenGL, even where that is slow.
- **Software** is pygame's own drawing at one pixel per point, as the game always drew. It works everywhere and is softer on high-density screens.

A window can't change renderer while it is open, so after you pick a different one the page offers **Restart now**. Or the change simply applies the next time you start the game.

**Light and glow** makes weapon fire feel physical. A phaser hit, a launch or a torpedo blast briefly lights the hulls next to it in its own colour, and panels and cards cast a soft shadow so they sit above the map. With the graphics card drawing, phaser beams, disruptor bolts and blasts also get a soft halo, and the very edge of the map is slightly darker, like a viewscreen. Text is never touched. It takes effect at once; turn it off for the flattest, quickest picture.

The **Now** box says what is drawing at the moment: the graphics card and the screen's density, or software drawing and why the graphics card isn't being used.

The choices are saved as `renderer` and `bloom` in `settings.json` in your config folder. `begin --renderer software` (or `gpu`, or `auto`) overrides them for one run.

See also: [Who fired what](#topic-weapon-colors), [Sound](#topic-sound).

<a id="topic-borg"></a>

### Fighting the Borg

*The Borg learn your weapons, take your crew and regrow their hulls. Learn them first, open the way, then strike hard.*

The Borg don't fight the way captains do. They don't retreat, bargain or surrender. Every weapon that hurts them teaches them, every drone that comes aboard is trying to make your crew into more drones, and their hulls grow back. **Trading shots loses.** What wins is guile first and then power: learn the ship, find the opening, then land everything at once.

#### They adapt

Each hit teaches the hive about the weapon that landed it. Soon your phasers barely scratch them and your torpedoes lose their bite. A scan shows how far they have got (the **ADAPTED** gauges), and your officers call it out.

```text
remodulate
seven, take the phasers
duty phasers
```

- `remodulate` puts your phasers on a new frequency, which the hive must learn from nothing. The banks lose their charge while they change over. Each new frequency is learned faster than the last, and least of all when Seven picks it.
- `duty phasers` has your science officer remodulate for you before the hive catches up.
- Hold your fire and mass it. Potshots teach them for free, but a full volley lands before they can answer.

#### Seven's work

Seven of Nine knows the Collective from the inside. Give her one duty at a time:

```text
tune shields
duty harmonics
duty off
```

- **Shields** (`tune shields`): she tunes your shield harmonics against their cutting beams. Tuned past halfway, their transporters can't lock on, so no drones come aboard. In time they shift frequency and she has to start again.
- **Harmonics** (`duty harmonics`): she keeps scanning their ships. Halfway through the survey she finds the ship's **vinculum relay**. When it is complete she has the ship's **shield harmonics**, and `design harmonic` builds torpedoes that pass straight through her shields. When Seven runs the science station on her own, she takes this duty herself and reports her progress. The gauge in the Borg panel shows how far she has got.
- If Seven is away or hurt, Spock takes the science station and the duties, a little more slowly.

#### The weak point

Every Borg ship routes its vinculum relay through some unremarkable system: a battery, a transporter, a probe launcher. Once your scans have found it, aim at it: `target cube relay` (or "Worf, target their relay"). Destroy it and **every drone aboard goes dormant**. The ship goes dark: no shields, no weapons, no helm, and no healing.

While she sleeps:

- Hit her warp drives or reactors and she goes up in a chain reaction. Stand well clear.
- Or send an [Away teams and the shuttle](#topic-away-team) across by transporter: plant charges, wreck her weapons, or bring a drone home.

When the drones wake, they reroute the relay and you have to find it again.

#### Drones aboard

Drones beam through any shield that isn't tuned against them. Once aboard, every crewman they overpower becomes another drone, and once enough of them are settled in they take your systems one at a time.

```text
repel security
repel seal
```

- `repel security` sends security teams to the decks they hold, so the drones win fewer fights for a while.
- `repel seal` seals and vents their sections. Most of the drones die, and a few of your own crew with them.
- The Doctor's **inoculation** (`design inoculate`) protects your crew from assimilation. Spock's **encryption** (`design encrypt`) keeps the drones out of your systems. Seven can **sever** the drones aboard from the hive (`design sever`).
- When the last drone is gone, any system they took comes back to you, damaged.

#### Power through the opening

Power alone loses. A cube's shields drink a whole salvo, her drones mend whatever gets through, and her hull grows back. But power is how a cube dies, **once guile has opened the way**.

An opening is any way through her shields:

- **Her harmonics.** Stolen by an [Away teams and the shuttle](#topic-away-team), they let every weapon you fire pass straight through for a few hits. Cracked by Seven's survey, they let your harmonic torpedoes through.
- **A dead facing.** A shield that is down, or a shield generator already destroyed.

Aimed fire that reaches her hull through an opening is a **strike**. Your gunners can see exactly what they are hitting, so the system they aim at is wrecked rather than scratched. While her shields are open the target panel says so, and Worf tells you each system he takes out.

```text
target cube propulsion
fire all torpedoes
fire all phasers
```

Choose what to wreck:

- **Her shields** (`target cube shields`). Destroyed generators are holes that stay open. Later salvos through them are strikes too, long after the harmonics are spent.
- **Her warp drives** (`target cube propulsion`). She can't run or chase. Each drive or reactor wrecked this way may set off her core, however whole her hull: stand clear.
- **Her crew decks** (`target cube crew`). Every salvo kills thousands of drones, and a ship with fewer drones repairs, regrows and boards more slowly.

The drones take a long time to mend what a strike wrecked, so make the salvo count. Aim every bank and tube at one system, and time the torpedoes so they land with the phasers.

**Then cloak.** The Enterprise's refit cloak lets her fire and vanish again. A cube can't beam drones to a ship she can't see, and her beams can't lock on it, so all she can shoot at is the flash where you were. Strike, cloak, move, and strike again through the holes you made.

A good order of battle:

1. Keep the range open and let Seven survey the cube. Tune your shields before the drones come.
2. Find the relay. Put her to sleep, and send Worf across to steal her harmonics.
3. When she wakes, put one full salvo through the harmonics into her shields, and the next into her drives.
4. Cloak, and finish her through the holes.

#### Talking to them

`hail cube` gets an answer from the Collective, not from a captain. They never accept terms, and they never break. Their silence is not anger; there is simply nothing over there to persuade.

Three presets teach the Borg in order: **First Contact: a Borg Probe**, **The Sphere** and **Wolf at the Door: the Cube**. The tour **The Collective** strings them into a campaign ([Tours of duty](#topic-tour)).

See also: [Away teams and the shuttle](#topic-away-team), [Scan](#topic-scan), [Bridge officers](#topic-crew), [Tactics](#topic-tactics), [Transporters and boarding](#topic-transport), [Tours of duty](#topic-tour), [Cloaking device](#topic-cloak).

<a id="topic-writing-help"></a>

### Writing help pages

*The Markdown format the manual uses, for editing or adding pages.*

Each page is a `.md` file. It starts with a short header between `---` lines:

```
---
title: Torpedoes
category: Weapons
order: 2
aliases: tor, torp, torpedo, torpedoes
summary: One line shown under the title and in search results.
see: fire, lock, loading
---
```

- **category** groups pages in the sidebar. The built-in groups are Getting started, Captain's manual (the chapters of the book), Coach, Helm, Weapons, Defense, Sensors and status, Ship systems, Allies and Game.
- **aliases** are the words `help <word>` matches. Add a command's name here, and `help <command>` and its short forms will find the page.
- **see** adds "See also" links at the bottom of the page.

#### Formatting

| You write | You get |
|---|---|
| `# Heading`, `## Section`, `### Sub-section` | headings |
| `**bold**`, `*italic*`, `` `code` `` | inline styles |
| `- item` / `1. item` | lists |
| `[Torpedoes](#topic-torpedoes)` or `[the torpedo page](#topic-torpedoes)` | a link to another page |
| `> **Tip** text` | a callout (Tip, Coach, Note, Warning, Example) |
| a table with `|` columns | a table |

A code block fenced with ```` ```console ```` holds example commands. Each line becomes clickable and is put in the console when clicked.

#### Live blocks

These placeholders are replaced with up-to-date tables and advice built from the game data:

| Placeholder | Shows |
|---|---|
| `> **Coach** You're not in a battle yet, so here is the training run. Once a battle starts, this space reads your fight instead: your target's range against your weapons' envelopes, the best torpedo and proximity setting, your shields, heat and power, with the command for each step.

##### Before you start
Every battle begins **paused**. Nothing moves until you press **Space**, so read the board first. **Enter** opens the console, **H** this manual and **F1** the controls. See [Your first battle](#topic-first-battle) for the full walkthrough.

##### 1. Find and target the enemy
Enemy ships are red. **Tab** targets the nearest, and the Target panel shows its class and range. In the console, the first few letters of a ship's name are enough (here, a Klingon called Gorkon):
```text
target gor
```

##### 2. Close the range
**W** and **S** change warp, and a right-click on the map sets your course. Or let the helm chase them:
```text
pursue gor warp 4
```

##### 3. Torpedoes at long range
Torpedoes reach far beyond phasers but need room to arm. When the coach says the shot is on, press **T**.
```text
fire all torpedoes
```

##### 4. Phasers up close
Inside phaser range press **F**. Phasers hit far harder the closer you are. See [Phasers](#topic-phasers).
```text
fire all phasers
```

##### 5. Keep a strong shield toward them
Six shields each cover 60°. When the one facing the enemy weakens, turn to bring a fresh one round. See [Shields](#topic-shields).

##### 6. Mind the engines and the power
Above cruise warp the drives heat up, and past the limit they take damage. For a long run, ask Geordi for all she's got and a team keeps them cooler for a while (see [Engine boost](#topic-boost)). Firing and shields drain the batteries.

##### 7. Dodge, and fan your shots
A Federation helm can jink out of the way of incoming torpedoes and then carry on with your course. Against a fast target, fan the salvo so a turn doesn't take it clear of every round. See [Course and speed](#topic-helm) and [Torpedoes](#topic-torpedoes).
```text
evasive
fire all torpedoes spread 10
```

##### 8. Let the crew help
Hand a station to its officer, or the whole bridge. Geordi La Forge can run the repairs, and a word from you lifts a shaken crew. See [Bridge officers](#topic-crew), [Repair](#topic-repair) and [Crew morale](#topic-morale).
```text
delegate tactical
geordi, manage repairs
address crew Steady. We have the better ship.
```

##### 9. Plan ahead
Write a named order before the fight in `config/orders.toml` and run it with one word. See [Named tactical orders](#topic-orders).
```text
orders
execute order beta-1
```

##### In the battle
Type `coach` or press **H** and pick **Coach**: this page then reads your actual fight and lists the most urgent thing first. Your officers help too. Try `spock, what do you advise?` (see [Talking to your officers](#topic-talking)).` | advice for the current battle |
| `> **Note** Start a battle to see the weapons of the ship you command.` | the weapons of the ship you command |
| `| Torpedo | Id | Warp | Warhead | Arms at | Reach | Max prox | Guidance | Reload | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Romulan Plasma Torpedo | `plasma` | 15 | 30 plasma (fades with distance) | 1,500 | 19,500 | 750 | homing | 6 c | Romulan Bird of Prey, Romulan War Eagle |
| Federation Mark 8 | `mk8` | 15 | 21.6 antimatter | 1,425 | 10,425 | 800 | straight | 4 c | - |
| Plasma X Torpedo | `xplasma` | 21 | 18 plasma (fades with distance) | 2,100 | 25,200 | 500 | homing | 5 c | Romulan Frigate |
| Borg torpedo | `bgt` | 24 | 18 antimatter | 1,440 | 18,240 | 600 | straight | 4 c | Borg Cube, Borg Probe, Borg Sphere |
| Federation Mark 7 | `mk7` | 30 | 14.4 antimatter | 1,200 | 19,200 | 800 | straight | 3 c | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon TX torpedo | `ktx` | 27 | 10 antimatter | 2,700 | 18,900 | 500 | straight | 3 c | Klingon Battle Cruiser, Klingon Dreadnought, Klingon Escort, Klingon Frigate |
| Orion Bullet Torpedo | `opbt` | 20 | 8 antimatter | 2,000 | 12,000 | 400 | straight | 3 c | Orion Anarchist, Orion Armadillo, Orion Saboteur |
| Orion Shield Auger | `oshb` | 20 | 8 shield-bore | 2,000 | 12,000 | 400 | straight | 5 c | - |` | every torpedo type compared |
| `| Probe | Id | Warp | Warhead | Arms after | Time fuse | Reach | Max prox | Sensor | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Dreadnought Killer (dink) | `dnk` | 3.5 | 30 | 5 c | 12 c | 4,200 | 1,500 | 0 | Klingon Dreadnought, Klingon Frigate |
| Romulan Pak Probe | `rmpp` | 2 | 28 | 6 c | 20 c | 4,000 | 1,000 | 0 | Romulan Bird of Prey, Romulan Frigate |
| Federation Probe X-2 | `px2` | 2.5 | 25 | 5 c | 20 c | 5,000 | 1,200 | 0 | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon Light Pak Probe | `klpp` | 2 | 20 | 6 c | 20 c | 4,000 | 1,000 | 0 | Klingon Battle Cruiser, Klingon Escort, Orion Anarchist, Orion Armadillo |
| Klingon Data Probe | `kdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Romulan version of Klingon Data Probe | `rdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Federation Probe Data-2 | `pxd2` | 20.5 | 0 | 1 c | 30 c | 61,500 | 1,200 | 20,000 | - |` | every probe type compared |
| `Damage per bank for a Dreadnought (charge 10, range 2,000) before shields:

| Range | Spread 10 | Spread 20 | Spread 45 |
|---|---|---|---|
| 0 | 22 | 11 | 5 |
| 500 | 19 | 10 | 4 |
| 1,000 | 16 | 8 | 4 |
| 1,500 | 11 | 6 | 2 |
| 1,800 | 7 | 4 | 2 |` | phaser damage by range and spread |
| `| Ship | Nation | Max warp | Phasers (range) | Tubes | Probes | Shields | Crew |
|---|---|---|---|---|---|---|---|
| Probe (`PR`) | Borg | 9 | 3 (2,400) | 2 × bgt | 0 × - | 6 × 150 | 260 |
| Sphere (`SP`) | Borg | 9 | 6 (2,600) | 4 × bgt | 0 × - | 6 × 240 | 1400 |
| Cube (`CU`) | Borg | 7 | 12 (2,900) | 6 × bgt | 0 × - | 6 × 420 | 9000 |
| Shuttlecraft (`SH`) | Federation | 5 | 0 (0) | 0 × mk7 | 0 × px2 | 6 × 25 | 8 |
| Tug (`TG`) | Federation | 4 | 0 (2,000) | 0 × - | 0 × - | 0 × 50 | 25 |
| Interceptor (`IN`) | Federation | 12 | 6 (2,000) | 1 × mk7 | 1 × px2 | 6 × 150 | 105 |
| Destroyer (`DE`) | Federation | 10 | 4 (2,000) | 4 × mk7 | 2 × px2 | 6 × 200 | 200 |
| Heavy Cruiser (`HC`) | Federation | 9 | 4 (2,000) | 6 × mk7 | 3 × px2 | 6 × 225 | 450 |
| Dreadnought (`DN`) | Federation | 9.5 | 6 (2,000) | 8 × mk7 | 4 × px2 | 6 × 250 | 500 |
| Dreadnought (cloak refit) (`DN`) | Federation | 9.5 | 6 (2,000) | 8 × mk7 | 4 × px2 | 6 × 250 | 500 |
| Tanker (`TN`) | Federation | 4 | 0 (2,000) | 0 × - | 0 × - | 6 × 50 | 20 |
| Starbase (`SB`) | Federation | 0 | 8 (2,000) | 0 × - | 0 × - | 6 × 950 | 12000 |
| Escort (`ES`) | Klingon | 11 | 4 (2,200) | 1 × ktx | 1 × klpp | 6 × 100 | 95 |
| Frigate (`FR`) | Klingon | 10.5 | 5 (2,200) | 2 × ktx | 2 × dnk | 6 × 175 | 175 |
| Battle Cruiser (`BC`) | Klingon | 10 | 5 (2,200) | 5 × ktx | 2 × klpp | 6 × 200 | 350 |
| Dreadnought (`DR`) | Klingon | 9 | 6 (2,200) | 8 × ktx | 4 × dnk | 6 × 225 | 500 |
| Outpost (`OP`) | Klingon | 0 | 8 (2,200) | 0 × - | 0 × - | 6 × 925 | 6000 |
| Assassin (`AS`) | Orion | 14 | 3 (1,800) | 0 × - | 0 × - | 6 × 100 | 45 |
| Raider (`RA`) | Orion | 12 | 5 (1,800) | 0 × - | 0 × - | 6 × 125 | 95 |
| Saboteur (`SA`) | Orion | 10 | 5 (2,000) | 1 × opbt | 0 × - | 6 × 175 | 110 |
| Anarchist (`AN`) | Orion | 10 | 5 (2,000) | 3 × opbt | 1 × klpp | 6 × 180 | 145 |
| Armadillo (`AR`) | Orion | 8 | 2 (2,000) | 2 × opbt | 1 × klpp | 0 × 180 | 45 |
| War Eagle (`WE`) | Romulan | 3.5 | 5 (2,500) | 1 × plasma | 0 × - | 6 × 400 | 115 |
| Frigate (`FR`) | Romulan | 8.25 | 4 (2,200) | 2 × xplasma | 2 × rmpp | 6 × 300 | 160 |
| Bird of Prey (`BP`) | Romulan | 6 | 3 (2,500) | 2 × plasma | 2 × rmpp | 6 × 325 | 275 |` | every ship class |
| `| Officer | Station | How they come across |
|---|---|---|
| **Commander Spock** | Helm; takes science for Seven of Nine when needed | precise and emphatic, dry wit, unflappable |
| **Lieutenant Worf** | Tactical | honour-bound, blunt, impatient for battle, fiercely loyal |
| **Lieutenant Commander La Forge** | Engineering | upbeat, technically fluent, born problem-solver, calm under pressure |
| **Seven of Nine** | Science | highly effective, efficient, coolly confident, ex-Borg precision |
| **Lieutenant Sulu** | Stands by; takes tactical for Worf when needed | unflappable, quietly confident, a duellist's patience |
| **Ensign Chekov** | Stands by; takes helm for Spock when needed | eager, quick, proud of where he comes from, young and brave |
| **The Doctor** | Sickbay | acerbic, brilliant, put-upon, secretly devoted to his patients |` | the bridge officers, their stations and traits |
| `### United Federation of Planets

- **Ships:** Tug, Interceptor, Destroyer, Heavy Cruiser, Dreadnought, Tanker, Starbase.
- **Torpedoes:** Federation Mark 7, Federation Mark 8. **Probes:** Federation Probe X-2, Federation Probe Data-2.
- **How they fight:** they lean on their torpedoes; their helms are drilled in evasive manoeuvres.
- **Terms:** watching their allies battered makes them wary; at the start they are stubborn, and they rarely strike their colours. Crew spirits start at 80.

##### Klingon Empire

- **Ships:** Escort, Frigate, Battle Cruiser, Dreadnought, Outpost.
- **Torpedoes:** Klingon TX torpedo. **Probes:** Klingon Light Pak Probe, Dreadnought Killer (dink), Klingon Data Probe.
- **How they fight:** they lean on their phasers; many of their captains favour the charge: a point-blank run at full speed, an alpha strike, a break to recharge, and again.
- **Terms:** watching their allies battered makes them angry; at the start they are stubborn, and they almost never strike their colours. Crew spirits start at 85.

##### Romulan Star Empire

- **Ships:** War Eagle, Frigate, Bird of Prey.
- **Torpedoes:** Romulan Plasma Torpedo, Plasma X Torpedo. **Probes:** Romulan Pak Probe, Romulan version of Klingon Data Probe.
- **How they fight:** they lean on their torpedoes; many of their captains favour the feint: they turn and run when you close (cloaking if they can), then turn on the pursuer with a full spread; they cloak to close and to reposition.
- **Terms:** watching their allies battered makes them wary; at the start they are very stubborn, and they almost never strike their colours. Crew spirits start at 75.

##### Orion Pirate Guild

- **Ships:** Assassin, Raider, Saboteur, Anarchist, Armadillo.
- **Torpedoes:** Orion Bullet Torpedo, Orion Shield Auger. **Probes:** Klingon Light Pak Probe.
- **How they fight:** they lean on their phasers; many of their captains favour the raid: in, one volley, and out of reach before you can answer.
- **Terms:** watching their allies battered makes them frightened; at the start they are easily talked round, and they readily strike their colours. Crew spirits start at 60.

##### The Borg Collective

- **Ships:** Probe, Sphere, Cube.
- **Torpedoes:** Borg torpedo. **Probes:** none.
- **How they fight:** they lean on their phasers.
- **Terms:** none. The Collective never bargains, never retreats and never surrenders.` | every power: ships, weapons, how they fight, how they take a hail |
| `| Project | Built by | Ask for it with |
|---|---|---|
| Plasma-seeker torpedo | Seven of Nine and Spock | `design seeker` |
| Harmonic torpedoes | Seven of Nine, Worf, Spock and Sulu | `design harmonic` |
| Counter-nanoprobe inoculation | The Doctor and Seven of Nine | `design inoculate` |
| Computer lockout | La Forge, Seven of Nine and Spock | `design encrypt` |
| Link to the hive cut | Seven of Nine, Spock and La Forge | `design sever` |
| Deflector tachyon pulse | Spock and Seven of Nine | `design deflector` |
| Tachyon detector torpedo | Spock and Seven of Nine | `design tachyon` |` | the projects officers build together |
| `- **Border Incident.** The Enterprise meets four Klingon battle cruisers probing the Neutral Zone. Begin's classic duel, grown to face a Dreadnought.
- **Romulan Ambush.** The Enterprise and a destroyer escort answer a distress call. Three Birds of Prey and a frigate wait under cloak. Watch for plasma.
- **Pirate Hunt.** Run down an Orion raiding party before it scatters. Orions are fast, brittle and unpredictable.
- **Dreadnought Duel.** Two Klingon dreadnoughts, two battle cruisers and a frigate against yours. Manage your shields and your power budget.
- **Outpost Assault.** Break a Klingon outpost's defensive screen. The outpost cannot move but carries eight phaser banks.
- **Fleet Action.** Seven ships against ten. Your wingmen fight on their own; use 'tell <ship> attack <target>' to direct them.
- **Three-Way Standoff.** Federation, Klingon and Romulan ships meet over a disputed system. Everyone is hostile to everyone.
- **Starbase Defense.** Hold the line at the starbase against three Klingon waves: frigates, then three battle cruisers, then two dreadnoughts with their escort. Between waves, damaged ships can dock to repair (2.0 rules).
- **First Contact: a Borg Probe.** A lone Borg probe is surveying the sector. Small, but it learns: watch its adaptation, remodulate, and let Seven scan it.
- **The Sphere.** A Borg sphere and its probe. Tune the shields before the drones come, find the vinculum relay, and put her to sleep.
- **Wolf at the Door: the Cube.** A cube, with a task force to stop it. Power alone will cost you dearly: survey her, send Worf across, and strike while she sleeps.`, `- **Border Patrol** (The Archanis sector). Patrol the Klingon border, deal with whatever you find, and fall back to Starbase 12 when the Klingons move on it. Six stops, about an hour. *Stops:* Orion raiders → A Klingon on the border → Frigates at Kessik → Romulan ambush → The scouting dreadnought → Starbase Defense.
- **Neutral Zone Watch** (The Romulan Neutral Zone). Four stops along the Neutral Zone. The Romulans cloak, strike and vanish; Starbase 47 is the line they must not cross. About forty minutes. *Stops:* Silence at Outpost 4 → Frigate screen → The Bird of Prey → The line at Starbase 47.
- **The Orion Run** (The Orion trade routes). A short hunt for an Orion raiding band: three stops, about twenty minutes. A good first tour. *Stops:* Raid on a convoy → Saboteurs → The Armadillo.
- **The Collective** (Beyond the Federation's edge). Something is taking whole colonies along the frontier and leaving nothing behind. Find it, learn it, and stop it before it reaches the core worlds. Four stops, about forty-five minutes. *Stops:* The empty colony → The sphere at the rift → The graveyard → The cube.` | the curated battles and the tours of duty |
| `| Order | Also | Explained in |
|---|---|---|
| `abort` | - | [Self-destruct and surrender](#topic-destruct) |
| `address` | `rally`, `speech` | [Crew morale](#topic-morale) |
| `aim` | - | [Targeting](#topic-targeting) |
| `alert` | `condition` | [Alert conditions](#topic-alert) |
| `ask` | `say` | [Talking to your officers](#topic-talking) |
| `assume` | `takeback` | [Bridge officers](#topic-crew) |
| `autoload` | `al` | [Loading and autoload](#topic-loading) |
| `away` | `shuttle`, `infiltrate`, `sneak` | [Away teams and the shuttle](#topic-away-team) |
| `bait` | - | [Disabling or taking out enemy ships](#topic-disable) |
| `banks` | `bank` | [Phasers](#topic-phasers) |
| `belay` | - | [Named tactical orders](#topic-orders) |
| `board` | - | [Transporters and boarding](#topic-transport) |
| `boost` | `overdrive` | [Engine boost](#topic-boost) |
| `capture` | `seize` | [Transporters and boarding](#topic-transport) |
| `cease` | `ceasefire` | [Cease fire](#topic-ceasefire) |
| `chart` | - | [Chart](#topic-chart) |
| `cloak` | `cl` | [Cloaking device](#topic-cloak) |
| `coach` | `advise`, `advice`, `hint` | [Coach](#topic-coach) |
| `computer` | `library` | [Library computer](#topic-library) |
| `conn` | - | [Giving an officer the bridge](#topic-conn) |
| `counsel` | `council`, `options` | [Counsel from the bridge](#topic-counsel) |
| `crew` | `bridge`, `officers` | [Bridge officers](#topic-crew) |
| `damage` | `dmg` | [Status displays](#topic-status) |
| `decloak` | `uncloak` | [Cloaking device](#topic-cloak) |
| `delegate` | `dg` | [Bridge officers](#topic-crew) |
| `design` | `collaborate`, `invent` | [Tachyon detector torpedo](#topic-tachyon) |
| `destroy` | `eliminate`, `annihilate` | [Disabling or taking out enemy ships](#topic-disable) |
| `destruct` | `self`, `selfdestruct`, `sd` | [Self-destruct and surrender](#topic-destruct) |
| `detonate` | `det`, `boom` | [Probes](#topic-probes) |
| `disable` | `disarm`, `cripple` | [Phasers](#topic-phasers) |
| `dock` | - | [Docking](#topic-dock) |
| `duty` | `tune`, `retune` | [Fighting the Borg](#topic-borg) |
| `elude` | `evade`, `flee` | [Pursue and elude](#topic-pursue) |
| `enable` | - | [Phasers](#topic-phasers) |
| `evasive` | `evasion`, `jink` | [Course and speed](#topic-helm) |
| `execute` | `exec` | [Named tactical orders](#topic-orders) |
| `fire` | `f`, `shoot` | [Fire](#topic-fire) |
| `fleet` | - | [Fleet and groups](#topic-fleet) |
| `fp` | - | [Fire](#topic-fire) |
| `fpr` | - | [Fire](#topic-fire) |
| `ft` | - | [Fire](#topic-fire) |
| `group` | `groups` | [Fleet and groups](#topic-fleet) |
| `hail` | `hailing`, `channel` | [Hailing enemy captains](#topic-hailing) |
| `helm` | `h`, `course`, `c` | [Course and speed](#topic-helm) |
| `help` | `?`, `man`, `manual`, `commands` | [Welcome aboard](#topic-index) |
| `hold` | `holdfire` | [Cease fire](#topic-ceasefire) |
| `hud` | `detail` | [Keyboard and mouse](#topic-controls) |
| `hunt` | `find`, `locate`, `search`, `seek` | [Cloaking device](#topic-cloak) |
| `key` | - | [Key macros](#topic-keys) |
| `launchers` | `launcher` | [Probes](#topic-probes) |
| `load` | `ld` | [Loading and autoload](#topic-loading) |
| `lock` | `lk` | [Lock and turn](#topic-lock) |
| `lower` | `drop`, `down` | [Shields](#topic-shields) |
| `mode` | `firemode`, `fm` | [Fire control and point defense](#topic-firecontrol) |
| `morale` | `spirits` | [Crew morale](#topic-morale) |
| `open` | `openfire` | [Cease fire](#topic-ceasefire) |
| `orders` | `plans` | [Ally orders](#topic-tell) |
| `pause` | `p` | [Time, pause and quitting](#topic-time) |
| `pd` | `pointdefense`, `point-defense`, `defense` | [Fire control and point defense](#topic-firecontrol) |
| `phaser` | `phasers` | [Phasers](#topic-phasers) |
| `prisoners` | `brig` | [Hailing enemy captains](#topic-hailing) |
| `probe` | `probes`, `pr` | [Probes](#topic-probes) |
| `pulse` | `deflector` | [Deflector tachyon pulse](#topic-deflector) |
| `pursue` | `chase`, `follow` | [Pursue and elude](#topic-pursue) |
| `quit` | `exit` | [Time, pause and quitting](#topic-time) |
| `raise` | `up` | [Shields](#topic-shields) |
| `range` | `display`, `rng`, `zoom`, `scale` | [Display range](#topic-range) |
| `recall` | - | [Away teams and the shuttle](#topic-away-team) |
| `record` | `rec` | [Named tactical orders](#topic-orders) |
| `reinforce` | `reenforce`, `rf` | [Shields](#topic-shields) |
| `release` | - | [Tractor beam](#topic-tractor) |
| `remodulate` | `remod`, `modulate`, `rotate` | [Fighting the Borg](#topic-borg) |
| `repair` | - | [Repair](#topic-repair) |
| `repel` | `security`, `intruders`, `seal`, `vent` | [Fighting the Borg](#topic-borg) |
| `report` | - | [Status displays](#topic-status) |
| `request` | `reinforcements`, `summon` | [Tours of duty](#topic-tour) |
| `resume` | `go`, `unpause` | [Time, pause and quitting](#topic-time) |
| `role` | - | [Phasers](#topic-phasers) |
| `scan` | `sc` | [Scan](#topic-scan) |
| `seeker` | `seekers` | [Cloaking device](#topic-cloak) |
| `shields` | `shield` | [Shields](#topic-shields) |
| `sound` | `volume`, `audio`, `mute` | [Sound](#topic-sound) |
| `spread` | `sp` | [Phasers](#topic-phasers) |
| `status` | `st` | [Status displays](#topic-status) |
| `stop` | `allstop`, `halt` | [Course and speed](#topic-helm) |
| `style` | `styles`, `ribbons` | [Command styles and trust](#topic-styles) |
| `surrender` | - | [Self-destruct and surrender](#topic-destruct) |
| `sweep` | `sniff`, `exhaust`, `plasma` | [Cloaking device](#topic-cloak) |
| `tachyon` | - | [Tachyon detector torpedo](#topic-tachyon) |
| `target` | `t`, `tgt`, `designate` | [Targeting](#topic-targeting) |
| `tell` | `order` | [Ally orders](#topic-tell) |
| `text` | - | [Key macros](#topic-keys) |
| `time` | `x` | [Time, pause and quitting](#topic-time) |
| `torp` | `torps`, `torpedo`, `torpedoes`, `torpedos` | [Torpedoes](#topic-torpedoes) |
| `tractor` | `tr` | [Tractor beam](#topic-tractor) |
| `translate` | `interpret`, `english` | [Orders in plain English](#topic-plain-english) |
| `transport` | `beam` | [Transporters and boarding](#topic-transport) |
| `tubes` | `tube` | [Torpedoes](#topic-torpedoes) |
| `turn` | `point` | [Lock and turn](#topic-lock) |
| `undock` | - | [Docking](#topic-dock) |
| `unload` | `ul` | [Loading and autoload](#topic-loading) |
| `voice` | `mic`, `microphone` | [Speaking orders](#topic-voice-orders) |
| `warp` | `w`, `speed` | [Course and speed](#topic-helm) |` | every console order and the page that explains it |

#### The book

`docs/MANUAL.md` is these pages bound into one book: the Captain's manual chapters first, then every other page by category, then the tables. It is built by `python -m begin.help.book`, and a test fails until it is rebuilt, so whenever you add or change a page, a ship, a weapon, an officer or an order, rebuild it and commit it with the change.

# Appendices

<a id="appendix-ships"></a>

## Ship classes

| Ship | Nation | Max warp | Phasers (range) | Tubes | Probes | Shields | Crew |
|---|---|---|---|---|---|---|---|
| Probe (`PR`) | Borg | 9 | 3 (2,400) | 2 × bgt | 0 × - | 6 × 150 | 260 |
| Sphere (`SP`) | Borg | 9 | 6 (2,600) | 4 × bgt | 0 × - | 6 × 240 | 1400 |
| Cube (`CU`) | Borg | 7 | 12 (2,900) | 6 × bgt | 0 × - | 6 × 420 | 9000 |
| Shuttlecraft (`SH`) | Federation | 5 | 0 (0) | 0 × mk7 | 0 × px2 | 6 × 25 | 8 |
| Tug (`TG`) | Federation | 4 | 0 (2,000) | 0 × - | 0 × - | 0 × 50 | 25 |
| Interceptor (`IN`) | Federation | 12 | 6 (2,000) | 1 × mk7 | 1 × px2 | 6 × 150 | 105 |
| Destroyer (`DE`) | Federation | 10 | 4 (2,000) | 4 × mk7 | 2 × px2 | 6 × 200 | 200 |
| Heavy Cruiser (`HC`) | Federation | 9 | 4 (2,000) | 6 × mk7 | 3 × px2 | 6 × 225 | 450 |
| Dreadnought (`DN`) | Federation | 9.5 | 6 (2,000) | 8 × mk7 | 4 × px2 | 6 × 250 | 500 |
| Dreadnought (cloak refit) (`DN`) | Federation | 9.5 | 6 (2,000) | 8 × mk7 | 4 × px2 | 6 × 250 | 500 |
| Tanker (`TN`) | Federation | 4 | 0 (2,000) | 0 × - | 0 × - | 6 × 50 | 20 |
| Starbase (`SB`) | Federation | 0 | 8 (2,000) | 0 × - | 0 × - | 6 × 950 | 12000 |
| Escort (`ES`) | Klingon | 11 | 4 (2,200) | 1 × ktx | 1 × klpp | 6 × 100 | 95 |
| Frigate (`FR`) | Klingon | 10.5 | 5 (2,200) | 2 × ktx | 2 × dnk | 6 × 175 | 175 |
| Battle Cruiser (`BC`) | Klingon | 10 | 5 (2,200) | 5 × ktx | 2 × klpp | 6 × 200 | 350 |
| Dreadnought (`DR`) | Klingon | 9 | 6 (2,200) | 8 × ktx | 4 × dnk | 6 × 225 | 500 |
| Outpost (`OP`) | Klingon | 0 | 8 (2,200) | 0 × - | 0 × - | 6 × 925 | 6000 |
| Assassin (`AS`) | Orion | 14 | 3 (1,800) | 0 × - | 0 × - | 6 × 100 | 45 |
| Raider (`RA`) | Orion | 12 | 5 (1,800) | 0 × - | 0 × - | 6 × 125 | 95 |
| Saboteur (`SA`) | Orion | 10 | 5 (2,000) | 1 × opbt | 0 × - | 6 × 175 | 110 |
| Anarchist (`AN`) | Orion | 10 | 5 (2,000) | 3 × opbt | 1 × klpp | 6 × 180 | 145 |
| Armadillo (`AR`) | Orion | 8 | 2 (2,000) | 2 × opbt | 1 × klpp | 0 × 180 | 45 |
| War Eagle (`WE`) | Romulan | 3.5 | 5 (2,500) | 1 × plasma | 0 × - | 6 × 400 | 115 |
| Frigate (`FR`) | Romulan | 8.25 | 4 (2,200) | 2 × xplasma | 2 × rmpp | 6 × 300 | 160 |
| Bird of Prey (`BP`) | Romulan | 6 | 3 (2,500) | 2 × plasma | 2 × rmpp | 6 × 325 | 275 |

<a id="appendix-torpedoes"></a>

## Torpedoes

| Torpedo | Id | Warp | Warhead | Arms at | Reach | Max prox | Guidance | Reload | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Romulan Plasma Torpedo | `plasma` | 15 | 30 plasma (fades with distance) | 1,500 | 19,500 | 750 | homing | 6 c | Romulan Bird of Prey, Romulan War Eagle |
| Federation Mark 8 | `mk8` | 15 | 21.6 antimatter | 1,425 | 10,425 | 800 | straight | 4 c | - |
| Plasma X Torpedo | `xplasma` | 21 | 18 plasma (fades with distance) | 2,100 | 25,200 | 500 | homing | 5 c | Romulan Frigate |
| Borg torpedo | `bgt` | 24 | 18 antimatter | 1,440 | 18,240 | 600 | straight | 4 c | Borg Cube, Borg Probe, Borg Sphere |
| Federation Mark 7 | `mk7` | 30 | 14.4 antimatter | 1,200 | 19,200 | 800 | straight | 3 c | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon TX torpedo | `ktx` | 27 | 10 antimatter | 2,700 | 18,900 | 500 | straight | 3 c | Klingon Battle Cruiser, Klingon Dreadnought, Klingon Escort, Klingon Frigate |
| Orion Bullet Torpedo | `opbt` | 20 | 8 antimatter | 2,000 | 12,000 | 400 | straight | 3 c | Orion Anarchist, Orion Armadillo, Orion Saboteur |
| Orion Shield Auger | `oshb` | 20 | 8 shield-bore | 2,000 | 12,000 | 400 | straight | 5 c | - |

<a id="appendix-probes"></a>

## Probes

| Probe | Id | Warp | Warhead | Arms after | Time fuse | Reach | Max prox | Sensor | Carried by |
|---|---|---|---|---|---|---|---|---|---|
| Dreadnought Killer (dink) | `dnk` | 3.5 | 30 | 5 c | 12 c | 4,200 | 1,500 | 0 | Klingon Dreadnought, Klingon Frigate |
| Romulan Pak Probe | `rmpp` | 2 | 28 | 6 c | 20 c | 4,000 | 1,000 | 0 | Romulan Bird of Prey, Romulan Frigate |
| Federation Probe X-2 | `px2` | 2.5 | 25 | 5 c | 20 c | 5,000 | 1,200 | 0 | Federation Destroyer, Federation Dreadnought, Federation Dreadnought (cloak refit), Federation Heavy Cruiser, Federation Interceptor, Federation Shuttlecraft |
| Klingon Light Pak Probe | `klpp` | 2 | 20 | 6 c | 20 c | 4,000 | 1,000 | 0 | Klingon Battle Cruiser, Klingon Escort, Orion Anarchist, Orion Armadillo |
| Klingon Data Probe | `kdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Romulan version of Klingon Data Probe | `rdat` | 20 | 10 | 6 c | 25 c | 50,000 | 1,000 | 20,000 | - |
| Federation Probe Data-2 | `pxd2` | 20.5 | 0 | 1 c | 30 c | 61,500 | 1,200 | 20,000 | - |

<a id="appendix-phaser-falloff"></a>

## Phaser damage by range

Damage per bank for a Dreadnought (charge 10, range 2,000) before shields:

| Range | Spread 10 | Spread 20 | Spread 45 |
|---|---|---|---|
| 0 | 22 | 11 | 5 |
| 500 | 19 | 10 | 4 |
| 1,000 | 16 | 8 | 4 |
| 1,500 | 11 | 6 | 2 |
| 1,800 | 7 | 4 | 2 |

<a id="appendix-orders"></a>

## Every order the console knows

| Order | Also | Explained in |
|---|---|---|
| `abort` | - | [Self-destruct and surrender](#topic-destruct) |
| `address` | `rally`, `speech` | [Crew morale](#topic-morale) |
| `aim` | - | [Targeting](#topic-targeting) |
| `alert` | `condition` | [Alert conditions](#topic-alert) |
| `ask` | `say` | [Talking to your officers](#topic-talking) |
| `assume` | `takeback` | [Bridge officers](#topic-crew) |
| `autoload` | `al` | [Loading and autoload](#topic-loading) |
| `away` | `shuttle`, `infiltrate`, `sneak` | [Away teams and the shuttle](#topic-away-team) |
| `bait` | - | [Disabling or taking out enemy ships](#topic-disable) |
| `banks` | `bank` | [Phasers](#topic-phasers) |
| `belay` | - | [Named tactical orders](#topic-orders) |
| `board` | - | [Transporters and boarding](#topic-transport) |
| `boost` | `overdrive` | [Engine boost](#topic-boost) |
| `capture` | `seize` | [Transporters and boarding](#topic-transport) |
| `cease` | `ceasefire` | [Cease fire](#topic-ceasefire) |
| `chart` | - | [Chart](#topic-chart) |
| `cloak` | `cl` | [Cloaking device](#topic-cloak) |
| `coach` | `advise`, `advice`, `hint` | [Coach](#topic-coach) |
| `computer` | `library` | [Library computer](#topic-library) |
| `conn` | - | [Giving an officer the bridge](#topic-conn) |
| `counsel` | `council`, `options` | [Counsel from the bridge](#topic-counsel) |
| `crew` | `bridge`, `officers` | [Bridge officers](#topic-crew) |
| `damage` | `dmg` | [Status displays](#topic-status) |
| `decloak` | `uncloak` | [Cloaking device](#topic-cloak) |
| `delegate` | `dg` | [Bridge officers](#topic-crew) |
| `design` | `collaborate`, `invent` | [Tachyon detector torpedo](#topic-tachyon) |
| `destroy` | `eliminate`, `annihilate` | [Disabling or taking out enemy ships](#topic-disable) |
| `destruct` | `self`, `selfdestruct`, `sd` | [Self-destruct and surrender](#topic-destruct) |
| `detonate` | `det`, `boom` | [Probes](#topic-probes) |
| `disable` | `disarm`, `cripple` | [Phasers](#topic-phasers) |
| `dock` | - | [Docking](#topic-dock) |
| `duty` | `tune`, `retune` | [Fighting the Borg](#topic-borg) |
| `elude` | `evade`, `flee` | [Pursue and elude](#topic-pursue) |
| `enable` | - | [Phasers](#topic-phasers) |
| `evasive` | `evasion`, `jink` | [Course and speed](#topic-helm) |
| `execute` | `exec` | [Named tactical orders](#topic-orders) |
| `fire` | `f`, `shoot` | [Fire](#topic-fire) |
| `fleet` | - | [Fleet and groups](#topic-fleet) |
| `fp` | - | [Fire](#topic-fire) |
| `fpr` | - | [Fire](#topic-fire) |
| `ft` | - | [Fire](#topic-fire) |
| `group` | `groups` | [Fleet and groups](#topic-fleet) |
| `hail` | `hailing`, `channel` | [Hailing enemy captains](#topic-hailing) |
| `helm` | `h`, `course`, `c` | [Course and speed](#topic-helm) |
| `help` | `?`, `man`, `manual`, `commands` | [Welcome aboard](#topic-index) |
| `hold` | `holdfire` | [Cease fire](#topic-ceasefire) |
| `hud` | `detail` | [Keyboard and mouse](#topic-controls) |
| `hunt` | `find`, `locate`, `search`, `seek` | [Cloaking device](#topic-cloak) |
| `key` | - | [Key macros](#topic-keys) |
| `launchers` | `launcher` | [Probes](#topic-probes) |
| `load` | `ld` | [Loading and autoload](#topic-loading) |
| `lock` | `lk` | [Lock and turn](#topic-lock) |
| `lower` | `drop`, `down` | [Shields](#topic-shields) |
| `mode` | `firemode`, `fm` | [Fire control and point defense](#topic-firecontrol) |
| `morale` | `spirits` | [Crew morale](#topic-morale) |
| `open` | `openfire` | [Cease fire](#topic-ceasefire) |
| `orders` | `plans` | [Ally orders](#topic-tell) |
| `pause` | `p` | [Time, pause and quitting](#topic-time) |
| `pd` | `pointdefense`, `point-defense`, `defense` | [Fire control and point defense](#topic-firecontrol) |
| `phaser` | `phasers` | [Phasers](#topic-phasers) |
| `prisoners` | `brig` | [Hailing enemy captains](#topic-hailing) |
| `probe` | `probes`, `pr` | [Probes](#topic-probes) |
| `pulse` | `deflector` | [Deflector tachyon pulse](#topic-deflector) |
| `pursue` | `chase`, `follow` | [Pursue and elude](#topic-pursue) |
| `quit` | `exit` | [Time, pause and quitting](#topic-time) |
| `raise` | `up` | [Shields](#topic-shields) |
| `range` | `display`, `rng`, `zoom`, `scale` | [Display range](#topic-range) |
| `recall` | - | [Away teams and the shuttle](#topic-away-team) |
| `record` | `rec` | [Named tactical orders](#topic-orders) |
| `reinforce` | `reenforce`, `rf` | [Shields](#topic-shields) |
| `release` | - | [Tractor beam](#topic-tractor) |
| `remodulate` | `remod`, `modulate`, `rotate` | [Fighting the Borg](#topic-borg) |
| `repair` | - | [Repair](#topic-repair) |
| `repel` | `security`, `intruders`, `seal`, `vent` | [Fighting the Borg](#topic-borg) |
| `report` | - | [Status displays](#topic-status) |
| `request` | `reinforcements`, `summon` | [Tours of duty](#topic-tour) |
| `resume` | `go`, `unpause` | [Time, pause and quitting](#topic-time) |
| `role` | - | [Phasers](#topic-phasers) |
| `scan` | `sc` | [Scan](#topic-scan) |
| `seeker` | `seekers` | [Cloaking device](#topic-cloak) |
| `shields` | `shield` | [Shields](#topic-shields) |
| `sound` | `volume`, `audio`, `mute` | [Sound](#topic-sound) |
| `spread` | `sp` | [Phasers](#topic-phasers) |
| `status` | `st` | [Status displays](#topic-status) |
| `stop` | `allstop`, `halt` | [Course and speed](#topic-helm) |
| `style` | `styles`, `ribbons` | [Command styles and trust](#topic-styles) |
| `surrender` | - | [Self-destruct and surrender](#topic-destruct) |
| `sweep` | `sniff`, `exhaust`, `plasma` | [Cloaking device](#topic-cloak) |
| `tachyon` | - | [Tachyon detector torpedo](#topic-tachyon) |
| `target` | `t`, `tgt`, `designate` | [Targeting](#topic-targeting) |
| `tell` | `order` | [Ally orders](#topic-tell) |
| `text` | - | [Key macros](#topic-keys) |
| `time` | `x` | [Time, pause and quitting](#topic-time) |
| `torp` | `torps`, `torpedo`, `torpedoes`, `torpedos` | [Torpedoes](#topic-torpedoes) |
| `tractor` | `tr` | [Tractor beam](#topic-tractor) |
| `translate` | `interpret`, `english` | [Orders in plain English](#topic-plain-english) |
| `transport` | `beam` | [Transporters and boarding](#topic-transport) |
| `tubes` | `tube` | [Torpedoes](#topic-torpedoes) |
| `turn` | `point` | [Lock and turn](#topic-lock) |
| `undock` | - | [Docking](#topic-dock) |
| `unload` | `ul` | [Loading and autoload](#topic-loading) |
| `voice` | `mic`, `microphone` | [Speaking orders](#topic-voice-orders) |
| `warp` | `w`, `speed` | [Course and speed](#topic-helm) |
