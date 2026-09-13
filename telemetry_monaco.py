# telemetry_monaco.py — FastF1 Monaco GP telemetry loader with local caching
"""
Loads Monaco Grand Prix race telemetry for supported years via the FastF1
library and caches the processed result locally so subsequent loads are fast.

Cache location: ./telemetry_cache/monaco_{year}.pkl
FastF1 API cache: ./ff1_cache/
"""

import os
import warnings
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')  # suppress FastF1 FutureWarning noise

SUPPORTED_YEARS = {2018, 2019, 2021, 2022, 2023, 2024}
CIRCUIT = 'Monaco'
CIRCUIT_LENGTH_M = 3337.0   # Monaco GP circuit length in metres
FF1_CACHE_DIR = './ff1_cache'
TELEMETRY_CACHE_DIR = './telemetry_cache'


def _darken_color(hex_color: str) -> str:
    """Return a darkened version of a hex color for car accent/shadow."""
    try:
        h = hex_color.lstrip('#')
        if len(h) != 6:
            return '#444444'
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        r, g, b = int(r * 0.5), int(g * 0.5), int(b * 0.5)
        return f'#{r:02x}{g:02x}{b:02x}'
    except Exception:
        return '#444444'


def _build_driver_info(session) -> dict:
    """Extract driver/team metadata from the FastF1 session."""
    info = {}
    for drv in session.laps['Driver'].unique():
        try:
            d = session.get_driver(drv)
            color = str(d.get('TeamColor', '888888') or '888888')
            if not color.startswith('#'):
                color = '#' + color
            info[drv] = {
                'code': drv,
                'full_name': str(d.get('FullName', drv) or drv),
                'team': str(d.get('TeamName', '') or ''),
                'color': color,
                'accent': _darken_color(color),
                'number': int(d.get('DriverNumber', 0) or 0),
            }
        except Exception:
            info[drv] = {
                'code': drv,
                'full_name': drv,
                'team': '',
                'color': '#888888',
                'accent': '#444444',
                'number': 0,
            }
    return info


def _build_driver_telemetry(session, drv: str) -> Optional[pd.DataFrame]:
    """
    Build a chronologically sorted telemetry DataFrame for one driver,
    spanning all their laps.

    Columns returned:
        Date, DateNS, Distance, Progress, Speed, Throttle, Brake,
        nGear, RPM, DRS, LapNumber, Position, GapSeconds,
        DistanceToDriverAhead, DriverAhead
    """
    rows = []
    drv_laps = session.laps.pick_drivers(drv).sort_values('LapNumber')
    for _, lap in drv_laps.iterlaps():
        try:
            tel = lap.get_car_data().add_distance()
            tel = tel.add_driver_ahead()
        except Exception:
            continue

        # Gap to car ahead in seconds
        tel['GapSeconds'] = (
            tel['DistanceToDriverAhead'] / tel['Speed'].clip(lower=1) * 3.6
        )

        # Track progress 0–1 along the Monaco circuit
        tel['Progress'] = (tel['Distance'] % CIRCUIT_LENGTH_M) / CIRCUIT_LENGTH_M

        # Lap metadata
        tel['Driver'] = drv
        tel['LapNumber'] = int(lap['LapNumber'])
        pos = lap.get('Position', None)
        try:
            tel['Position'] = int(pos) if pos is not None and not np.isnan(float(pos)) else 20
        except Exception:
            tel['Position'] = 20

        rows.append(tel)

    if not rows:
        return None

    merged = pd.concat(rows, ignore_index=True)

    # Sort chronologically using the absolute Date column
    if 'Date' in merged.columns:
        merged = merged.sort_values('Date').reset_index(drop=True)

    # Integer nanosecond timestamps for fast numpy searchsorted
    merged['DateNS'] = merged['Date'].values.astype('int64')

    return merged


def load_monaco_session(year: int) -> dict:
    """
    Load all driver telemetry for a Monaco GP year.

    Returns a dict with:
        year, circuit, total_laps, drivers (list), driver_info (dict),
        driver_telemetry (dict of DataFrames), num_to_code (dict)

    On the first call for a year this downloads data via FastF1 (~30–120s).
    Subsequent calls load from the local cache (~1s).

    Raises:
        ValueError: if year is not in SUPPORTED_YEARS.
    """
    if year not in SUPPORTED_YEARS:
        raise ValueError(
            f"Year {year} is not supported. Supported Monaco GP years: "
            f"{sorted(SUPPORTED_YEARS)}"
        )

    os.makedirs(TELEMETRY_CACHE_DIR, exist_ok=True)
    cache_path = os.path.join(TELEMETRY_CACHE_DIR, f'monaco_{year}.pkl')

    if os.path.exists(cache_path):
        print(f'[telemetry_monaco] Loading cached Monaco {year} telemetry...')
        return pd.read_pickle(cache_path)

    print(f'[telemetry_monaco] Downloading Monaco {year} via FastF1...')

    # Import here so the module is importable even if fastf1 is slow to start
    import fastf1
    os.makedirs(FF1_CACHE_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(FF1_CACHE_DIR)

    session = fastf1.get_session(year, CIRCUIT, 'R')
    session.load(telemetry=True, laps=True, weather=False)

    driver_info = _build_driver_info(session)

    # Build per-driver telemetry
    driver_telemetry = {}
    for drv in session.laps['Driver'].unique():
        print(f'  Processing driver {drv}...')
        tel = _build_driver_telemetry(session, drv)
        if tel is not None and len(tel) > 0:
            driver_telemetry[drv] = tel

    total_laps = int(session.laps['LapNumber'].max())

    # Driver number (string) → code mapping (for resolving DriverAhead field)
    num_to_code = {}
    for drv, info in driver_info.items():
        num_to_code[str(info.get('number', ''))] = drv
        num_to_code[drv] = drv  # also map code → code for safety

    data = {
        'year': year,
        'circuit': CIRCUIT,
        'total_laps': total_laps,
        'drivers': sorted(driver_telemetry.keys()),
        'driver_info': driver_info,
        'driver_telemetry': driver_telemetry,
        'num_to_code': num_to_code,
    }

    print(f'[telemetry_monaco] Caching Monaco {year} telemetry to {cache_path}...')
    pd.to_pickle(data, cache_path)
    print(f'[telemetry_monaco] Done. {len(driver_telemetry)} drivers loaded.')

    return data


def get_drivers_for_year(year: int) -> list:
    """
    Return driver metadata for a year without loading full telemetry.
    Uses the cache if available, otherwise loads laps-only from FastF1 (fast).

    Returns:
        List of dicts: [{code, full_name, team, color, accent, number}, ...]
    """
    if year not in SUPPORTED_YEARS:
        raise ValueError(f"Year {year} is not supported.")

    # If full cache exists, use it (already has driver_info)
    cache_path = os.path.join(TELEMETRY_CACHE_DIR, f'monaco_{year}.pkl')
    if os.path.exists(cache_path):
        data = pd.read_pickle(cache_path)
        return list(data['driver_info'].values())

    # Otherwise load session with laps only (no telemetry) — much faster
    import fastf1
    os.makedirs(FF1_CACHE_DIR, exist_ok=True)
    fastf1.Cache.enable_cache(FF1_CACHE_DIR)
    session = fastf1.get_session(year, CIRCUIT, 'R')
    session.load(telemetry=False, laps=True, weather=False)
    info = _build_driver_info(session)
    return list(info.values())


def find_nearest_row(drv_data: pd.DataFrame, target_date_ns: int) -> Optional[pd.Series]:
    """
    Binary-search for the telemetry row closest to target_date_ns (int64 ns).
    O(log n) — safe to call for every driver on every tick.
    """
    if drv_data is None or len(drv_data) == 0:
        return None
    dates = drv_data['DateNS'].values
    idx = int(np.searchsorted(dates, target_date_ns))
    idx = max(0, min(idx, len(drv_data) - 1))
    return drv_data.iloc[idx]
