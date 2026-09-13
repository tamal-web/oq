"""
Rule Compliance (RC) Engine -- Track-Aware Version (Monaco 2026 configured)
============================================================================
2026 F1 regulations grant the FIA per-circuit relaxations/tightenings of the
energy rules (harvest cap, and at some tracks a bespoke MGU-K power-taper
curve instead of the generic zone-based 350/250kW split). This version makes
every track-dependent constant a swappable `TrackEnergyProfile`, and ships a
concrete Monaco profile built from FIA's confirmed Monaco-specific numbers.

Monaco specifics encoded here (see rule_ref / confidence on each for how
solid the source is):
  - 9MJ per-lap harvest cap all weekend (qualifying and race), dropping to
    8.5MJ in the race for a driver whose Overtake Mode is unavailable.
  - A bespoke "Rev 1" MGU-K power-taper curve replaces the generic zone-based
    split: deployment starts tapering from 350kW as low as 200km/h (vs the
    normal 290km/h), reaching ~0kW by 300km/h without Overtake Mode active,
    or a shallower taper (down to ~150kW at 300km/h, 0kW by 310km/h) with it.
  - No Straight Mode activation zones anywhere on the lap -- active aero
    stays in Corner Mode for the entire circuit, qualifying and race.
  - Race distance is 260km rather than the standard 305km (Sporting Regs
    Art. B2.5.2b -- confirmed directly from the official FIA document).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, List, Literal


class ActionType(Enum):
    NOMINAL_DEPLOY = "nominal_deploy"
    BOOST = "boost"
    OVERTAKE_MODE = "overtake_mode"
    RECHARGE = "recharge"


class SessionType(Enum):
    QUALIFYING = "qualifying"
    RACE = "race"


@dataclass
class RegLimits:
    """Constants that do NOT vary by track -- global 2026 regulation floor/ceiling."""
    mguk_power_abs_max: float = 350e3            # W -- Sporting Regs Art. B7.2.3
    mguk_torque_max: float = 500.0               # Nm -- PU Tech Regs Art. 5.4.10
    torque_efficiency_correction: float = 0.97
    v_launch_min: float = 50 / 3.6                # m/s -- PU Tech Regs Art. 5.4.11/12
    dSoC_max: float = 4e6                         # J -- reported delta-SoC limit
    overtake_detection_gap_s: float = 1.0         # s
    overtake_bonus_max: float = 0.5e6             # J


@dataclass
class PowerTaperPoint:
    speed_kmh: float
    max_power_w: float


@dataclass
class TrackEnergyProfile:
    """
    Everything the FIA is allowed to relax/tighten per circuit lives here.
    Build one of these per track rather than editing RC's internals.
    """
    name: str
    harvest_cap_qualifying: float
    harvest_cap_race: float
    harvest_cap_race_no_overtake_capability: float   # fallback cap if a car can't use Overtake Mode
    race_distance_km: float = 305.0

    # If a track uses the generic zone-based split (350kW key zones / 250kW elsewhere),
    # set uses_power_taper_curve=False and rely on the default constants.
    # If (like Monaco) the track has a bespoke taper curve, provide the breakpoints and
    # flip this flag -- check_power_request will interpolate the curve instead.
    uses_power_taper_curve: bool = False
    power_taper_no_overtake: Optional[List[PowerTaperPoint]] = None
    power_taper_with_overtake: Optional[List[PowerTaperPoint]] = None

    straight_mode_available: bool = True   # False at Monaco -- no Straight Mode activation zones


# ---------------------------------------------------------------------------
# MONACO 2026 PROFILE
# ---------------------------------------------------------------------------
MONACO_2026 = TrackEnergyProfile(
    name="Monaco",
    harvest_cap_qualifying=9e6,                          # confirmed, multiple corroborating sources
    harvest_cap_race=9e6,                                 # confirmed
    harvest_cap_race_no_overtake_capability=8.5e6,       # reported -- edge case, single source
    race_distance_km=260.0,                               # confirmed directly from FIA Sporting Regs Art. B2.5.2b
    uses_power_taper_curve=True,
    straight_mode_available=False,                        # confirmed, multiple corroborating sources

    # "Rev 1" curve without Overtake Mode active -- reconstructed from reported breakpoints,
    # NOT the literal FIA curve equation. Treat interpolated mid-points as approximate.
    power_taper_no_overtake=[
        PowerTaperPoint(speed_kmh=0,   max_power_w=350e3),
        PowerTaperPoint(speed_kmh=200, max_power_w=350e3),   # taper begins here (vs 290km/h elsewhere)
        PowerTaperPoint(speed_kmh=300, max_power_w=0.0),      # ~0kW by 300km/h without Overtake Mode
    ],
    # Shallower taper when Overtake Mode is active
    power_taper_with_overtake=[
        PowerTaperPoint(speed_kmh=0,   max_power_w=350e3),
        PowerTaperPoint(speed_kmh=200, max_power_w=350e3),
        PowerTaperPoint(speed_kmh=300, max_power_w=150e3),    # ~150kW at 300km/h with Overtake Mode
        PowerTaperPoint(speed_kmh=310, max_power_w=0.0),      # tapers to 0 by 310km/h
    ],
)


@dataclass
class ComplianceResult:
    allowed: bool
    reason: str
    clipped_value: Optional[float] = None
    rule_ref: Optional[str] = None
    confidence: str = "confirmed"   # "confirmed" | "reported" | "assumed"


def _interpolate_taper(curve: List[PowerTaperPoint], speed_kmh: float) -> float:
    """Piecewise-linear lookup of max legal power at a given speed."""
    if speed_kmh <= curve[0].speed_kmh:
        return curve[0].max_power_w
    for i in range(1, len(curve)):
        if speed_kmh <= curve[i].speed_kmh:
            p0, p1 = curve[i - 1], curve[i]
            frac = (speed_kmh - p0.speed_kmh) / (p1.speed_kmh - p0.speed_kmh)
            return p0.max_power_w + frac * (p1.max_power_w - p0.max_power_w)
    return curve[-1].max_power_w  # beyond the last breakpoint -> hold at the final value


class RuleComplianceEngine:
    def __init__(self, reg_limits: RegLimits, track: TrackEnergyProfile):
        self.reg = reg_limits
        self.track = track

        self._detection_point_crossed_this_lap = False
        self._proximity_met_at_detection = False
        self._overtake_zone_eligible_this_lap = False

    # -----------------------------------------------------------------
    # ENERGY COMPLIANCE
    # -----------------------------------------------------------------
    def check_power_request(
        self,
        requested_power_w: float,
        speed_mps: float,
        overtake_mode_active: bool = False,
        is_pit_lane_resume_or_start: bool = False,
        zone_is_key_accel_zone: bool = True,   # only used for tracks WITHOUT a taper curve
    ) -> ComplianceResult:
        # absolute ceiling always applies, regardless of track
        if requested_power_w > self.reg.mguk_power_abs_max:
            return ComplianceResult(
                allowed=False,
                reason="Exceeds absolute 350kW MGU-K power ceiling",
                clipped_value=self.reg.mguk_power_abs_max,
                rule_ref="Sporting Regs Art. B7.2.3",
                confidence="confirmed",
            )

        speed_kmh = speed_mps * 3.6

        if self.track.uses_power_taper_curve:
            curve = (
                self.track.power_taper_with_overtake
                if overtake_mode_active
                else self.track.power_taper_no_overtake
            )
            legal_cap = _interpolate_taper(curve, speed_kmh)
            if requested_power_w > legal_cap:
                return ComplianceResult(
                    allowed=False,
                    reason=(
                        f"{self.track.name} taper curve caps power at "
                        f"{legal_cap/1000:.0f}kW at {speed_kmh:.0f}km/h"
                        f"{' (Overtake Mode active)' if overtake_mode_active else ''}"
                    ),
                    clipped_value=legal_cap,
                    rule_ref=f"{self.track.name}-specific Rev 1 power mode",
                    confidence="reported",
                )
        else:
            # generic zone-based split used at most other circuits
            zone_cap = self.reg.mguk_power_abs_max if zone_is_key_accel_zone else 250e3
            if requested_power_w > zone_cap:
                return ComplianceResult(
                    allowed=False,
                    reason=f"Exceeds zone power cap ({zone_cap/1000:.0f}kW)",
                    clipped_value=zone_cap,
                    rule_ref="2026 zone-based refinement (April 2026)",
                    confidence="reported",
                )

        if speed_mps < self.reg.v_launch_min and not is_pit_lane_resume_or_start:
            return ComplianceResult(
                allowed=False,
                reason="MGU-K deployment below 50km/h launch threshold outside pit-lane start/resume",
                clipped_value=0.0,
                rule_ref="PU Tech Regs Art. 5.4.11/12",
                confidence="confirmed",
            )

        return ComplianceResult(allowed=True, reason="Within power limits")

    def check_torque_request(self, requested_torque_nm: float) -> ComplianceResult:
        if requested_torque_nm > self.reg.mguk_torque_max:
            return ComplianceResult(
                allowed=False,
                reason="Exceeds 500Nm MGU-K torque ceiling",
                clipped_value=self.reg.mguk_torque_max,
                rule_ref="PU Tech Regs Art. 5.4.10",
                confidence="confirmed",
            )
        return ComplianceResult(allowed=True, reason="Within torque limit")

    def check_harvest_this_lap(
        self,
        energy_harvested_lap: float,
        overtake_bonus_unlocked: bool,
        session_type: SessionType,
        overtake_capable: bool = True,
    ) -> ComplianceResult:
        if session_type == SessionType.QUALIFYING:
            cap = self.track.harvest_cap_qualifying
        else:
            cap = (
                self.track.harvest_cap_race
                if overtake_capable
                else self.track.harvest_cap_race_no_overtake_capability
            )
        if overtake_bonus_unlocked:
            cap += self.reg.overtake_bonus_max

        if energy_harvested_lap > cap:
            return ComplianceResult(
                allowed=False,
                reason=(
                    f"Lap harvest {energy_harvested_lap/1e6:.2f}MJ exceeds "
                    f"{self.track.name} cap {cap/1e6:.2f}MJ ({session_type.value})"
                ),
                clipped_value=cap,
                rule_ref=f"{self.track.name} per-lap harvest cap",
                confidence="reported",
            )
        return ComplianceResult(allowed=True, reason="Within harvest cap")

    def check_delta_soc(self, soc_now: float, soc_lap_start: float) -> ComplianceResult:
        delta = soc_now - soc_lap_start
        if abs(delta) > self.reg.dSoC_max:
            return ComplianceResult(
                allowed=False,
                reason=f"|delta SoC| {abs(delta)/1e6:.2f}MJ exceeds {self.reg.dSoC_max/1e6:.1f}MJ limit",
                rule_ref="PU Tech Regs Art. 5.4.8/9 (delta-SoC limit)",
                confidence="reported",
            )
        return ComplianceResult(allowed=True, reason="Within delta-SoC limit")

    # -----------------------------------------------------------------
    # OVERTAKE COMPLIANCE (unchanged by track -- proximity/zone rule is global)
    # -----------------------------------------------------------------
    def register_detection_point_crossing(self, gap_to_car_ahead_s: Optional[float]):
        self._detection_point_crossed_this_lap = True
        self._proximity_met_at_detection = (
            gap_to_car_ahead_s is not None
            and gap_to_car_ahead_s <= self.reg.overtake_detection_gap_s
        )
        self._overtake_zone_eligible_this_lap = self._proximity_met_at_detection

    def check_overtake_mode_activation(self, currently_in_activation_zone: bool) -> ComplianceResult:
        if not self._detection_point_crossed_this_lap:
            return ComplianceResult(
                allowed=False,
                reason="No detection point crossing registered yet this lap",
                rule_ref="Sporting Regs Art. B7.2 (single detection point per circuit)",
                confidence="reported",
            )
        if not currently_in_activation_zone:
            return ComplianceResult(
                allowed=False,
                reason="Not currently within the approved activation zone",
                rule_ref="Sporting Regs Art. B7.2",
                confidence="reported",
            )
        if not self._overtake_zone_eligible_this_lap:
            return ComplianceResult(
                allowed=False,
                reason="Proximity condition (<=1s) was not met at the detection point",
                rule_ref="Sporting Regs Art. B7.2",
                confidence="confirmed",
            )
        return ComplianceResult(
            allowed=True,
            reason="Proximity met at detection point and currently in activation zone",
            rule_ref="Sporting Regs Art. B7.2",
            confidence="reported",
        )

    def check_boost_mode_activation(self) -> ComplianceResult:
        return ComplianceResult(
            allowed=True,
            reason="Boost Mode has no proximity/zone restriction",
            rule_ref="F1 2026 terminology update (Boost Mode is unrestricted)",
            confidence="reported",
        )

    def reset_lap(self):
        self._detection_point_crossed_this_lap = False
        self._proximity_met_at_detection = False
        self._overtake_zone_eligible_this_lap = False

    # -----------------------------------------------------------------
    # UNIFIED ENTRY POINT
    # -----------------------------------------------------------------
    def evaluate_action(
        self,
        action: ActionType,
        requested_power_w: float,
        speed_mps: float,
        energy_harvested_lap: float,
        overtake_bonus_unlocked: bool,
        soc_now: float,
        soc_lap_start: float,
        session_type: SessionType,
        currently_in_activation_zone: bool = False,
        overtake_capable: bool = True,
        requested_torque_nm: Optional[float] = None,
        is_pit_lane_resume_or_start: bool = False,
        zone_is_key_accel_zone: bool = True,
    ) -> ComplianceResult:
        overtake_mode_active = action == ActionType.OVERTAKE_MODE

        if action == ActionType.OVERTAKE_MODE:
            gate = self.check_overtake_mode_activation(currently_in_activation_zone)
            if not gate.allowed:
                return gate
        elif action == ActionType.BOOST:
            gate = self.check_boost_mode_activation()
            if not gate.allowed:
                return gate

        power_check = self.check_power_request(
            requested_power_w,
            speed_mps,
            overtake_mode_active=overtake_mode_active,
            is_pit_lane_resume_or_start=is_pit_lane_resume_or_start,
            zone_is_key_accel_zone=zone_is_key_accel_zone,
        )
        if not power_check.allowed:
            return power_check

        if requested_torque_nm is not None:
            torque_check = self.check_torque_request(requested_torque_nm)
            if not torque_check.allowed:
                return torque_check

        harvest_check = self.check_harvest_this_lap(
            energy_harvested_lap, overtake_bonus_unlocked, session_type, overtake_capable
        )
        if not harvest_check.allowed:
            return harvest_check

        soc_check = self.check_delta_soc(soc_now, soc_lap_start)
        if not soc_check.allowed:
            return soc_check

        return ComplianceResult(allowed=True, reason="All applicable rules satisfied")

    # -----------------------------------------------------------------
    # Efficiency advisory (unchanged -- soft signal, not a hard rule)
    # -----------------------------------------------------------------
    def advise_energy_margin(
        self, soc_now: float, harvest_cap_remaining: float, laps_remaining_in_stint: int
    ) -> str:
        if laps_remaining_in_stint <= 0:
            return "no_laps_remaining"
        projected_headroom = harvest_cap_remaining * laps_remaining_in_stint
        if soc_now < 0.15 * self.reg.dSoC_max:
            return "low_margin: consider Recharge before further Boost/Overtake spend"
        if projected_headroom < soc_now:
            return "tight_budget: remaining harvest capacity may not replenish current spend rate"
        return "healthy_margin"


# =============================================================================
# INTEGRATION WRAPPER FOR OVERTAKE ENGINE (oe.py)
# =============================================================================

# Global instance initialized for Monaco
_GLOBAL_RC_ENGINE = RuleComplianceEngine(reg_limits=RegLimits(), track=MONACO_2026)

def check_rule_compliance(energy_state: dict, row: dict) -> tuple[bool, str]:
    """
    Stateless adapter called per-tick by oe.py.
    Returns (allowed: bool, reason: str).
    """
    try:
        speed_kph = float(row.get('Speed') or 0)
        speed_mps = speed_kph / 3.6
    except (TypeError, ValueError):
        speed_kph = 0.0
        speed_mps = 0.0

    gap_raw = row.get('GapSeconds')
    try:
        gap_s = float(gap_raw) if gap_raw is not None else None
        if gap_s is not None and (gap_s != gap_s or gap_s <= 0):
            gap_s = None
    except (TypeError, ValueError):
        gap_s = None

    # Register detection point crossing when gap is within 1s.
    # Do NOT call reset_lap on every non-close tick — that would reset state
    # during the same lap whenever the gap briefly widens above 1s (e.g., in
    # a braking zone where the car ahead also brakes). Only reset at a true
    # lap boundary (handled by the lap counter in server.py / EE).
    if gap_s is not None and gap_s <= 1.0:
        _GLOBAL_RC_ENGINE.register_detection_point_crossing(gap_s)

    # Extract energies in Joules
    energy_harvested_lap_j = energy_state.get('energy_regen_lap_mj', 0.0) * 1e6
    soc_now_j = energy_state.get('soc_mj', 0.0) * 1e6
    deployed_j = energy_state.get('energy_deployed_lap_mj', 0.0) * 1e6
    soc_lap_start_j = soc_now_j + deployed_j - energy_harvested_lap_j
    overtake_earned = energy_state.get('overtake_mode_earned', False)

    # Determine appropriate action type
    action = ActionType.OVERTAKE_MODE if overtake_earned else ActionType.BOOST

    # FIX: Check a REALISTIC deployment power for the current speed, not always
    # the maximum 350 kW. The old code always checked 350 kW which fails the
    # power taper above 200 kph. Instead, we check what the taper allows.
    # If the taper allows any positive power at this speed, RC passes.
    if MONACO_2026.uses_power_taper_curve:
        if overtake_earned and MONACO_2026.power_taper_with_overtake:
            taper_limit_w = _interpolate_taper(MONACO_2026.power_taper_with_overtake, speed_kph)
        elif MONACO_2026.power_taper_no_overtake:
            taper_limit_w = _interpolate_taper(MONACO_2026.power_taper_no_overtake, speed_kph)
        else:
            taper_limit_w = 350e3
    else:
        taper_limit_w = 350e3

    # If the taper allows zero power at this speed, RC cannot approve any deployment.
    if taper_limit_w <= 0:
        return False, f"MGU-K deployment not permitted at {speed_kph:.0f} kph (taper=0)"

    # Use the taper-limited power as the requested power (what the car can actually do)
    requested_power_w = min(350e3, taper_limit_w)

    result = _GLOBAL_RC_ENGINE.evaluate_action(
        action=action,
        requested_power_w=requested_power_w,
        speed_mps=speed_mps,
        energy_harvested_lap=energy_harvested_lap_j,
        overtake_bonus_unlocked=overtake_earned,
        soc_now=soc_now_j,
        soc_lap_start=soc_lap_start_j,
        session_type=SessionType.RACE,
        currently_in_activation_zone=True,  # Simplified: within gap → in zone
        overtake_capable=True,
    )

    return result.allowed, result.reason
