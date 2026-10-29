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
