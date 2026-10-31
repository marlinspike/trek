---
title: Bridge officers
category: Crew
order: 0
aliases: crew, bridge, officers, delegate, dg, assume, takeback, station, stations, spock, worf, geordi, la forge, laforge, seven, seven of nine, chatter
summary: Hand a station to its officer, take it back, and hear what your crew thinks.
see: conn, talking, llm, controls
---
Four officers stand by on your bridge. Each one can run a **station** for you, so you can concentrate on the decisions that matter.

| Station | Officer | Runs |
|---|---|---|
| Helm | Commander Spock | course and speed: closing, opening the range, weaving |
| Tactical | Lieutenant Worf | targets, phasers, torpedoes, probes, point defense |
| Engineering | Lieutenant Commander Geordi La Forge | shields, reinforcing, repair priorities, cloak |
| Science | Seven of Nine | scanning the target and every other contact |

```console
delegate tactical
delegate helm science
delegate all
assume helm
assume all
crew
```

- `delegate <station>` hands a station to its officer. `assume <station>` takes it back and ends anything that officer was working on. `all` covers every station.
- `stand down` takes every station and the bridge back at once and holds fire; `spock, stand down` (or just `spock, stop`) does it for one officer. See [[ceasefire|Cease fire and stand down]].
- The **Crew** tab, beside **Contacts** and **Fleet** under the weapons, shows who runs each station. Click **Captain** / **Officer** to switch, or click an officer's name to speak to them.
- `crew` lists your officers, who is running what, and how each of them feels about you.
- To let one officer command the whole ship, say "Seven, take the bridge". See [[conn|Giving an officer the bridge]].
- To have Seven knock out an enemy's shields, phasers or torpedoes, say "Seven, disable the Klingons' shields". See [[disable|Disabling enemy systems]].

## You stay in command

- Anything you order yourself overrides the officer for a few seconds, then they carry on from where you left them.
- Officers never pick a target when you have chosen one. They only choose when you have none.
- Officers never retreat, surrender, self-destruct, beam across or give orders to allies. Those decisions are yours.
- If you beam to another ship, your officers come with you. Their stations go back to you until you hand them over again.

Each officer has a personality. Worf is aggressive and closes for the kill; Spock holds a careful range; Geordi spends repair effort where it matters most; Seven scans everything, efficiently.

## Chatter

Your officers comment on the battle: Worf when torpedoes go out, Geordi when the hull or the engines are in trouble, Seven when new contacts appear. `crew chatter off` quiets them, and `crew chatter on` brings them back.

To ask them questions or give them orders in plain words, see [[talking|Talking to your officers]].
