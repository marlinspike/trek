---
title: Your crew
category: Captain's manual
order: 3
aliases: your crew, the crew, officers and personalities, personalities, sulu, chekov, doctor, the doctor, stand-ins, stand in, trust, rapport
summary: The officers on your bridge: who they are, what each does best, and how to command them.
see: crew, conn, talking, disable, styles
---
A captain is only as good as the bridge. Your officers can run their stations for you, take the whole ship, work on projects together, argue their case, and remember how you treated them. Each of them is a person, with traits, a temper and a way of speaking. Those change how they talk, never how well they do the job.

{{crew_roster}}

## Who they are

**Commander Spock** runs the helm and advises on every station. He holds a careful, calculated range, quotes the odds, and keeps an eye on the damage. When a system is badly hurt he offers to direct the repair crews, and once you agree he sets the priority as the fight changes (`spock, manage repairs`). With the conn he fights like the logician he is. When Seven is away, he takes the science station, a little more slowly against the Borg.

**Lieutenant Worf** runs tactical: targets, phasers, torpedoes, probes and point defense. Given the conn, he closes fast and hits hard. He can `capture` a ship for you: he opens a hole in her shields, thins her crew and boards her. Against the Borg he is the one who takes the shuttle across ([[away-team]]). He will remind you that a Klingon captain does not surrender to a demand.

**Lieutenant Commander Geordi La Forge** runs engineering: shields, reinforcing, repair priorities and the cloak. He tells you when the hull or the engines are in trouble, warns you when your own warp drive is venting a trail, and can put a team on the engines when you need **all she's got** ([[boost]]). Given the conn, he looks after the ship first.

**Seven of Nine** runs science. She scans everything, efficiently. Tell her what to knock out and on whom (`seven, disable their shields`) and she plans it and carries it out:

- She scans the target.
- She aims the phasers tight.
- She fires torpedoes in one close salvo fused to burst on a ring, so a dodge in any direction still meets a blast.
- Against a trigger-happy crew she baits their point defense first.

She and Spock build the [[tachyon]] detector and the [[deflector]] pulse that find cloaked ships, and the plasma-seeker that follows a leaking drive. Against the Borg she is indispensable. She knows the Collective from the inside: she tunes your shields against them, studies their ships, and finds the vinculum relay.

**Lieutenant Sulu** stands by and takes tactical when Worf is away or hurt. **Ensign Chekov** takes the helm when Spock moves to cover science.

**The Doctor** runs sickbay. He runs no station, but he is aboard in every battle:

- He mends an away team that comes back hurt and sends them back to duty.
- He studies the drones you rescue, which makes every later scan of the Borg go further.
- With Seven, he can inoculate the crew against assimilation (`design inoculate`).

## Handing over the work

| You say | What happens |
|---|---|
| `delegate tactical`, "Worf, take tactical" | that officer runs their station; you can still give any order yourself |
| `seven, take the bridge`, `conn spock` | one officer runs every station, in their own style |
| "I have the helm", `assume all`, `stand down` | the station, or everything, comes back to you |
| `seven, disable their shields`, `capture gorkon` | an officer takes on a whole job and reports as it goes |
| `spock, manage repairs` | Spock directs the repair crews |

Your own orders always come first. Anything you order overrides an officer for a few seconds, and then they carry on. Officers never retreat, surrender, self-destruct, beam across or give orders to your allies: those decisions are yours.

## Working together

Some things take two or three of them. Ask any of them in your own words ("Spock, there's a cloaked ship out there") or use `design`:

{{collaborations}}

Each takes some cycles of work, and longer if the ship has lost crew. The officers tell you when it starts and when it is ready.

## Talking to them

Start a line with an officer's name and talk:

- "status" or "sitrep" gets a report on their station.
- "what do you recommend?" gets their best idea, with the command that carries it out.

They answer from what your sensors know, never more. Now and then an officer at a station you are running proposes an order ("Torpedoes inbound, Captain. Evasive manoeuvres?"). **Y** makes it so and **N** belays it. With a language model connected ([[llm]]), they answer in their own words and never repeat a line. Without one, they use lines written for them. Either way, `crew chatter off` quiets them, though an officer working a job still says what they are doing.

## Trust and rapport

They remember. Thanks and taking their advice build **rapport**, and insults wear it down. Rapport colours how they speak to you. **Trust** grows as you fight together: for each proposal you accept, each battle won at their post, and each time they stand out in the debrief. Trusted officers propose even while you type. Veterans act on an urgent proposal themselves if you leave it unanswered. See [[styles|Command styles and trust]].

You can make any of them your own in `config/officers.toml`: their name, traits, way of speaking, interests and lines. See [[talking|Talking to your officers]].
