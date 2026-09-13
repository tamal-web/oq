# server.py — F1 Overtake Intelligence WebSocket server
"""
FastAPI backend that streams Monaco GP race replays over WebSockets.

Endpoints:
    GET  /              — service info
    GET  /races         — supported Monaco GP years
    GET  /drivers/{year} — driver list for a year
    WS   /ws/race/{year}/{driver} — race replay stream

WebSocket protocol (server → client):
    {"type": "status",   "status": "loading"|"ready", "message": "...", ...}
    {"type": "tick",     "session_time_s": float, "race": {...}, "energy": {...}, "overtake": {...}}
    {"type": "finished"}
    {"type": "error",    "message": "..."}

WebSocket protocol (client → server):
    {"type": "set_speed", "speed": float}
    {"type": "pause"}
    {"type": "resume"}
"""

import asyncio
import math
from typing import Optional

import numpy as np
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ee import EnergyEngine
from oe import OvertakeEngine
from telemetry_monaco import (
    SUPPORTED_YEARS,
    load_monaco_session,
    get_drivers_for_year,
    find_nearest_row,
)

# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(title='F1 Overtake Intelligence', version='1.0.0')

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        'http://localhost:5173',
        'http://127.0.0.1:5173',
        'http://localhost:5174',
        'http://127.0.0.1:5174',
        'http://localhost:5175',
        'http://127.0.0.1:5175',
        'http://localhost:3000',
        'http://127.0.0.1:3000',
    ],
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)

MONACO_ONLY_MESSAGE = (
    f'Only Monaco Grand Prix races are supported. '
    f'Supported years: {sorted(SUPPORTED_YEARS)}'
)


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get('/')
def root():
    return {
        'service': 'F1 Overtake Intelligence',
        'circuit': 'Monaco Grand Prix',
        'supported_years': sorted(SUPPORTED_YEARS),
        'note': 'OI model trained exclusively on Monaco GP 2022–2024 data.',
    }


@app.get('/races')
def get_races():
    return {
        'circuit': 'Monaco Grand Prix',
        'years': sorted(SUPPORTED_YEARS),
    }


@app.get('/drivers/{year}')
async def get_drivers(year: int):
    if year not in SUPPORTED_YEARS:
        raise HTTPException(status_code=400, detail=MONACO_ONLY_MESSAGE)
    loop = asyncio.get_event_loop()
    try:
        drivers = await loop.run_in_executor(None, get_drivers_for_year, year)
        return {'year': year, 'circuit': 'Monaco Grand Prix', 'drivers': drivers}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── WebSocket replay ──────────────────────────────────────────────────────────

def _safe_float(val, default=None):
    """Convert a value to float, returning default on failure."""
    if val is None:
        return default
    try:
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (TypeError, ValueError):
        return default


def _safe_int(val, default=0):
    try:
        return int(val)
    except (TypeError, ValueError):
        return default


async def _replay_loop(
    ws: WebSocket,
    session_data: dict,
    driver: str,
    speed_ctrl: list,   # [float] — mutable speed reference
    paused_ctrl: list,  # [bool]  — mutable pause reference
) -> None:
    """
    Core replay loop: iterates through the selected driver's telemetry,
    updates EE + OE each tick, and streams the combined state over WebSocket.
    """
    drv_tel = session_data['driver_telemetry'][driver]
    all_drivers: dict = session_data['driver_telemetry']
    driver_info: dict = session_data['driver_info']
    num_to_code: dict = session_data['num_to_code']
    total_laps: int = session_data['total_laps']

    oe = OvertakeEngine()

    # Session start reference for session_time_s computation
    session_start = drv_tel['Date'].iloc[0] if len(drv_tel) > 0 else None

    n = len(drv_tel)
    ee = EnergyEngine()  # keep for fallback, but we'll use all_engines
    all_engines = {d: EnergyEngine() for d in all_drivers}

    prev_date_ns: Optional[int] = None

    for i in range(n):
        # ── Pause handling ────────────────────────────────────────────────
        while paused_ctrl[0]:
            await asyncio.sleep(0.05)

        row_series = drv_tel.iloc[i]
        row_dict = row_series.to_dict()

        # ── Session time ─────────────────────────────────────────────────
        session_time_s: Optional[float] = None
        if session_start is not None:
            try:
                session_time_s = round(
                    (row_series['Date'] - session_start).total_seconds(), 2
                )
            except Exception:
                pass

        current_date_ns = int(row_series['DateNS'])

        da_raw = row_dict.get('DriverAhead', None)
        car_ahead_code = num_to_code.get(str(da_raw), da_raw) if da_raw else None

        energy_state = None
        opponent_energy_state = None

        # ── Locate all other drivers at this moment ───────────────────────
        cars = []
        for drv_code, drv_data in all_drivers.items():
            near = find_nearest_row(drv_data, current_date_ns)
            if near is None:
                continue
            
            near_dict = near.to_dict()
            # Update their specific energy engine
            drv_energy = all_engines[drv_code].update(near_dict)
            
            if drv_code == driver:
                energy_state = drv_energy
            elif drv_code == car_ahead_code:
                opponent_energy_state = drv_energy

            info = driver_info.get(drv_code, {'code': drv_code, 'color': '#888888', 'accent': '#444444', 'number': 0, 'full_name': drv_code})
            progress = _safe_float(near.get('Progress'), 0.0)
            lap = _safe_int(near.get('LapNumber'), 1)
            position = _safe_int(near.get('Position'), 20)
            cars.append({
                'code': drv_code,
                'progress': progress,
                'lap': lap,
                'color': info.get('color', '#888888'),
                'accent': info.get('accent', '#444444'),
                'number': info.get('number', 0),
                'full_name': info.get('full_name', drv_code),
                'is_selected': drv_code == driver,
            })

        # Dynamically calculate live position based on total distance covered (lap + progress)
        # Note: we use (lap - 1) + progress to represent total continuous laps covered.
        cars.sort(key=lambda c: (c['lap'] - 1) + c['progress'], reverse=True)
        
        for rank, c in enumerate(cars):
            c['position'] = rank + 1

        # Fallback if the selected driver's row wasn't found in the synchronous loop
        if energy_state is None:
            energy_state = all_engines[driver].update(row_dict)

        # ── Overtake Engine update ────────────────────────────────────────
        oe_state = oe.update(row_dict, energy_state, opponent_energy_state=opponent_energy_state)

        # ── Race state ────────────────────────────────────────────────────
        race_state = {
            'selected_driver': driver,
            'lap': _safe_int(row_dict.get('LapNumber'), 1),
            'total_laps': total_laps,
            'cars': cars,
            'car_ahead_code': car_ahead_code,
            'gap_to_ahead_s': _safe_float(row_dict.get('GapSeconds')),
        }

        # ── Send WebSocket tick ───────────────────────────────────────────
        try:
            await ws.send_json({
                'type': 'tick',
                'session_time_s': session_time_s,
                'race': race_state,
                'energy': energy_state,
                'opponent_energy': opponent_energy_state,
                'overtake': oe_state,
            })
        except Exception:
            return  # client disconnected

        # ── Timing: sleep for real dt / replay speed ──────────────────────
        if prev_date_ns is not None:
            dt_ns = current_date_ns - prev_date_ns
            dt_s = max(0.01, min(dt_ns / 1e9, 1.0))
        else:
            dt_s = 0.1

        prev_date_ns = current_date_ns
        speed = max(0.1, speed_ctrl[0])
        await asyncio.sleep(dt_s / speed)

    # Race replay complete
    try:
        await ws.send_json({'type': 'finished'})
    except Exception:
        pass


@app.websocket('/ws/race/{year}/{driver}')
async def websocket_race(ws: WebSocket, year: int, driver: str):
    """
    WebSocket endpoint for Monaco GP race replay.

    Validates that the requested year is a supported Monaco GP.
    Streams one tick message per telemetry row (~10 Hz real-time).
    Accepts speed and pause/resume control messages from the client.
    """
    await ws.accept()

    # ── Monaco-only validation ────────────────────────────────────────────
    if year not in SUPPORTED_YEARS:
        await ws.send_json({
            'type': 'error',
            'message': MONACO_ONLY_MESSAGE,
        })
        await ws.close(code=4000)
        return

    # ── Load telemetry (blocking I/O → thread executor) ───────────────────
    import os
    from telemetry_monaco import TELEMETRY_CACHE_DIR
    cache_path = os.path.join(TELEMETRY_CACHE_DIR, f'monaco_{year}.pkl')
    is_cached = os.path.exists(cache_path)
    
    await ws.send_json({
        'type': 'status',
        'status': 'loading',
        'message': f'Loading Monaco {year} from local cache...' if is_cached else f'Downloading Monaco {year} telemetry via FastF1 (may take ~2 min)...',
    })

    loop = asyncio.get_event_loop()
    try:
        session_data = await loop.run_in_executor(None, load_monaco_session, year)
    except Exception as exc:
        await ws.send_json({'type': 'error', 'message': str(exc)})
        await ws.close()
        return

    # ── Driver validation ────────────────────────────────────────────────
    available_drivers = session_data.get('drivers', [])
    if driver not in available_drivers:
        await ws.send_json({
            'type': 'error',
            'message': (
                f'Driver "{driver}" not found in Monaco {year}. '
                f'Available: {available_drivers}'
            ),
        })
        await ws.close()
        return

    # ── Notify client: ready ─────────────────────────────────────────────
    await ws.send_json({
        'type': 'status',
        'status': 'ready',
        'total_laps': session_data['total_laps'],
        'drivers': session_data['drivers'],
        'driver_info': session_data['driver_info'],
    })

    # ── Mutable control refs shared between replay task and message handler
    speed_ctrl = [1.0]   # replay speed multiplier
    paused_ctrl = [False]

    replay_task = asyncio.create_task(
        _replay_loop(ws, session_data, driver, speed_ctrl, paused_ctrl)
    )

    # ── Handle incoming control messages ─────────────────────────────────
    try:
        while not replay_task.done():
            try:
                msg = await asyncio.wait_for(ws.receive_json(), timeout=0.5)
            except asyncio.TimeoutError:
                continue
            except Exception:
                break

            msg_type = msg.get('type', '')
            if msg_type == 'set_speed':
                speed_ctrl[0] = max(0.1, min(float(msg.get('speed', 1.0)), 16.0))
            elif msg_type == 'pause':
                paused_ctrl[0] = True
            elif msg_type == 'resume':
                paused_ctrl[0] = False

    except WebSocketDisconnect:
        pass
    finally:
        replay_task.cancel()
        try:
            await replay_task
        except asyncio.CancelledError:
            pass


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, log_level='info')
