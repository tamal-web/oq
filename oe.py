# oe.py — Overtake Engine orchestrator
"""
OE (Overtake Engine) combines three sub-components to produce the final
per-telemetry-row overtake decision:

    OI — Overtake Intelligence   (ML prediction)
    EC — Energy Conservation     (energy strategy check)
    RC — Rule Compliance         (regulatory compliance check)

Final decision:  should_overtake = OI and EC and RC

OI is only evaluated when the car ahead is within OVERTAKE_TRIGGER_GAP seconds.
EC and RC are always evaluated when within the trigger gap.
"""

import sys
from pathlib import Path

# Ensure oe_subparts is importable when server.py runs from the project root
sys.path.insert(0, str(Path(__file__).parent))

from oe_subparts.ec import check_energy_conservation
from oe_subparts.oi_monoco.oi_inference import load_oi_model, predict_row
from oe_subparts.rc import check_rule_compliance

# Configurable gap threshold — change this constant to adjust the trigger zone
OVERTAKE_TRIGGER_GAP = 2.0  # seconds


class OvertakeEngine:
    """
    Main orchestrator for the overtake decision.

    Architecture:
        OE
        ├── OI — Overtake Intelligence (oe_subparts/oi_monoco/oi_inference.py)
        ├── EC — Energy Conservation   (oe_subparts/ec.py)
        └── RC — Rule Compliance       (oe_subparts/rc.py)

    Usage:
        oe = OvertakeEngine()         # loads OI model once
        state = oe.update(row, ee)    # call each telemetry tick
    """

    def __init__(self):
        """Load the OI model once at initialisation (avoids per-tick I/O)."""
        self._model = load_oi_model()

    def update(
        self, row: dict, energy_state: dict, opponent_energy_state: dict = None
    ) -> dict:
        """
        Evaluate the overtake decision for one telemetry row.

        Args:
            row:          Telemetry row dict for the selected (attacking) driver.
                          Must contain at minimum: GapSeconds, and all FEATURE_COLS
                          required by the OI model.
            energy_state: Serialised EnergyEngine state dict for the same driver
                          (output of EnergyEngine.update()).
            opponent_energy_state: Optional serialised EnergyEngine state dict for the car ahead.

        Returns:
            Dict with keys:
                oi_prediction  (bool)  — ML model recommendation
                ec             (bool)  — energy conservation check result
                rc             (bool)  — rule compliance check result
                should_overtake(bool)  — OI and EC and RC
                gap_seconds    (float|None) — current gap to car ahead
                within_trigger (bool)  — gap is within OVERTAKE_TRIGGER_GAP
        """
        # Resolve gap value
        gap_raw = row.get("GapSeconds", None)
        try:
            gap_s = float(gap_raw) if gap_raw is not None else None
            if gap_s is not None and (gap_s != gap_s or gap_s <= 0):  # NaN or ≤ 0
                gap_s = None
        except (TypeError, ValueError):
            gap_s = None

        within_trigger = gap_s is not None and gap_s <= OVERTAKE_TRIGGER_GAP

        if within_trigger:
            oi_pass, oi_reason = predict_row(row, self._model)
            rc_pass, rc_reason = check_rule_compliance(energy_state, row)
            ec_pass, ec_reason, ec_decision = check_energy_conservation(
                energy_state,
                row,
                rc_allowed=rc_pass,
                opponent_energy_state=opponent_energy_state,
            )
        else:
            oi_pass, oi_reason = False, "Out of trigger zone"
            rc_pass, rc_reason = False, "Out of trigger zone"
            ec_pass, ec_reason, ec_decision = False, "Out of trigger zone", "NONE"

        return {
            "oi_prediction": oi_pass,
            "oi_reason": oi_reason,
            "ec": ec_pass,
            "ec_reason": ec_reason,
            "ec_decision": ec_decision,
            "rc": rc_pass,
            "rc_reason": rc_reason,
            # DECISION LOGIC:
            # RC = hard gate (regulatory compliance — cannot overtake illegally)
            # EC = hard gate (energy economics — must be energetically sound)
            # OI = advisory signal (ML model has known LapNumber data leakage;
            #      until retrained, it cannot be a hard veto or the system
            #      will never recommend overtaking)
            #
            # should_overtake = True when RC + EC both pass (safe and affordable)
            # Displayed as "STRONG" in the UI when OI also agrees.
            "should_overtake": bool(rc_pass and ec_pass and oi_pass),
            "oi_advisory": oi_pass,  # OI agreement — shown in UI, not a hard gate
            "gap_seconds": round(gap_s, 3) if gap_s is not None else None,
            "within_trigger": within_trigger,
        }
