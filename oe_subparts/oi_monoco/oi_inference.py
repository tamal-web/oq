import time
from pathlib import Path
import pandas as pd
import joblib

FEATURE_COLS = ['Speed', 'Throttle', 'Brake', 'nGear', 'RPM', 'DRS', 'GapSeconds', 'LapNumber']
OVERTAKE_TRIGGER_GAP = 2.0  # seconds — configurable gap threshold

_MODEL_PATH = Path(__file__).parent / 'overtake_model_monaco.pkl'


def load_oi_model():
    """Load the trained OI RandomForestClassifier from disk."""
    return joblib.load(_MODEL_PATH)


def predict_row(row: dict, model) -> tuple[bool, str]:
    """
    Run OI inference for a single telemetry row.

    LapNumber leakage fix:
    The trained RandomForest has 67.7% feature importance on LapNumber,
    meaning it memorised *which laps* overtakes happened in training rather
    than learning physics. At inference we replace LapNumber with the
    median training-set value (38) so the model decides based on Speed,
    DRS, GapSeconds etc. Re-training with LapNumber excluded is the
    long-term fix.

    Args:
        row:   Dict containing at minimum the FEATURE_COLS keys.
        model: Loaded sklearn model (from load_oi_model()).

    Returns:
        (bool, str): (Prediction, Reason string)
    """
    try:
        gap = float(row.get('GapSeconds', float('nan')))
    except (TypeError, ValueError):
        return False, "Invalid gap data"

    if not (0 < gap <= OVERTAKE_TRIGGER_GAP):
        return False, "Gap outside trigger zone"

    try:
        vals = {}
        for col in FEATURE_COLS:
            v = row.get(col, None)
            if v is None:
                return False, f"Missing feature: {col}"
            try:
                fv = float(v)
                if fv != fv:  # NaN check
                    return False, f"NaN in feature: {col}"
                vals[col] = fv
            except (TypeError, ValueError):
                return False, f"Invalid feature: {col}"

        # Neutralise LapNumber data leakage: set to median so it contributes
        # no signal and the model relies on real features (DRS, Gap, Speed).
        vals['LapNumber'] = 38.0

        features = pd.DataFrame([vals])
        proba = model.predict_proba(features)[0]  # [P(no overtake), P(overtake)]
        p_overtake = float(proba[1])

        # Lower threshold from 0.5 → 0.30 to account for class imbalance.
        # The model's P(overtake) ranges from 0.20–0.59 with a mean of ~0.36
        # (after neutralising LapNumber). A threshold of 0.30 correctly selects
        # the top ~68% of scenarios by predicted probability.
        DECISION_THRESHOLD = 0.30
        if p_overtake >= DECISION_THRESHOLD:
            return True, f"OI P={p_overtake:.2f}"
        else:
            return False, f"OI P={p_overtake:.2f} < {DECISION_THRESHOLD:.2f}"
    except Exception as e:
        return False, f"Inference error: {e}"


def main():
    """Standalone replay demo — runs the 2024 Monaco GP through OI inference."""
    print("Loading model and telemetry...")
    model = load_oi_model()
    tel_path = Path(__file__).parent / 'telemetry_all.pkl'
    telemetry_all = pd.read_pickle(str(tel_path))

    replay_data = telemetry_all[telemetry_all['Year'] == 2024].sort_values('Time')
    print(f"Replaying {len(replay_data)} telemetry rows for the 2024 Monaco GP race...\n")

    prediction_count = 0
    for _, row in replay_data.iterrows():
        row_dict = row.to_dict()
        gap_raw = row_dict.get('GapSeconds', float('nan'))
        try:
            gap_val = float(gap_raw)
        except (TypeError, ValueError):
            continue
        if 0 < gap_val <= OVERTAKE_TRIGGER_GAP:
            pred, reason = predict_row(row_dict, model)
            prediction_count += 1
            print(
                f"Lap {int(row['LapNumber']):>3} | "
                f"{row['Driver']} | "
                f"Gap {gap_val:.2f}s | "
                f"Predicted overtake={pred} ({reason})"
            )
            time.sleep(0.001)

    print(f"\nDone. {prediction_count} decision-zone predictions printed.")


if __name__ == '__main__':
    main()
