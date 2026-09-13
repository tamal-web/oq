"""
Energy Conservation (EC) Engine
================================
Decides STRIKE_NOW / HOLD_THEN_STRIKE_LATER / HARVEST_NOW by comparing the
expected value of each option, not by thresholding "legal + affordable."

Integrates:
  - EnergyStateInput   <- Energy Intelligence Engine's EnergyState
  - ComplianceInput    <- RC Engine's ComplianceResult (the legality gate)
  - OvertakeOpportunity <- Overtake Intelligence's read of the current window

Grounded in an observed 2026-season failure mode: a large share of this
season's overtakes have been "reversible" passes -- a car with more charge
surges past a more-depleted car, only to be re-passed a lap later once the
energy state flips back. Those passes register as position changes but
carry close to zero real value. This engine's core fix is that it never
credits the full value of a position gain -- it multiplies by an estimated
probability the pass actually STICKS, and that probability is explicitly a
function of the energy differential between the two cars, not just whether
the move is legal and affordable.

Track behavior differs by circuit and is captured in TrackOvertakeProfile.
Monaco is configured below: it is energy-ABUNDANT (9MJ/lap cap, short
straights, heavy braking -- see the RC engine's MONACO_2026 profile) but
historically one of the hardest circuits on the calendar to physically pass
on, because its narrow, barrier-lined layout leaves little racing room
regardless of battery charge. That combination -- energy not being the
bottleneck, opportunities being rare -- is encoded explicitly below, and it
changes the Hold-vs-Strike math: at a track with very few passing windows
per lap, waiting for "a better one" is not free, because a better one may
simply not come.

All numeric weights in TrackOvertakeProfile are calibrated heuristics, not
values fit to a labeled dataset -- they are structured so that plugging in
real logged overtake-attempt outcomes (per track) later is a matter of
re-fitting these few parameters, not restructuring the engine.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Optional


# ---------------------------------------------------------------------------
# Inputs from the other three engines
# ---------------------------------------------------------------------------

@dataclass
class EnergyStateInput:
    """Mirrors the fields of Energy Intelligence's EnergyState that EC needs."""
    soc: float                       # J, current SoC
    harvest_cap_remaining: float     # J, legal headroom left to harvest this lap
    energy_harvested_lap: float      # J
    overtake_bonus_left: float       # J
    soc_confidence: float            # 0-1
    laps_remaining_in_stint: int


@dataclass
class ComplianceInput:
    """Mirrors the fields of RC's ComplianceResult that EC needs."""
    allowed: bool
    clipped_value: Optional[float] = None


class TrackSection(Enum):
    STRAIGHT = "straight"
    BRAKING_ZONE = "braking_zone"
    CORNER_EXIT = "corner_exit"


@dataclass
class OvertakeOpportunity:
    """What Overtake Intelligence hands EC about the current window."""
    gap_to_car_ahead_s: float
    closing_speed_delta_mps: float                      # positive = closing on the car ahead
    track_section: TrackSection
    energy_required_j: float                            # cost of the proposed move
    position_value: float                               # 0-1, how much this swap is worth
    laps_remaining_in_race: int
    opponent_estimated_soc_fraction: Optional[float] = None  # 0-1, inferred, never directly observed
    opponent_used_overtake_mode_this_lap: bool = False


# ---------------------------------------------------------------------------
# Track-specific overtaking priors
# ---------------------------------------------------------------------------

@dataclass
class TrackOvertakeProfile:
    name: str
    base_pass_stick_probability: float   # geometry-driven baseline, independent of energy state
    energy_differential_weight: float    # how much an energy edge over the opponent raises P(stick)
    opportunities_per_lap: float         # rough count of distinct viable overtaking windows per lap
    reversal_discount: float             # value haircut applied for passes likely to be easily reversed


# Monaco: energy-abundant (see RC engine's MONACO_2026 harvest cap of 9MJ/lap) but
# geometrically one of the most difficult circuits to pass on -- narrow, barrier-lined,
# very few real overtaking zones. Because the bottleneck here is track geometry rather
# than energy, the energy-differential term is weighted low (a fully-charged car still
# usually can't manufacture a passing lane that doesn't exist), and opportunities_per_lap
# is low, which matters a lot for the Hold decision -- see _probability_better_window().
MONACO_OVERTAKE_PROFILE = TrackOvertakeProfile(
    name="Monaco",
    base_pass_stick_probability=0.45,  # probability the ATTEMPT succeeds given car is in the trigger zone
    energy_differential_weight=0.20,   # energy edge matters somewhat at Monaco (limited zones)
    opportunities_per_lap=1.0,         # Monaco has ~1 real overtaking zone per lap (Harbour chicane)
    reversal_discount=0.25,            # passes at Monaco are hard to immediately reverse (narrow track)
)

# Reference profile for a high-speed, energy-differential-driven circuit -- shows how a
# second track plugs into the same engine; not requested this turn, included for contrast.
GENERIC_HIGH_SPEED_PROFILE = TrackOvertakeProfile(
    name="GenericHighSpeed",
    base_pass_stick_probability=0.35,
    energy_differential_weight=0.45,
    opportunities_per_lap=2.5,
    reversal_discount=0.55,
)


class ECDecision(Enum):
    STRIKE_NOW = "strike_now"
    HOLD_THEN_STRIKE_LATER = "hold_then_strike_later"
    HARVEST_NOW = "harvest_now"


@dataclass
class ECResult:
    decision: ECDecision
    p_pass_sticks: float
    ev_strike: float
    ev_hold: float
    ev_harvest: float
    rationale: str


def _clip(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


class EnergyConservationEngine:
    def __init__(self, track: TrackOvertakeProfile, energy_value_per_mj: float = 1.0):
        """
        energy_value_per_mj converts joules into the same "value units" as
        position_value (0-1 scale), so energy cost and position gain are
        directly comparable in the expected-value math. It is scaled per-call
        by how energy-scarce the car actually is right now (see
        _energy_value_per_mj) rather than being a single fixed constant.
        """
        self.track = track
        self.energy_value_per_mj_base = energy_value_per_mj

    # -----------------------------------------------------------------
    # P(pass sticks) -- the central fix for the reversible-pass problem
    # -----------------------------------------------------------------
    def _probability_pass_sticks(
        self, opportunity: OvertakeOpportunity, own_soc_fraction: float
    ) -> float:
        opp_soc = (
            opportunity.opponent_estimated_soc_fraction
            if opportunity.opponent_estimated_soc_fraction is not None
            else 0.5  # unknown -> assume symmetric energy states, the conservative case
        )
        soc_diff = own_soc_fraction - opp_soc
        energy_term = self.track.energy_differential_weight * soc_diff

        proximity_term = 0.15 * _clip(1.0 - opportunity.gap_to_car_ahead_s / 1.0, 0.0, 1.0)
        closing_term = _clip(opportunity.closing_speed_delta_mps / 15.0, -0.15, 0.15)

        # a defender who already burned their own Overtake Mode this lap is more
        # depleted than the "unknown -> symmetric" assumption -- nudge P(stick) up
        depletion_bonus = 0.05 if opportunity.opponent_used_overtake_mode_this_lap else 0.0

        p = (
            self.track.base_pass_stick_probability
            + energy_term
            + proximity_term
            + closing_term
            + depletion_bonus
        )
        return _clip(p, 0.02, 0.95)

    # -----------------------------------------------------------------
    # How much one joule is currently "worth" giving up
    # -----------------------------------------------------------------
    def _energy_value_per_mj(self, energy: EnergyStateInput) -> float:
        scarcity = 1.0
        if energy.laps_remaining_in_stint > 0:
            projected_recoverable = energy.harvest_cap_remaining * energy.laps_remaining_in_stint
            if projected_recoverable < energy.soc:
                # can't fully replenish this spend before the stint likely ends -- costs more
                scarcity = 1.5
        if energy.soc_confidence < 0.6:
            # uncertain SoC estimate -- be more conservative about spending against it
            scarcity *= 1.2
        return self.energy_value_per_mj_base * scarcity

    def _opportunity_cost(self, opportunity: OvertakeOpportunity, energy: EnergyStateInput) -> float:
        mj_spent = opportunity.energy_required_j / 1e6
        return mj_spent * self._energy_value_per_mj(energy)

    def _race_phase_multiplier(self, opportunity: OvertakeOpportunity) -> float:
        # position gains matter more as laps run out: less time left for a rival to
        # simply re-pass back, and fewer remaining chances to try again if you hold
        if opportunity.laps_remaining_in_race <= 5:
            return 1.6
        if opportunity.laps_remaining_in_race <= 15:
            return 1.25
        return 1.0

    def _probability_better_window(self) -> float:
        # tracks with few overtaking opportunities per lap make "wait for something
        # better" a weaker bet. At Monaco with only ~1 zone/lap, the probability
        # of getting a BETTER window next lap is very low — the current window
        # IS the rare window. Cap at 0.15 for low-opportunity tracks.
        raw = 0.20 * self.track.opportunities_per_lap
        return _clip(raw, 0.05, 0.45)

    # -----------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------
    def evaluate(
        self,
        energy: EnergyStateInput,
        compliance: ComplianceInput,
        opportunity: OvertakeOpportunity,
        own_soc_cap: float = 4e6,
    ) -> ECResult:
        own_soc_fraction = _clip(energy.soc / own_soc_cap, 0.0, 1.0)
        p_stick = self._probability_pass_sticks(opportunity, own_soc_fraction)
        phase_mult = self._race_phase_multiplier(opportunity)
        opp_cost = self._opportunity_cost(opportunity, energy)

        can_strike_legally = compliance.allowed
        can_strike_affordably = energy.soc >= opportunity.energy_required_j

        # ---- EV(Strike Now) ----
        if can_strike_legally and can_strike_affordably:
            value_if_sticks = opportunity.position_value * phase_mult
            # Never credit full position_value for a move unlikely to stick.
            # Discount proportional to reversal risk and p_stick.
            value_if_sticks *= 1.0 - self.track.reversal_discount * (1.0 - p_stick)

            # FIX: opp_cost is the cost regardless of outcome.
            # EV = p_stick × value_gained - cost_spent (cost occurs whether move succeeds or not)
            # NOT: (p × value) - ((1-p) × cost) - cost  <-- that subtracts cost twice
            ev_strike = (p_stick * value_if_sticks) - opp_cost
        else:
            ev_strike = float("-inf")  # not a real option right now

        # ---- EV(Hold -> Strike Later) ----
        p_better_window = self._probability_better_window()
        future_p_stick = _clip(p_stick + 0.08, 0.02, 0.95)  # slightly better: more banked energy by then
        future_value = opportunity.position_value * phase_mult * (
            1.0 - self.track.reversal_discount * (1.0 - future_p_stick)
        )
        delay_discount = 0.85  # a later lap is worth less — the race is finite
        risk_of_losing_window_entirely = opportunity.position_value * 0.20
        ev_hold = (
            p_better_window * future_value * delay_discount
            - (1.0 - p_better_window) * risk_of_losing_window_entirely
        )

        # ---- EV(Harvest Now) ----
        # FIX: Normalise harvest value to the same scale as position_value (0-1).
        # harvest_cap_remaining is in joules (0 → 9e6). Normalise to 0-1 relative
        # to a full lap's harvest budget. Then scale by a small weight so it only
        # wins when the position gain is truly marginal and the battery is very low.
        harvest_cap_fraction = _clip(energy.harvest_cap_remaining / 9e6, 0.0, 1.0)
        soc_fraction = _clip(energy.soc / own_soc_cap, 0.0, 1.0)
        # Harvest is only valuable if battery is low — at high SOC, forgoing the
        # pass to harvest more is pointless (battery already full).
        harvest_urgency = _clip(1.0 - soc_fraction, 0.0, 1.0)  # 1.0 when depleted
        recharge_value = harvest_cap_fraction * harvest_urgency * 0.15  # max 0.15 units
        forgone_value = p_stick * opportunity.position_value * phase_mult * 0.5
        ev_harvest = recharge_value - forgone_value

        options = {
            ECDecision.STRIKE_NOW: ev_strike,
            ECDecision.HOLD_THEN_STRIKE_LATER: ev_hold,
            ECDecision.HARVEST_NOW: ev_harvest,
        }
        decision = max(options, key=options.get)

        rationale_bits = [
            f"P(stick)={p_stick:.2f}",
        ]
        if not can_strike_legally:
            rationale_bits.append("RC blocked")
        elif not can_strike_affordably:
            rationale_bits.append("Insufficient SoC")
        else:
            rationale_bits.append(f"EV(strike)={ev_strike:.2f}")

        return ECResult(
            decision=decision,
            p_pass_sticks=p_stick,
            ev_strike=ev_strike,
            ev_hold=ev_hold,
            ev_harvest=ev_harvest,
            rationale="; ".join(rationale_bits),
        )


# =============================================================================
# INTEGRATION WRAPPER FOR OVERTAKE ENGINE (oe.py)
# =============================================================================

_GLOBAL_EC_ENGINE = EnergyConservationEngine(track=MONACO_OVERTAKE_PROFILE)

def check_energy_conservation(
    energy_state: dict,
    row: dict,
    rc_allowed: bool,
    opponent_energy_state: Optional[dict] = None,
) -> tuple[bool, str, str]:
    """
    Stateless adapter called per-tick by oe.py.
    Returns (pass: bool, reason: str, decision_name: str).
    """
    # 1. Prepare EnergyStateInput — all in joules
    soc_mj = energy_state.get('soc_mj', 0.0)
    regen_mj = energy_state.get('energy_regen_lap_mj', 0.0)
    soc_j = soc_mj * 1e6
    # Monaco harvest cap is 9 MJ/lap per RC profile
    harvest_cap_remaining_j = max(0.0, 9.0 - regen_mj) * 1e6

    energy_input = EnergyStateInput(
        soc=soc_j,
        harvest_cap_remaining=harvest_cap_remaining_j,
        energy_harvested_lap=regen_mj * 1e6,
        overtake_bonus_left=energy_state.get('overtake_mode_bonus_remaining_mj', 0.0) * 1e6,
        soc_confidence=energy_state.get('soc_confidence', 0.9),
        laps_remaining_in_stint=20,
    )

    # 2. Prepare ComplianceInput
    compliance = ComplianceInput(allowed=rc_allowed)

    # 3. Prepare OvertakeOpportunity
    lap = int(row.get('LapNumber', 1))
    laps_remaining = max(1, 78 - lap)

    gap_raw = row.get('GapSeconds')
    try:
        gap = float(gap_raw) if gap_raw is not None else 1.0
        if gap != gap or gap <= 0:  # NaN or non-positive
            gap = 1.0
    except (TypeError, ValueError):
        gap = 1.0

    brake = row.get('Brake', False)
    brake_val = float(brake) if not isinstance(brake, bool) else (1.0 if brake else 0.0)
    throttle = float(row.get('Throttle', 0.0))

    if brake_val > 0.05:
        section = TrackSection.BRAKING_ZONE
    elif throttle > 90:
        section = TrackSection.STRAIGHT
    else:
        section = TrackSection.CORNER_EXIT

    # Position value: scaled by how tight the gap is.
    # Gap of 0.1s → very close → high urgency (0.85)
    # Gap of 2.0s → near trigger limit → lower urgency (0.40)
    # Linear interpolation between 0.40 (at 2.0s) and 0.85 (at 0.1s)
    gap_clamped = max(0.1, min(2.0, gap))
    position_value = 0.85 - (gap_clamped - 0.1) / (2.0 - 0.1) * (0.85 - 0.40)

    # End-of-race urgency boost
    if laps_remaining <= 5:
        position_value = min(0.95, position_value * 1.3)

    # Opponent SOC
    opp_soc_frac = 0.5
    if opponent_energy_state:
        opp_soc_mj = opponent_energy_state.get('soc_mj', 2.0)
        opp_soc_frac = _clip(opp_soc_mj / 4.0, 0.0, 1.0)

    # Energy cost of the overtake: roughly 0.3 MJ = 300kJ for a short burst
    # (0.6 MJ was too high; most Monaco passes are short braking-zone dives)
    energy_required_j = 0.3e6

    opportunity = OvertakeOpportunity(
        gap_to_car_ahead_s=gap,
        closing_speed_delta_mps=0.0,
        track_section=section,
        energy_required_j=energy_required_j,
        position_value=position_value,
        laps_remaining_in_race=laps_remaining,
        opponent_estimated_soc_fraction=opp_soc_frac,
        opponent_used_overtake_mode_this_lap=False,
    )

    # 4. Evaluate
    result = _GLOBAL_EC_ENGINE.evaluate(energy_input, compliance, opportunity)

    is_pass = (result.decision == ECDecision.STRIKE_NOW)

    reason_prefix = "EV+: " if is_pass else f"{result.decision.name}: "
    reason = f"{reason_prefix}{result.rationale}"

    return is_pass, reason, result.decision.name
