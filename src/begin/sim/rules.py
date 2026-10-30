"""Rules profile: every tunable constant of the simulation in one place.

Constants tagged [R] come from the decoded begin2 binary (see
docs/REFERENCE.md); [E] marks remake extensions.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum


class DamageModel(str, Enum):
    REMAKE = "remake"          # [E] shields as 1.65, structural hull pool, location-aware subsystems
    CLASSIC_165 = "classic165"  # [R] begin 1.65 dealDamageToHull: any post-shield hit >= 50 kills


@dataclass(frozen=True)
class Rules:
    ticks_per_cycle: int = 10
    damage_model: DamageModel = DamageModel.REMAKE

    # helm [R]
    units_per_warp: float = 100.0
    warp_snap: float = 0.01
    min_warp: float = -1.0

    # power [R]
    warp_spill: float = 0.5
    life_support_failure_cycles: float = 3.0
    shield_reinforce_cost: float = 4.0

    # drives [R]
    temp_floor: float = 12.0
    temp_limit: float = 40.0
    temp_rate: float = 4.0

    # shields [R]
    shield_regen_min: float = 0.1

    # phasers [R]
    phaser_dam_mult: float = 45.0
    phaser_half: float = 0.5
    spread_min: float = 10.0
    spread_max: float = 45.0
    bank_bears_cone: float = 22.5

    # torpedoes and blasts [R]
    splash_mult: float = 5.0
    splash_radius_per_damage: float = 10.0
    prox_floor: float = 100.0
    probe_prox_floor: float = 50.0
    probe_time_floor: float = 5.0
    destruct_divisor: float = 9.0
    destruct_countdown: float = 5.0

    # sensors [R]
    cloak_reflect: float = 0.005
    sensor_haze_limit: float = 1.5     # [E] × rated range: beyond 1.0 contacts are hazy, beyond this they fade
    sensor_haze_error: float = 0.08    # [E] × rated range: position error at the haze limit
    probe_reflect: float = 0.5
    cloak_reveal_cycles: float = 1.0
    # [E] the deflector tachyon pulse (Spock and Seven reconfigure the dish; sim/projects.py)
    deflector_pulse_range: float = 15000.0
    deflector_pulse_arc: float = 60.0      # full width of the cone ahead of the ship, degrees
    deflector_pulse_energy: float = 40.0   # from the batteries, per pulse
    deflector_pulse_cooldown: float = 30.0
    deflector_pulse_reveal: float = 20.0   # cycles a cloaked ship stays visible

    # tractor / docking / transport [R]
    tractor_range: float = 1000.0
    dock_range: float = 1000.0
    beam_range: float = 3000.0

    # torpedo tubes: Begin's tubes fire in any direction [M]. True limits each tube to its mount's arc [E].
    tube_arcs: bool = False

    # phasers against ordnance [E]: chance each torpedo in the cone is set off = base + damage × per, capped.
    # Tuned in balance runs: higher values let automatic point defense stop ~95% of torpedoes.
    beam_kill_base: float = 0.1
    beam_kill_per_damage: float = 0.05
    beam_kill_max: float = 0.85
    pd_kill_scale: float = 0.4       # [E] × the chance above for point-defense shots; at 1.0 PD stopped ~85% of torpedoes

    # remake damage model [E]
    hull_per_mass: float = 1.0
    hull_base: float = 40.0
    crew_loss_scale: float = 0.6
    subsystem_rolls_per_damage: float = 0.1   # Begin: n = damage / 10
    targeted_max_accuracy: float = 0.85
    weapons_need_full_repair: bool = True     # [R] banks/tubes must be at 0% damage to charge/load
    # hull repairs [E]: share of the hull patched per cycle by a full crew, out of the fight
    hull_repair_rate: float = 0.004           # about 4 minutes to patch a badly holed hull
    hull_repair_under_fire: float = 0.25      # × the rate while in battle (hit lately, or an enemy close)
    hull_repair_docked: float = 0.03          # per cycle at a base, × the base's repair ratio
    hull_field_limit: float = 0.75            # crews in space patch the hull to this; a base restores the rest
    battle_quiet_cycles: float = 15.0         # cycles without a hull hit before repairs speed up again
    battle_enemy_range: float = 12000.0       # an enemy ship this close also counts as "in battle"
    # crew morale [E] (sim/systems/morale.py): points per event, before the race's steadiness
    morale_hull_loss: float = 60.0            # × the share of the hull lost in one hit
    morale_crew_loss: float = 80.0            # × the share of the crew lost
    morale_system_lost: float = 1.5           # a system destroyed
    morale_shield_down: float = 2.0           # a shield collapses
    morale_ally_lost: float = 8.0             # a ship of our side destroyed or surrendered
    morale_damage_dealt: float = 25.0         # × the share of an enemy's hull we knock off
    morale_enemy_lost: float = 6.0            # an enemy ship destroyed, disabled or surrendered (whole side)
    morale_kill_bonus: float = 6.0            # more for the ship that did it
    morale_repaired: float = 1.0              # a system back in service
    morale_hull_patched: float = 2.0          # each quarter of the hull patched
    morale_recovery: float = 0.5              # per cycle back toward the race's usual spirits, out of the fight
    morale_address: float = 8.0               # the captain's address to the crew, × how rousing it was
    morale_address_cycles: float = 60.0       # cycles before another address does any good
    # what morale does: ± these shares at 100 or 0 (none at 50)
    morale_repair: float = 0.25               # repair speed
    morale_reload: float = 0.15               # torpedo tube loading speed
    morale_accuracy: float = 0.15             # point defense and aimed fire
    morale_nerve: float = 0.30                # AI captains' damage threshold before retreating

    # engagement [E]
    escape_distance: float = 60000.0
    escape_cycles: float = 10.0
    captain_hold_cycles: float = 8.0
    scan_range_fraction: float = 0.5

    # extra knobs for experiments, merged from settings or presets
    extra: dict[str, float] = field(default_factory=dict)

    @property
    def dt(self) -> float:
        """Length of one tick in cycles."""
        return 1.0 / self.ticks_per_cycle

    def with_changes(self, **kw: object) -> Rules:
        return replace(self, **kw)  # type: ignore[arg-type]


DEFAULT_RULES = Rules()
