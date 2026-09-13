import fastf1
import pandas as pd
import os

os.makedirs('./ff1_cache', exist_ok=True)
fastf1.Cache.enable_cache('./ff1_cache')

YEARS = [2022, 2023, 2024]
FEATURE_COLS = ['Speed', 'Throttle', 'Brake', 'nGear', 'RPM', 'DRS', 'GapSeconds', 'LapNumber']


def load_sessions():
    sessions = {}
    for year in YEARS:
        print(f"  Loading {year} Monaco Race session...")
        s = fastf1.get_session(year, 'Monaco', 'R')
        s.load(telemetry=True, laps=True, weather=False)
        sessions[year] = s
    return sessions


def build_telemetry(sessions):
    rows = []
    for year, session in sessions.items():
        print(f"  Building telemetry for {year}...")
        for drv in session.laps['Driver'].unique():
            for _, lap in session.laps.pick_driver(drv).iterlaps():
                try:
                    tel = lap.get_car_data().add_distance()
                    tel = tel.add_driver_ahead()
                except Exception:
                    continue
                # Guard against zero / missing speed
                tel['GapSeconds'] = tel['DistanceToDriverAhead'] / tel['Speed'].clip(lower=1) * 3.6
                tel['Driver'] = drv
                tel['Year'] = year
                tel['LapNumber'] = lap['LapNumber']
                rows.append(tel)
    if not rows:
        raise RuntimeError("No telemetry rows collected — check FastF1 data availability.")
    telemetry_all = pd.concat(rows, ignore_index=True)
    telemetry_all = telemetry_all[telemetry_all['DistanceToDriverAhead'].notna()]
    return telemetry_all


def filter_decision_zone(telemetry_all):
    df = telemetry_all[
        (telemetry_all['GapSeconds'] > 0) & (telemetry_all['GapSeconds'] <= 2.0)
    ].copy()
    df = df.dropna(subset=FEATURE_COLS)
    return df


def add_labels(df, sessions):
    labels = pd.Series(0, index=df.index, dtype='int')
    for year, session in sessions.items():
        for drv in session.laps['Driver'].unique():
            drv_laps = session.laps.pick_driver(drv).sort_values('LapNumber')
            pos_by_lap = dict(zip(drv_laps['LapNumber'], drv_laps['Position']))
            mask = (df['Year'] == year) & (df['Driver'] == drv)
            for lap_num, idx in df[mask].groupby('LapNumber').groups.items():
                pos_now = pos_by_lap.get(lap_num)
                pos_next = pos_by_lap.get(lap_num + 1)
                labels.loc[idx] = int(
                    pos_next is not None
                    and pos_now is not None
                    and pos_next < pos_now
                )
    df = df.copy()
    df['Overtook'] = labels
    return df


def main():
    print("Loading sessions...")
    sessions = load_sessions()

    print("Building telemetry...")
    telemetry_all = build_telemetry(sessions)

    # Save full telemetry (used later by inference for the 2024 replay)
    telemetry_all.to_pickle('telemetry_all.pkl')
    print(f"  Saved telemetry_all.pkl with {len(telemetry_all)} rows.")

    print("Filtering decision zone (gap <= 2 s)...")
    df = filter_decision_zone(telemetry_all)
    print(f"  Decision-zone rows: {len(df)}")

    print("Adding labels...")
    df = add_labels(df, sessions)

    # Save the clean, labeled training dataset
    df.to_pickle('training_dataset.pkl')
    print(
        f"\nSaved training_dataset.pkl with {len(df)} rows "
        f"and telemetry_all.pkl with {len(telemetry_all)} rows."
    )
    print(f"Label distribution:\n{df['Overtook'].value_counts()}")


if __name__ == '__main__':
    main()
