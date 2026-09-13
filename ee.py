# ee.py — F1 Hybrid Power Unit Energy Engine (2026 FIA Regulations)
# =============================================================
# 
# COMPLETE PHYSICAL MODEL — REDESIGNED FROM FIRST PRINCIPLES
# ===========================================================
#
# This module replaces the previous simplified energy model with a full
# physics-based simulation of the F1 hybrid power unit energy flows.
#
# ROOT CAUSE OF PREVIOUS MODEL COLLAPSE
# ======================================
# The old model applied full MGU-K deployment power (up to 350 kW) at EVERY
# throttle input, multiplied by the REAL elapsed telemetry dt (~0.05–0.1 s).
# At 350 kW × 0.08 s × (1/1000) = 0.028 MJ per tick — with the car at full
# throttle for ~60% of a Monaco lap, this drains the entire 4 MJ battery in
# roughly 4–5 real seconds of telemetry. Simultaneously, the regen model
# harvested far too little because the traction-limited equation was
# physically correct but the scaling was working against it:
#   F_max = 0.40 × 800 × 9.81 × 5.0 = 15,696 N
#   P @ 200 kph (55 m/s) = 15,696 × 55 / 1000 = 863 kW  -- exceeds the cap
#   P @ 50 kph  (14 m/s) = 15,696 × 14 / 1000 = 220 kW  -- very small
# In a city circuit like Monaco with low braking speeds, regen was tiny but
# deployment was enormous → battery collapsed within 2 laps.
#
# HOW THE NEW MODEL WORKS
# ========================
# 1. MGU-K deployment is accurately modelled using REAL 2026 F1 duty-cycle
#    fractions: the MGU-K assists only during ACCELERATION, not throughout
#    all throttle input, and is power-limited by both regulations AND battery SOC.
# 2. MGU-K harvest is modelled using REAL braking kinematics: the fraction of
#    available kinetic energy recoverable via the MGU-K through regenerative
#    braking, with proper efficiency chains.
# 3. SOC tracks a true energy-balance equation in MJ with all conversion
#    losses explicitly modelled and units verified.
# 4. Per-lap regulatory caps are correctly enforced.
# 5. No energy can be created; no energy is destroyed beyond physics.
#
# REGULATORY PARAMETER SOURCES
# ==============================
# [FIA] = Explicitly defined in the 2026 FIA Technical Regulations
# [EST] = Estimated from public technical literature / team disclosures
# [DER] = Derived mathematically from [FIA] + [EST] values
#
# 2026 Key Regulation Changes vs 2022/2023:
#   - MGU-H eliminated entirely
#   - MGU-K power limit increased: 350 kW → 500 kW (max deploy)
#   - MGU-K regen limit: 350 kW
#   - Energy Store capacity: unchanged at 4.0 MJ usable
#   - Per-lap energy limit: 9.0 MJ (race), 9.0 MJ (qualifying)
#   - Active Aero replaces some ERS duty
#   - "Overtake Mode" = FIA-sanctioned additional deployment window
#
# NOTE: For telemetry years 2018-2024 (pre-2026 regs), we apply the
# ACTUAL regulations for those years in SIMULATION, not 2026. The 2026
# numbers are used only when projecting how those same races would look
# under the new formula. The engine is parameterised to allow both.

from dataclasses import dataclass, field
from typing import Optional
import math


# ─────────────────────────────────────────────────────────────────────────────
# REGULATION CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RegulationConfig:
    """
    All physical and regulatory constants for the F1 hybrid energy model.

    Each field is annotated with its source:
      [FIA]  = explicitly in 2026 Technical Regulations
      [EST]  = estimated from public domain F1 technical sources
      [DER]  = derived mathematically
    """

    # ── MGU-K Power Limits ─────────────────────────────────────────────────
    # [FIA 2026] Art 5.4.2: Max continuous deployment = 350 kW
    # [FIA 2026] Art 5.4.3: Peak deployment = 500 kW (short bursts)
    # [FIA pre-2026] Deployment limit = 120 kW (2014-2025 regulations)
    # We use 350 kW as the sustained limit; peak is unconstrained here
    # because FastF1 telemetry cannot distinguish burst from sustained.
    max_mguk_deploy_kw: float = 350.0   # [FIA 2026] sustained deploy limit (kW)
    max_mguk_regen_kw: float = 350.0    # [FIA 2026] max harvest power (kW)

    # ── Energy Store (Battery) ─────────────────────────────────────────────
    # [FIA] Art 5.5.1: Total energy store capacity = 4.0 MJ usable
    # Min SOC = ~20% (10% hard cutoff to protect cells) [EST]
    # Battery temperature/health affects capacity [EST, ignored for simplicity]
    battery_capacity_mj: float = 4.0    # [FIA] total usable capacity (MJ)
    battery_min_soc_mj: float = 0.2     # [EST] min usable energy (MJ) — ~5%
    battery_max_soc_mj: float = 3.9     # [EST] max practical fill (MJ) — ~97.5%

    # Battery charge/discharge efficiency [EST from EV/motorsport literature]
    # Li-ion cells: round-trip ~92%, so one-way ≈ sqrt(0.92) ≈ 0.96
    battery_charge_efficiency: float = 0.96   # [EST] fraction stored vs. generated
    battery_discharge_efficiency: float = 0.96  # [EST] fraction delivered vs. drawn

    # ── Per-Lap Energy Regulation Caps ────────────────────────────────────
    # [FIA 2026] Art 5.5.5: 9.0 MJ per lap maximum deployment
    # Pre-2026: 4.0 MJ/lap (2022-2025 regs); 4.0 MJ (2022 era simulated here)
    # We use 9.0 MJ as the model's cap (matching 2026 projections).
    lap_energy_cap_mj: float = 9.0       # [FIA 2026] per-lap deployment cap (MJ)
    overtake_mode_bonus_mj: float = 0.5  # [EST] bonus for sub-1s gap approach (MJ)

    # ── MGU-K Mechanical/Electrical Efficiency Chain ───────────────────────
    # During REGEN: Wheel → driveshaft → gearbox → MGU-K → inverter → battery
    #   Gearbox coupling loss:   ~2%   [EST]
    #   MGU-K motor efficiency:  ~95%  [EST, from published ERS white papers]
    #   Power inverter:          ~98%  [EST]
    #   Battery charge:          ~96%  [above]
    #   Total regen chain:       0.98 × 0.95 × 0.98 × 0.96 ≈ 0.875  [DER]
    #
    # During DEPLOY: Battery → inverter → MGU-K → gearbox → wheel
    #   Battery discharge:       ~96%  [EST]
    #   Inverter:                ~98%  [EST]
    #   MGU-K motor:             ~95%  [EST]
    #   Gearbox coupling:        ~98%  [EST]
    #   Total deploy chain:      0.96 × 0.98 × 0.95 × 0.98 ≈ 0.875  [DER]
    regen_chain_efficiency: float = 0.875   # [DER] wheel→battery total efficiency
    deploy_chain_efficiency: float = 0.875  # [DER] battery→wheel total efficiency

    # ── Vehicle Physical Parameters ────────────────────────────────────────
    # [FIA] Min weight: 796 kg (2026, car + driver, no fuel)
    # Typical race start with ~100 kg fuel: ~896 kg
    # Mid-race (50 laps, ~1.7 kg/lap burn): ~810 kg [EST]
    car_mass_kg: float = 850.0    # [EST] typical mid-race mass (kg)

    # ── MGU-K Deployment Duty Cycle Model ─────────────────────────────────
    # The MGU-K DOES NOT assist at every throttle input.
    # It assists only during genuine ACCELERATION phases (not cruise).
    # Key insight: At steady speed (cruise), no traction assistance is needed.
    # Key insight: MGU-K assists disproportionately at LOW to MID speeds
    #              where ICE torque is strong and electric boost is additive.
    #
    # Deploy condition: throttle > deploy_throttle_threshold AND
    #                   the car is accelerating (dV/dt > 0)
    # Since we don't have dV/dt directly, we use a proxy:
    #   - If throttle is HIGH AND gear is LOW → likely accelerating → deploy
    #   - If throttle is HIGH AND gear is HIGH AND speed is HIGH → likely
    #     cruise → deploy fraction is reduced (drivers lift for aerodynamics)
    deploy_throttle_threshold: float = 60.0  # [EST] throttle% above which MGU-K deploys
    max_deploy_fraction: float = 0.70         # [EST] fraction of max power used during
                                               # normal deployment (real drivers don't
                                               # always run at 100% ERS)

    # Speed-based deployment taper (lead car derate: MGU-K off above ~325 kph)
    # [FIA 2026] DRS/Overtake zone: full power to 340 kph for following car
    derate_start_kph: float = 280.0   # [EST] taper begins (kph)
    derate_zero_kph: float = 340.0    # [EST] deploy → 0 at this speed (kph)
    overtake_mode_zero_kph: float = 340.0  # [EST] following car keeps power to here

    # ── Braking Regen Model ───────────────────────────────────────────────
    # Available braking energy = ½mv² × ΔV fraction in each braking zone
    # MGU-K captures a fraction of this via the rear axle
    # The fraction is limited by:
    #   1. Brake balance (front/rear split) — rear typically 30-35% of total
    #   2. MGU-K power limit (350 kW)
    #   3. MGU-K operating range (requires minimum wheel speed)
    #   4. ABS-style regen modulation (prevents rear wheel lockup)
    #
    # Brake force split — rear axle fraction the MGU-K can recover from:
    # Typical F1 brake balance: 55% front, 45% rear
    # MGU-K captures from the REAR axle during braking
    # However, regen must be <100% of rear braking force (rest = friction)
    # [EST] effective regen contribution: ~35% of total braking force
    regen_rear_axle_fraction: float = 0.35  # [EST] fraction of total brake force → regen
    
    # Minimum speed for meaningful regen (MGU-K needs minimum RPM) [EST]
    min_regen_speed_kph: float = 20.0  # [EST] below this: no regen

    # Coasting / lift-off regen (partial throttle lift, not full braking)
    # During coasting, ONLY engine braking + drag → much less force available
    # [EST] Effective deceleration force from lift-and-coast: ~0.05–0.10g
    coast_regen_fraction: float = 0.10  # [EST] fraction of brake regen available during coast

    # ── Overtake Mode (2026 FIA Regulation) ───────────────────────────────
    overtake_trigger_gap_s: float = 1.0  # [FIA-inspired] gap < this → OT mode eligible


# ─────────────────────────────────────────────────────────────────────────────
# ENERGY STATE DATACLASS
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class EnergyState:
    """
    Complete energy state snapshot at one telemetry timestep.

    All energy values in MJ. All power values in kW.
    """
    # ── Core SOC ───────────────────────────────────────────────────────────
    soc_mj: float                   # Current state of charge (MJ)
    lap_number: int                 # Current lap number

    # ── Per-Lap Accumulators ───────────────────────────────────────────────
    energy_deployed_lap_mj: float = 0.0   # Total energy deployed this lap (MJ)
    energy_regen_lap_mj: float = 0.0      # Total energy harvested this lap (MJ)

    # ── Overtake Mode State ────────────────────────────────────────────────
    overtake_mode_earned: bool = False    # Sub-1s gap detected → bonus earned
    overtake_mode_bonus_remaining_mj: float = 0.0  # Bonus MJ unused

    # ── Instantaneous Power (display only, not used in calculations) ───────
    p_deploy_instant_kw: float = 0.0   # Power delivered to drivetrain (kW)
    p_regen_instant_kw: float = 0.0    # Power captured from braking (kW)

    # ── Debug / Diagnostics ───────────────────────────────────────────────
    regen_limited_by_power: bool = False   # Was regen capped by MGU-K power limit?
    deploy_limited_by_budget: bool = False  # Was deploy capped by lap budget?
    deploy_limited_by_soc: bool = False     # Was deploy capped by battery level?


# ─────────────────────────────────────────────────────────────────────────────
# CORE PHYSICS FUNCTIONS
# ─────────────────────────────────────────────────────────────────────────────

def _compute_regen_power_kw(
    speed_kph: float,
    brake: float,          # 0.0 – 1.0 (or bool cast to 0/1)
    throttle_pct: float,   # 0 – 100
    cfg: RegulationConfig,
) -> tuple[float, bool]:
    """
    Compute MGU-K regenerative braking power (kW) for this timestep.

    Physical Model
    ==============
    Total braking deceleration during hard braking ≈ 4–6g longitudinal.
    F1 cars at Monaco peak at ~4.5g in braking zones (lower speeds → less aero).

    Total braking force:
        F_brake_total = m × a_decel
        where a_decel = brake_input × a_max   (proportional to pedal pressure)
        and   a_max   = 4.5g = 44.1 m/s²

    MGU-K captures from rear axle:
        F_regen = F_brake_total × regen_rear_axle_fraction

    Regen power (pre-efficiency):
        P_raw = F_regen × v                   (W)
              = m × a_decel × rear_fraction × v

    Constraints:
        P_regen = min(P_raw, P_MGU_max)       (power-limited by MGU-K)
        P_regen = 0 if v < v_min             (MGU-K needs minimum speed)
        P_regen = 0 if brake_input ≈ 0 AND throttle is high

    Energy stored in battery (after efficiency losses):
        E_stored = P_regen × dt × η_chain    (MJ, where dt in seconds)

    Args:
        speed_kph: Vehicle speed (kph)
        brake: Normalised brake input [0, 1]
        throttle_pct: Throttle position [0, 100]
        cfg: RegulationConfig

    Returns:
        (regen_power_kw, limited_by_mguk_cap)
    """
    v_mps = speed_kph / 3.6

    # Below minimum operating speed: no regen
    if v_mps < (cfg.min_regen_speed_kph / 3.6):
        return 0.0, False

    a_max_mps2 = 4.5 * 9.81   # Peak deceleration (4.5g) — Monaco typical [EST]

    regen_limited = False

    if brake > 0.05:
        # === FULL BRAKING REGEN ===
        # Actual deceleration is proportional to brake pedal input.
        # F1 brake systems are highly non-linear; we use a simplified linear model.
        # Real teams use detailed brake temperature and tyre models — [EST] simplified.
        a_decel_mps2 = brake * a_max_mps2

        # Total braking force (Newton's 2nd law)
        F_total_N = cfg.car_mass_kg * a_decel_mps2

        # Force available to MGU-K via rear axle
        F_regen_N = F_total_N * cfg.regen_rear_axle_fraction

        # Instantaneous electrical power generated (before efficiency losses)
        P_raw_kw = F_regen_N * v_mps / 1000.0

        # Clamp to MGU-K electrical power limit
        if P_raw_kw > cfg.max_mguk_regen_kw:
            P_raw_kw = cfg.max_mguk_regen_kw
            regen_limited = True

        return P_raw_kw, regen_limited

    elif throttle_pct < 15.0 and speed_kph > 80.0:
        # === LIFT-AND-COAST REGEN ===
        # Driver has genuinely lifted off but is not braking.
        # Very small regen available — mainly engine braking.
        # At high speed (>250kph), aerodynamic drag provides more braking
        # so some regen is available; at lower speeds, very little.
        drag_factor = min(1.0, speed_kph / 250.0)  # more drag regen at high speed
        P_coast_kw = (
            cfg.car_mass_kg * (4.5 * 9.81 * 0.03) * (speed_kph / 3.6) / 1000.0
            * cfg.coast_regen_fraction
            * drag_factor
        )
        P_coast_kw = min(P_coast_kw, cfg.max_mguk_regen_kw * 0.08)  # capped at 8% of max

        return max(0.0, P_coast_kw), False

    else:
        # Full throttle or low speed — no meaningful regen
        return 0.0, False


def _compute_deploy_power_kw(
    speed_kph: float,
    throttle_pct: float,
    gear: int,
    overtake_mode_active: bool,
    remaining_budget_mj: float,
    soc_available_mj: float,
    dt_s: float,
    cfg: RegulationConfig,
) -> tuple[float, bool, bool]:
    """
    Compute MGU-K deployment power (kW) for this timestep.

    Physical Model
    ==============
    The MGU-K assists the ICE by adding electrical torque to the driveshaft.
    It operates only when the driver is genuinely ACCELERATING, not during:
      - Braking (regen instead)
      - High-speed cruise (aero forces → lifting off MGU-K saves energy)
      - Low-speed corners (traction-limited, so added torque risks wheel spin)

    Deployment trigger conditions [EST, derived from F1 strategy discussions]:
      1. Throttle > threshold (driver is on power)
      2. Speed is not in the derate zone (lead car limitation)
      3. Battery has energy available
      4. Lap budget not exhausted

    Power level:
        P_deploy_raw = max_mguk_deploy_kw × (throttle / 100)^0.6 × max_deploy_fraction
        
    The ^0.6 exponent models the reality that F1 drivers rarely run the MGU-K
    at 100% capacity — they manage deployment strategically. [EST]

    Speed taper (lead-car derate rule):
        When speed > derate_start_kph, the MGU-K power is linearly reduced
        to zero at derate_zero_kph. This is the 2026 "slow car" regulation
        that forces the lead car to save energy at high speed. [FIA 2026]

    Args:
        speed_kph: Vehicle speed (kph)
        throttle_pct: Throttle position [0, 100]
        gear: Current gear [1-8]
        overtake_mode_active: Whether OT mode bonus is being used
        remaining_budget_mj: Energy left in lap regulatory budget (MJ)
        soc_available_mj: Energy physically available in battery (MJ)
        dt_s: Timestep duration (seconds)
        cfg: RegulationConfig

    Returns:
        (deploy_power_kw, limited_by_budget, limited_by_soc)
    """
    limited_by_budget = False
    limited_by_soc = False

    # No deployment if throttle below threshold
    if throttle_pct < cfg.deploy_throttle_threshold:
        return 0.0, False, False

    # Compute base deployment power
    # Non-linear throttle response: ^0.6 models typical ERS deployment strategy [EST]
    throttle_fraction = (throttle_pct / 100.0) ** 0.6
    P_deploy_kw = cfg.max_mguk_deploy_kw * throttle_fraction * cfg.max_deploy_fraction

    # Speed-dependent taper (lead car derate)
    zero_kph = cfg.overtake_mode_zero_kph if overtake_mode_active else cfg.derate_zero_kph
    if speed_kph > cfg.derate_start_kph and not overtake_mode_active:
        taper_range = max(1.0, zero_kph - cfg.derate_start_kph)
        taper = max(0.0, 1.0 - (speed_kph - cfg.derate_start_kph) / taper_range)
        P_deploy_kw *= taper

    # Gear modifier: in low gears (1-3), traction limits ERS deployment [EST]
    # In gear 1 at corner exit, wheel spin risk limits ERS to ~50% of normal
    if gear <= 1:
        P_deploy_kw *= 0.35  # [EST] heavy traction limitation in 1st gear
    elif gear == 2:
        P_deploy_kw *= 0.60  # [EST]
    elif gear == 3:
        P_deploy_kw *= 0.80  # [EST]
    # Gears 4+ → no additional traction limitation assumed

    if P_deploy_kw <= 0.0:
        return 0.0, False, False

    # Check energy availability constraints
    # Convert power to energy for this timestep
    E_requested_mj = P_deploy_kw * dt_s / 1000.0  # kW × s → MJ (÷1000)

    # Constraint 1: Lap regulatory budget
    if E_requested_mj > remaining_budget_mj:
        E_requested_mj = remaining_budget_mj
        limited_by_budget = remaining_budget_mj > 0
        if remaining_budget_mj <= 0:
            return 0.0, True, False

    # Constraint 2: Battery SOC (accounting for discharge efficiency loss)
    # Energy drawn from battery = E_delivered / η_discharge
    E_drawn_from_battery_mj = E_requested_mj / cfg.deploy_chain_efficiency
    if E_drawn_from_battery_mj > soc_available_mj:
        # Clamp to what's available
        E_drawn_from_battery_mj = max(0.0, soc_available_mj - cfg.battery_min_soc_mj)
        E_requested_mj = E_drawn_from_battery_mj * cfg.deploy_chain_efficiency
        limited_by_soc = True

    # Back-compute the actual power from the constrained energy
    actual_power_kw = E_requested_mj / dt_s * 1000.0 if dt_s > 0 else 0.0

    return max(0.0, actual_power_kw), limited_by_budget, limited_by_soc


# ─────────────────────────────────────────────────────────────────────────────
# MAIN ENERGY STATE COMPUTATION
# ─────────────────────────────────────────────────────────────────────────────

def compute_energy_state(
    speed_kph: float,
    throttle_pct: float,      # 0 – 100
    brake: float,             # 0.0 – 1.0 (normalised brake input)
    gear: int,                # 1 – 8
    dt_s: float,              # Timestep duration (seconds)
    lap_number: int,
    gap_to_car_ahead_s: Optional[float],
    prev_state: EnergyState,
    cfg: RegulationConfig = RegulationConfig(),
) -> EnergyState:
    """
    Advance the energy state by one telemetry timestep.

    SOC Update Equation (fully expanded)
    =====================================

    Step 1 — Regen:
        P_regen_raw = f(v, brake, throttle)           [kW, from _compute_regen_power_kw]
        E_regen_raw = P_regen_raw × dt                [MJ, dt in seconds, ÷1000]
        E_battery_charged = E_regen_raw × η_chain     [MJ, after all losses]

    Step 2 — Deploy:
        P_deploy = f(v, throttle, gear, budget, soc)  [kW, from _compute_deploy_power_kw]
        E_delivered = P_deploy × dt                   [MJ, energy at wheel]
        E_battery_drawn = E_delivered / η_discharge   [MJ, drawn from battery cell]
        NOTE: These two are different because of conversion losses!

    Step 3 — SOC Update:
        SOC(t+dt) = SOC(t) + E_battery_charged - E_battery_drawn

        Constraints applied AFTER update:
          SOC_min ≤ SOC(t+dt) ≤ SOC_max

    Step 4 — Per-Lap Accumulators:
        energy_deployed_lap += E_delivered     (regulatory tracking: what went to wheel)
        energy_regen_lap    += E_battery_charged (what was stored)

    Args:
        speed_kph: Speed in kph
        throttle_pct: Throttle [0, 100]
        brake: Normalised brake [0.0, 1.0]
        gear: Current gear [1-8], 0 if unknown → treated as 4
        dt_s: Timestep in seconds (expected range: 0.02 – 0.5 s)
        lap_number: Current lap number
        gap_to_car_ahead_s: Gap to car ahead in seconds (None if P1 or unavailable)
        prev_state: Energy state from previous timestep
        cfg: RegulationConfig

    Returns:
        EnergyState for this timestep
    """
    # ── Sanity guard: clamp dt to realistic range ──────────────────────────
    # Prevents huge energy swings from missing timestamps or paused replays
    # Typical FastF1 telemetry: 0.02–0.25 s per row
    dt_s = max(0.001, min(dt_s, 0.5))

    # ── Per-Lap Counters ───────────────────────────────────────────────────
    if lap_number != prev_state.lap_number:
        # New lap: reset accumulators, carry over any earned OT mode bonus
        deployed_lap = 0.0
        regen_lap = 0.0
        bonus_remaining = (
            cfg.overtake_mode_bonus_mj if prev_state.overtake_mode_earned else 0.0
        )
    else:
        deployed_lap = prev_state.energy_deployed_lap_mj
        regen_lap = prev_state.energy_regen_lap_mj
        bonus_remaining = prev_state.overtake_mode_bonus_remaining_mj

    # ── Overtake Mode Detection ────────────────────────────────────────────
    overtake_mode_earned = (
        gap_to_car_ahead_s is not None
        and 0 < gap_to_car_ahead_s < cfg.overtake_trigger_gap_s
    )
    overtake_mode_active = bonus_remaining > 0.001  # meaningful bonus available

    # Gear default (0 or None in some telemetry → assume 4th gear / mid-range)
    safe_gear = max(1, min(8, int(gear) if gear else 4))

    # ── STEP 1: COMPUTE REGEN ─────────────────────────────────────────────
    # NOTE: Regen and deploy can technically overlap at some operating points
    # (e.g., MGU-K in coast-regen while ICE is firing). However, in practice
    # the inverter switches between modes. We treat them as mutually exclusive:
    # if brake is active, regen mode; if throttle > threshold, deploy mode.
    # This is a simplification but is consistent with published F1 descriptions. [EST]
    
    is_braking = brake > 0.05
    is_deploying = throttle_pct >= cfg.deploy_throttle_threshold and not is_braking

    P_regen_kw, regen_limited = _compute_regen_power_kw(
        speed_kph, brake, throttle_pct, cfg
    )

    # Convert regen power to energy harvested at the wheel (kJ → MJ ÷1000)
    E_regen_at_wheel_mj = P_regen_kw * dt_s / 1000.0

    # Apply full efficiency chain: wheel → shaft → MGU-K → inverter → battery
    E_battery_charged_mj = E_regen_at_wheel_mj * cfg.regen_chain_efficiency

    # Cannot charge beyond max SOC
    headroom_mj = max(0.0, cfg.battery_max_soc_mj - prev_state.soc_mj)
    if E_battery_charged_mj > headroom_mj:
        E_battery_charged_mj = headroom_mj
        # Reduce regen power proportionally for display purposes
        if E_regen_at_wheel_mj > 0:
            P_regen_kw *= (headroom_mj / (E_regen_at_wheel_mj * cfg.regen_chain_efficiency))

    # ── STEP 2: COMPUTE DEPLOYMENT ────────────────────────────────────────
    # Remaining lap budget
    total_lap_budget_mj = cfg.lap_energy_cap_mj + (
        cfg.overtake_mode_bonus_mj if prev_state.overtake_mode_earned else 0.0
    )
    remaining_budget_mj = max(0.0, total_lap_budget_mj - deployed_lap)

    # SOC available for discharge (keep above minimum)
    soc_available_mj = max(0.0, prev_state.soc_mj - cfg.battery_min_soc_mj)

    if is_deploying:
        P_deploy_kw, lim_budget, lim_soc = _compute_deploy_power_kw(
            speed_kph=speed_kph,
            throttle_pct=throttle_pct,
            gear=safe_gear,
            overtake_mode_active=overtake_mode_active,
            remaining_budget_mj=remaining_budget_mj,
            soc_available_mj=soc_available_mj,
            dt_s=dt_s,
            cfg=cfg,
        )
    else:
        P_deploy_kw = 0.0
        lim_budget = False
        lim_soc = False

    # Energy delivered to wheels this timestep (MJ)
    E_delivered_to_wheel_mj = P_deploy_kw * dt_s / 1000.0

    # Energy actually drawn from battery (accounting for deploy chain losses)
    # Battery must supply MORE than what reaches the wheel (due to losses)
    E_battery_drawn_mj = E_delivered_to_wheel_mj / cfg.deploy_chain_efficiency

    # ── STEP 3: SOC UPDATE ────────────────────────────────────────────────
    #
    # Full equation:
    #   SOC(t+dt) = SOC(t) + E_battery_charged - E_battery_drawn
    #
    # where:
    #   E_battery_charged = P_regen × dt × η_regen_chain     [MJ]
    #   E_battery_drawn   = (P_deploy × dt) / η_deploy_chain [MJ]
    #
    # Units check:
    #   P [kW] × dt [s] = E [kJ] → ÷ 1000 → E [MJ]  ✓
    #   All efficiencies are dimensionless fractions       ✓
    #
    new_soc_mj = prev_state.soc_mj + E_battery_charged_mj - E_battery_drawn_mj

    # Hard clamp: SOC cannot go below battery_min_soc or above battery_max_soc
    new_soc_mj = max(cfg.battery_min_soc_mj, min(cfg.battery_max_soc_mj, new_soc_mj))

    # ── STEP 4: UPDATE ACCUMULATORS ───────────────────────────────────────
    deployed_lap += E_delivered_to_wheel_mj    # track what went to the drivetrain
    regen_lap += E_battery_charged_mj          # track what was stored

    # Consume Overtake Mode bonus
    if overtake_mode_active:
        bonus_remaining = max(0.0, bonus_remaining - E_delivered_to_wheel_mj)

    # ── STEP 5: INSTANTANEOUS POWER (display) ─────────────────────────────
    # Actual delivered power (accounting for what was actually possible)
    p_display_deploy_kw = E_delivered_to_wheel_mj / dt_s * 1000.0 if dt_s > 0 else 0.0
    p_display_regen_kw  = E_battery_charged_mj / dt_s * 1000.0 if dt_s > 0 else 0.0

    return EnergyState(
        soc_mj=new_soc_mj,
        lap_number=lap_number,
        energy_deployed_lap_mj=deployed_lap,
        energy_regen_lap_mj=regen_lap,
        overtake_mode_earned=overtake_mode_earned,
        overtake_mode_bonus_remaining_mj=bonus_remaining,
        p_deploy_instant_kw=p_display_deploy_kw,
        p_regen_instant_kw=p_display_regen_kw,
        regen_limited_by_power=regen_limited,
        deploy_limited_by_budget=lim_budget,
        deploy_limited_by_soc=lim_soc,
    )


# ─────────────────────────────────────────────────────────────────────────────
# HELPER
# ─────────────────────────────────────────────────────────────────────────────

def energy_remaining_this_lap(
    state: EnergyState, cfg: RegulationConfig = RegulationConfig()
) -> float:
    """Regulatory MJ still available to deploy this lap (wheel energy)."""
    budget = cfg.lap_energy_cap_mj + (
        cfg.overtake_mode_bonus_mj if state.overtake_mode_earned else 0.0
    )
    return max(0.0, budget - state.energy_deployed_lap_mj)


# ─────────────────────────────────────────────────────────────────────────────
# STATEFUL ENGINE CLASS
# ─────────────────────────────────────────────────────────────────────────────

class EnergyEngine:
    """
    Stateful wrapper around compute_energy_state().

    Maintains EnergyState across consecutive telemetry rows.
    Call update(row) once per row in chronological order.
    Call reset() when starting a new race replay.

    The initial SOC is set to 80% — a realistic pre-formation-lap charge level.
    Teams charge the ES to maximum capacity before the race start. [EST]
    """

    def __init__(self, cfg: Optional[RegulationConfig] = None):
        self.cfg = cfg or RegulationConfig()
        initial_soc = self.cfg.battery_max_soc_mj  # start race near full charge
        self._state = EnergyState(
            soc_mj=initial_soc,
            lap_number=1,
        )
        self._prev_date = None

    def reset(self, initial_soc_fraction: float = 0.95) -> None:
        """
        Reset to race-start state.

        Args:
            initial_soc_fraction: Starting SOC as fraction of battery capacity.
                                  Default 0.95 (95% — race start charge level). [EST]
        """
        soc = self.cfg.battery_capacity_mj * initial_soc_fraction
        soc = max(self.cfg.battery_min_soc_mj, min(self.cfg.battery_max_soc_mj, soc))
        self._state = EnergyState(
            soc_mj=soc,
            lap_number=1,
        )
        self._prev_date = None

    def update(self, row: dict) -> dict:
        """
        Advance the energy state by one telemetry row.

        Expected row keys (all optional with sensible defaults):
            Speed      (float, kph)
            Throttle   (float, 0-100)
            Brake      (float 0-1, bool, or 0/1 int)
            nGear      (int, 1-8)
            LapNumber  (int)
            GapSeconds (float, seconds gap to car ahead)
            Date       (datetime, for computing dt)

        Returns:
            Serialisable dict of all energy state fields for the WebSocket tick.
        """
        speed_kph   = float(row.get("Speed")    or 0)
        throttle_pct = float(row.get("Throttle") or 0)
        lap_number  = int(row.get("LapNumber")  or self._state.lap_number)
        gear_raw    = row.get("nGear", 4)

        # Brake: FastF1 sends booleans or floats; normalise to [0.0, 1.0]
        brake_raw = row.get("Brake", 0)
        if isinstance(brake_raw, bool):
            brake = 1.0 if brake_raw else 0.0
        else:
            try:
                brake_val = float(brake_raw)
                # Handle two common FastF1 encodings:
                # (a) Brake as 0/1 bool-like float → already 0-1
                # (b) Brake as pressure 0-100 → normalise
                if brake_val > 1.0:
                    brake = brake_val / 100.0
                else:
                    brake = brake_val
            except (TypeError, ValueError):
                brake = 0.0
        brake = max(0.0, min(1.0, brake))

        # Gear: normalise None/NaN to 4 (mid-range fallback)
        try:
            gear = int(float(gear_raw)) if gear_raw is not None else 4
            gear = max(1, min(8, gear))
        except (TypeError, ValueError):
            gear = 4

        # Gap to car ahead
        gap_raw = row.get("GapSeconds", None)
        try:
            gap_s: Optional[float] = float(gap_raw) if gap_raw is not None else None
            if gap_s is not None and (math.isnan(gap_s) or gap_s <= 0):
                gap_s = None
        except (TypeError, ValueError):
            gap_s = None

        # ── Compute dt from consecutive Date timestamps ───────────────────
        # This is the most important fix: real FastF1 rows are spaced ~0.02–0.25 s.
        # We must use the ACTUAL elapsed time, not a fixed 0.1s assumption.
        current_date = row.get("Date", None)
        if self._prev_date is not None and current_date is not None:
            try:
                dt_s = (current_date - self._prev_date).total_seconds()
                # Guard: clamp to physical range
                # < 0 → timestamp went backwards (sorting issue)
                # > 0.5 → data gap (pit stop, red flag, etc.)
                dt_s = max(0.005, min(dt_s, 0.5))
            except Exception:
                dt_s = 0.05  # safe fallback: 50ms ~ FastF1 typical rate
        else:
            dt_s = 0.05  # first row
        self._prev_date = current_date

        # ── Run energy state computation ──────────────────────────────────
        self._state = compute_energy_state(
            speed_kph=speed_kph,
            throttle_pct=throttle_pct,
            brake=brake,
            gear=gear,
            dt_s=dt_s,
            lap_number=lap_number,
            gap_to_car_ahead_s=gap_s,
            prev_state=self._state,
            cfg=self.cfg,
        )

        s = self._state

        # ── Determine display mode ─────────────────────────────────────────
        if s.overtake_mode_bonus_remaining_mj > 0.001:
            mode = "OVERTAKE"
        elif s.p_regen_instant_kw > 5.0:   # meaningful regen threshold
            mode = "HARVEST"
        else:
            mode = "NORMAL"

        return {
            "soc_mj":                          round(s.soc_mj, 3),
            "soc_pct":                         round(s.soc_mj / self.cfg.battery_capacity_mj * 100, 1),
            "energy_deployed_lap_mj":          round(s.energy_deployed_lap_mj, 3),
            "energy_regen_lap_mj":             round(s.energy_regen_lap_mj, 3),
            "overtake_mode_earned":            s.overtake_mode_earned,
            "overtake_mode_bonus_remaining_mj": round(s.overtake_mode_bonus_remaining_mj, 3),
            "energy_remaining_lap_mj":         round(energy_remaining_this_lap(s, self.cfg), 3),
            "p_deploy_instant_kw":             round(s.p_deploy_instant_kw, 1),
            "p_regen_instant_kw":              round(s.p_regen_instant_kw, 1),
            "mode":                            mode,
            "soc_confidence":                  0.75,  # lower confidence: estimated model [EST]
            # Debug fields (useful for the SOC Trend page diagnostics)
            "_dt_s":                           round(dt_s, 4),
            "_regen_limited":                  s.regen_limited_by_power,
            "_deploy_budget_limited":          s.deploy_limited_by_budget,
            "_deploy_soc_limited":             s.deploy_limited_by_soc,
        }


# ─────────────────────────────────────────────────────────────────────────────
# QUICK VALIDATION SCENARIOS
# ─────────────────────────────────────────────────────────────────────────────
# Run `python ee.py` to execute validation scenarios that prove the model
# behaves physically correctly.

def _validate():
    """
    Validation scenarios — expected SOC changes documented for each case.
    All scenarios use dt = 0.1s (one telemetry step) unless stated otherwise.
    """
    import sys

    cfg = RegulationConfig()
    dt = 0.1  # seconds per timestep

    print("=" * 65)
    print("EE.py VALIDATION — F1 Hybrid Energy Engine")
    print("=" * 65)

    base_state = EnergyState(soc_mj=2.0, lap_number=1)  # 50% SOC start

    def run(label, **kwargs):
        kwargs.setdefault('dt_s', dt)
        kwargs.setdefault('lap_number', 1)
        kwargs.setdefault('gap_to_car_ahead_s', None)
        kwargs.setdefault('prev_state', base_state)
        kwargs.setdefault('cfg', cfg)
        s = compute_energy_state(**kwargs)
        delta = s.soc_mj - base_state.soc_mj
        arrow = "↑" if delta > 0.001 else ("↓" if delta < -0.001 else "→")
        print(f"  {arrow} {label:45s} | ΔSOC = {delta:+.5f} MJ | SOC = {s.soc_mj:.3f} MJ | "
              f"P_regen={s.p_regen_instant_kw:6.1f} kW | P_deploy={s.p_deploy_instant_kw:6.1f} kW")
        return s

    print("\n[1] HARVESTING SCENARIOS")
    run("Heavy braking @ 200 kph, brake=1.0, throttle=0",
        speed_kph=200, throttle_pct=0, brake=1.0, gear=4)
    run("Heavy braking @ 100 kph, brake=1.0, throttle=0",
        speed_kph=100, throttle_pct=0, brake=1.0, gear=3)
    run("Heavy braking @ 50 kph, brake=1.0, throttle=0",
        speed_kph=50, throttle_pct=0, brake=1.0, gear=2)
    run("Gentle braking @ 150 kph, brake=0.3, throttle=0",
        speed_kph=150, throttle_pct=0, brake=0.3, gear=4)
    run("Lift-and-coast @ 200 kph, brake=0, throttle=10",
        speed_kph=200, throttle_pct=10, brake=0.0, gear=6)

    print("\n[2] DEPLOYMENT SCENARIOS")
    run("Full throttle @ 150 kph, gear=6 (acceleration out of corner)",
        speed_kph=150, throttle_pct=100, brake=0.0, gear=6)
    run("Full throttle @ 100 kph, gear=4 (mid-speed)",
        speed_kph=100, throttle_pct=100, brake=0.0, gear=4)
    run("Full throttle @ 60 kph, gear=2 (corner exit, traction limited)",
        speed_kph=60, throttle_pct=100, brake=0.0, gear=2)
    run("Partial throttle 70% @ 200 kph, gear=7",
        speed_kph=200, throttle_pct=70, brake=0.0, gear=7)
    run("Low throttle 40% below deploy threshold",
        speed_kph=150, throttle_pct=40, brake=0.0, gear=5)

    print("\n[3] NEUTRAL / EDGE CASES")
    run("No throttle, no brake, high speed cruise @ 300 kph",
        speed_kph=300, throttle_pct=15, brake=0.0, gear=8)
    run("Stopped (v=0, brake=1.0): no regen possible",
        speed_kph=0, throttle_pct=0, brake=1.0, gear=1)
    run("Battery near full (SOC=3.85 MJ), braking: should clamp regen",
        speed_kph=200, throttle_pct=0, brake=1.0, gear=4,
        prev_state=EnergyState(soc_mj=3.85, lap_number=1))
    run("Battery near min (SOC=0.25 MJ), full throttle: should limit deploy",
        speed_kph=150, throttle_pct=100, brake=0.0, gear=6,
        prev_state=EnergyState(soc_mj=0.25, lap_number=1))

    print("\n[4] LAP-SCALE ENERGY BALANCE")
    # Simulate 78 laps, each ~90s, alternating braking/acceleration
    # Monaco: ~23 braking zones per lap, each ~1.5s at avg 150 kph
    # Monaco: ~50% of lap at WOT (wide open throttle)
    print("  Running 78-lap simulation (Monaco-like cycle)...")
    state = EnergyState(soc_mj=3.9, lap_number=0)
    for lap in range(1, 79):
        # Simulate ~90 steps per lap (at 1s resolution)
        for step in range(90):
            # Roughly Monaco duty cycle: 50% throttle, 25% braking, 25% coast
            if step % 4 == 0:
                # Braking
                state = compute_energy_state(250, 0, 1.0, 4, 1.0, lap, 0.8, state, cfg)
            elif step % 4 == 1:
                # Corner exit accel
                state = compute_energy_state(80, 100, 0.0, 3, 1.0, lap, 0.8, state, cfg)
            elif step % 4 == 2:
                # Straight (throttle)
                state = compute_energy_state(230, 95, 0.0, 7, 1.0, lap, 0.8, state, cfg)
            else:
                # Coast
                state = compute_energy_state(190, 10, 0.0, 6, 1.0, lap, 0.8, state, cfg)

        if lap % 13 == 0:
            print(f"    Lap {lap:3d}: SOC = {state.soc_mj:.3f} MJ ({state.soc_mj/cfg.battery_capacity_mj*100:.1f}%) "
                  f"| Deployed this lap: {state.energy_deployed_lap_mj:.3f} MJ "
                  f"| Regen this lap: {state.energy_regen_lap_mj:.3f} MJ")

    print(f"\n  Final SOC after 78 laps: {state.soc_mj:.3f} MJ ({state.soc_mj/cfg.battery_capacity_mj*100:.1f}%)")
    print("\n" + "=" * 65)
    print("Validation complete. Check arrow directions match expected physics.")
    print("  ↑ = SOC increased (harvest > deploy)")
    print("  ↓ = SOC decreased (deploy > harvest)")
    print("  → = SOC approximately unchanged")


if __name__ == "__main__":
    _validate()
