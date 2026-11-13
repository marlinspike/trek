---
title: Missions
category: Game
order: 5
aliases: missions, mission, rescue, escort, convoy, intercept, runner, ward, hunters, distress call, stricken ship, evacuees
summary: Battles with a goal beyond holding the field: rescue a crippled ship's people, get a convoy through, stop a runner.
see: counsel, transport, after-battle, tour, patrol, campaigns
---
Some battles carry a mission. The battle still ends the old way, when one side holds the field; the mission is a second question it answers, and Starfleet's assessment judges both. The mission card at the top right of the map shows the goal and how it stands, and the ship it is about is marked on the map.

## Rescue

A ship of ours is crippled and drifting, with people aboard and her reactor failing (the card counts down the cycles). To take them off, bring a ship of ours within transporter range (3,000) and **lower the shield facing her**: transporters cannot beam through a raised shield. A Dreadnought's eight transporter rooms take about ten people a cycle. The people you rescue ride in the ship that took them off, and if she is lost they are lost with her. When the enemy is beaten, whoever is still aboard is taken off after the battle.

That makes a rescue the mind against the sword: you must turn a lowered face to the stricken ship and an armoured face to the enemy, or have a wingman screen you. One enemy ship (the hunter) goes for her from the start. Saving three in four counts as a success; saving everyone under fire can earn the **Karagite Order of Heroism**.

    lower 5                  (the shield facing her, by number)
    reenforce 2              (the shield facing the enemy)

## Escort

A freighter or tanker sails for a point at her own speed, and she cannot fight. Hunters go for her. Get her there and she goes to warp; if she is destroyed or taken, the mission fails. Close up on her before the hunters do, and kill or disable them first.

## Intercept

One enemy ship, the runner, makes for the edge of the sector with her report. She must not escape: destroy her, cripple her drives so she can't move, or make her surrender. She still fires when she can, and her friends will try to buy her the time.

She carries the news, not a fight: laden and nursing her drives, she makes only part of your best warp (`runner_pace`, 0.6 by default). She is already out on the flank when the battle starts, and her friends stand between you and her. A stern chase gives her the lead she started with; a course that leads her meets her. Spock works one out in the counsel ("Cut her off"), and Worf locks on once she is in reach, not before, so your weapons stay on the ships that are.

    counsel disable the runner's engines
    helm <intercept course> warp 9.5
    pursue <runner> warp 9.5

## Wards don't hold the field

The ship you protect is not a fighting ship: she doesn't keep a battle going, can't escape by distance, and isn't counted among a tour stop's friends.

## Failing a mission

A failed mission doesn't end a tour. It shows in Starfleet's assessment, in the log, and in what happens later: on the Border Patrol, a frigate whose report gets through brings one more Klingon to Starbase 12, and the Aldren's survivors and the Tamar Kessel's cargo are only yours if you save them.

## Writing your own

A tour stop or a preset can carry a mission (see [[tour]]):

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
