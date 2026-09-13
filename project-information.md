# F1 Overtake Intelligence & Energy Management System

## 1. Project Overview

This project is an **F1 race-replay and overtake-decision system designed around the 2026 F1 energy-regulation concept**.

The application replays historical **Monaco Grand Prix** telemetry and continuously evaluates the state of a selected attacking driver. At each telemetry update, the system updates:

1. The driver's race position and track location.
2. The driver's energy state through the **Energy Engine (EE)**.
3. The overtake decision through the **Overtake Engine (OE)**.
4. The frontend dashboard through a synchronized WebSocket update.

The central question answered by the system is:

> **Should the selected driver attempt an overtake at this moment?**

The final overtake decision is produced by the Overtake Engine, which combines three subcomponents:

- **OI — Overtake Intelligence:** machine-learning prediction of whether an overtake should be attempted.
- **EC — Energy Conservation:** determines whether the overtake is energetically feasible and, eventually, whether spending energy now is strategically worthwhile.
- **RC — Rule Compliance:** determines whether the proposed action is compliant with the relevant energy and overtaking rules.

At the current project stage, **EC and RC are placeholders that return `True`**. OI is the real trained binary-classification model.

---

# 2. Core Project Objective

The application is intended to demonstrate a complete decision pipeline built on historical F1 telemetry:

```text
Historical Monaco GP Telemetry
            ↓
      Telemetry Replay
            ↓
      ┌───────────────┐
      │ Energy Engine │
      │     EE.py     │
      └───────┬───────┘
              │
              ↓
      ┌─────────────────┐
      │ Overtake Engine │
      │      OE.py      │
      └───────┬─────────┘
              │
       ┌──────┼──────┐
       ↓      ↓      ↓
      OI     EC     RC
       │      │      │
       └──────┼──────┘
              ↓
      Final Overtake Decision
              ↓
          WebSocket
              ↓
        React Frontend
       ┌──────┼──────────┐
       ↓      ↓          ↓
    Track   Energy   Overtake
    State   Metrics  Prediction
```

The important architectural principle is:

> **One telemetry update must produce one synchronized application state that drives the track, race positions/ranks, Energy Engine metrics, and Overtake Engine prediction together.**

---

# 3. Circuit Scope: Monaco Only

This project is intentionally restricted to the **Monaco Grand Prix**.

There are two reasons for this restriction:

1. The frontend track visualization is specifically a Monaco circuit.
2. The current OI model was trained using Monaco Grand Prix telemetry only.

Therefore, the application must **not expose a general F1 circuit selector**.

The user can select only supported Monaco races/years.

## Currently supported races

- 2022 Monaco Grand Prix
- 2023 Monaco Grand Prix
- 2024 Monaco Grand Prix

Conceptually, the frontend selector should be:

```text
Circuit: Monaco Grand Prix

Race Year:
- 2022
- 2023
- 2024
```

The circuit itself is not user-selectable. It is always Monaco.

The backend should also validate race requests so that an unsupported/non-Monaco race cannot be loaded through a manually modified request.

If the model is retrained for additional Monaco seasons in the future, those seasons can be added without changing the overall architecture.

---

# 4. Technology Stack

## Backend / Data / Machine Learning

- **Python**
- **FastF1** — historical F1 telemetry/session data source and preprocessing ecosystem.
- **Pandas / NumPy** — telemetry processing and numerical calculations.
- **scikit-learn** — machine-learning model implementation, including the current Random Forest OI classifier.
- **Pickle (`.pkl`)** — local persistence of preprocessed telemetry, training datasets, and the trained OI model.
- **WebSocket-capable Python backend** — real-time communication with the React frontend.

## Frontend

- **React 19**
- **Vite 8**
- **JavaScript / JSX** in the current frontend
- **CSS**
- **pnpm** package manager

## Existing frontend dependencies / tooling

The current frontend contains packages such as:

- React
- React DOM
- Vite
- `@vitejs/plugin-react`
- ESLint
- `eslint-plugin-react-hooks`
- `eslint-plugin-react-refresh`

## Runtime Architecture

```text
Python Backend
      ↕ WebSocket
React + Vite Frontend
```

The backend is the source of truth for replay time and telemetry state. The frontend renders the state received from the backend.

---

# 5. Project Folder Structure

Current project structure:

```text
.
├── ee.py
├── oe.py
├── server.py
├── frontend-react/
│   ├── eslint.config.js
│   ├── index.html
│   ├── node_modules/
│   ├── package.json
│   ├── pnpm-lock.yaml
│   ├── public/
│   │   ├── favicon.svg
│   │   └── icons.svg
│   ├── README.md
│   ├── src/
│   │   ├── App.css
│   │   ├── App.jsx
│   │   ├── index.css
│   │   ├── main.jsx
│   │   ├── monaco.jsx
│   │   └── assets/
│   │       ├── hero.png
│   │       ├── react.svg
│   │       └── vite.svg
│   └── vite.config.js
└── oe_subparts/
    ├── ec.py
    ├── rc.py
    └── oi_monoco/
        ├── ff1_cache/
        │   ├── 2022/
        │   │   └── 2022-05-29_Monaco_Grand_Prix/
        │   │       └── 2022-05-29_Race/
        │   │           ├── _extended_timing_data.ff1pkl
        │   │           ├── car_data.ff1pkl
        │   │           ├── driver_info.ff1pkl
        │   │           ├── lap_count.ff1pkl
        │   │           ├── position_data.ff1pkl
        │   │           ├── race_control_messages.ff1pkl
        │   │           ├── session_info.ff1pkl
        │   │           ├── session_status_data.ff1pkl
        │   │           ├── timing_app_data.ff1pkl
        │   │           └── track_status_data.ff1pkl
        │   ├── 2023/
        │   │   └── 2023-05-28_Monaco_Grand_Prix/
        │   │       └── 2023-05-28_Race/
        │   │           ├── _extended_timing_data.ff1pkl
        │   │           ├── car_data.ff1pkl
        │   │           ├── driver_info.ff1pkl
        │   │           ├── lap_count.ff1pkl
        │   │           ├── position_data.ff1pkl
        │   │           ├── race_control_messages.ff1pkl
        │   │           ├── session_info.ff1pkl
        │   │           ├── session_status_data.ff1pkl
        │   │           ├── timing_app_data.ff1pkl
        │   │           └── track_status_data.ff1pkl
        │   ├── 2024/
        │   │   └── 2024-05-26_Monaco_Grand_Prix/
        │   │       └── 2024-05-26_Race/
        │   │           ├── _extended_timing_data.ff1pkl
        │   │           ├── car_data.ff1pkl
        │   │           ├── driver_info.ff1pkl
        │   │           ├── lap_count.ff1pkl
        │   │           ├── position_data.ff1pkl
        │   │           ├── race_control_messages.ff1pkl
        │   │           ├── session_info.ff1pkl
        │   │           ├── session_status_data.ff1pkl
        │   │           ├── timing_app_data.ff1pkl
        │   │           └── track_status_data.ff1pkl
        │   └── fastf1_http_cache.sqlite
        ├── oi_inference.py
        ├── oi_preprocessing.py
        ├── oi_training.py
        ├── overtake_model_monaco.pkl
        ├── telemetry_all.pkl
        └── training_dataset.pkl
```

> `node_modules/` is shown because it exists in the current working tree, but it is generated dependency content and normally should not be version-controlled.

---

# 6. Backend File Responsibilities

## `ee.py` — Energy Engine

The Energy Engine is responsible for maintaining the current energy state of the selected attacking car.

It consumes telemetry rows and uses existing physics-based calculations to reverse-engineer energy information from observable telemetry.

Important values include, where available from the existing implementation:

- SOC
- Overtake Bonus Left
- Energy Harvested
- Energy Deployed
- Energy Harvested This Lap
- Energy Deployed This Lap
- P Regen Instant
- P Deploy Instant
- Mode
- Harvest Cap Remaining
- SOC Confidence
- SOC Delta This Lap
- Other existing energy-related metrics

The Energy Engine should expose or preserve an `update()`-style function that accepts one telemetry update and updates its internal state.

The frontend should **not duplicate the Energy Engine physics**. It should only display the resulting state received from the backend.

---

## `oe.py` — Overtake Engine

`oe.py` is the top-level Overtake Engine and **orchestrator**.

It is responsible for combining the results of:

```text
OI + EC + RC
```

into the final overtake decision.

`oe.py` should not contain the entire implementation of those subcomponents. It should call their exposed functions/classes and combine the outputs.

A conceptual decision is:

```python
should_overtake = oi_result and ec_result and rc_result
```

The actual implementation should respect the existing model output/API and project code.

---

# 7. Overtake Engine Subcomponents

## 7.1 OI — Overtake Intelligence

Location:

```text
oe_subparts/oi_monoco/oi_inference.py
```

OI is the machine-learning component.

Its responsibility is to answer:

> **Should I overtake right now?**

It uses a **binary classification model** trained on Monaco Grand Prix race telemetry from:

- 2022
- 2023
- 2024

The current trained model is stored in:

```text
oe_subparts/oi_monoco/overtake_model_monaco.pkl
```

The inference layer should expose a clean callable interface that `oe.py` can use.

If the existing `oi_inference.py` does not expose a suitable function, add a wrapper rather than rewriting the underlying trained model unnecessarily.

### OI responsibilities

OI should:

- Receive the features/state needed by the trained model.
- Run the trained binary classifier.
- Return a clear prediction.
- Remain specific to Monaco data unless the model is retrained for other circuits.

OI does **not** own:

- Energy physics.
- Energy conservation strategy.
- Rule compliance.
- Frontend rendering.
- WebSocket transport.

---

## 7.2 EC — Energy Conservation

Location:

```text
oe_subparts/ec.py
```

EC represents the energy-conservation and energy-strategy layer of OE.

Its eventual purpose is to determine whether an overtake is energetically sensible.

Future EC logic is expected to consider concepts such as:

- Current usable energy.
- SOC.
- Energy required to execute an overtake.
- Overtake Mode / boost energy impact.
- Available energy of the car ahead when relevant.
- Potential response/boost from the opponent.
- Whether the attacking car can maintain the required performance after committing energy.
- Whether energy should instead be conserved/harvested for a later opportunity.
- Long-term race strategy.

The conceptual future question is:

> **Do we have enough energy to complete the overtake, and is using that energy now strategically better than saving it for later?**

### Current implementation

EC is fully implemented using an **Expected Value (EV) decision matrix** designed to mitigate "reversible passes" commonly seen under 2026 regulations.

It continuously evaluates three distinct options:
- **STRIKE_NOW**: EV of attacking, considering the probability the pass sticks (heavily discounting easily reversed overtakes).
- **HOLD_THEN_STRIKE_LATER**: EV of waiting for a better opportunity window on a future lap.
- **HARVEST_NOW**: EV of saving/recharging energy for later deployment.

At Monaco, the EC engine is configured via `MONACO_OVERTAKE_PROFILE` as an *energy-abundant* but *geometrically restrictive* circuit. It aggressively weights down energy differentials (as having energy doesn't create space in Monaco) and applies a severe reversal discount to ensure the attacker doesn't waste energy on a pass they cannot defend. The final EC decision is passed directly to the Overtake Engine, alongside a detailed probability rationale.

---

## 7.3 RC — Rule Compliance

Location:

```text
oe_subparts/rc.py
```

RC represents the rule-compliance layer of OE.

Its eventual purpose is to ensure that the proposed overtake is legally/compliance-wise valid under the relevant F1 energy and overtaking constraints.

Future RC logic can validate concepts such as:

- Whether the driver is eligible to use the relevant overtake/energy mode.
- Whether energy deployment remains within applicable limits.
- Whether the proposed action violates applicable overtaking conditions.
- Whether other regulatory constraints should prevent the action.

### Current implementation

RC is fully implemented as a **track-aware Rule Compliance Engine configured for Monaco 2026**. 
It encodes FIA-confirmed and reported per-circuit energy relaxations:

- **Bespoke Power Taper Curve**: Monaco uses a "Rev 1" curve where the 350kW ceiling starts tapering at 200km/h (instead of 290km/h).
- **Per-lap Harvest Cap**: 9MJ in qualifying and race (drops to 8.5MJ if Overtake Mode is lost).
- **Straight Mode**: Disabled for Monaco; active aero stays in Corner Mode.
- **Race Distance**: 260km (Sporting Regs Art. B2.5.2b).

The RC Engine integrates statelessly with the Overtake Engine orchestrator (`oe.py`), evaluating at each tick whether a proposed `BOOST` or `OVERTAKE_MODE` deployment satisfies all power limits, torque ceilings, delta-SoC constraints, and harvest caps before green-lighting an overtake.

---

# 8. OE Final Decision

`oe.py` should combine all three subcomponents.

Conceptually:

```text
                 OI
                  ↓
          ML overtake prediction
                  │
                  ├──────┐
                  ↓      │
                 EC      │
                  ↓      │
                 RC      │
                  ↓      │
           Final OE result
```

The final result should contain enough information for both the UI and debugging.

A useful conceptual structure is:

```json
{
  "oi_prediction": true,
  "ec": true,
  "rc": true,
  "should_overtake": true
}
```

The exact field names should follow the existing implementation where practical.

---

# 9. Driver Selection Model

The application supports selecting the **attacking driver**.

The selected driver is the car for which:

- EE calculates energy state.
- OE calculates the overtake decision.
- The frontend highlights the car in the race replay.

The **opponent** should be automatically identified as the car immediately ahead of the selected driver based on the current race ordering/telemetry.

Therefore:

```text
Selected Driver = Attacking Car
Car Immediately Ahead = Opponent
```

If driver selection has not yet been implemented, a reasonable default is the driver currently in **P2**, because that naturally creates a P2-versus-P1 overtaking scenario.

The architecture should still support explicit driver selection later without requiring a major redesign.

---

# 10. Telemetry Data Strategy

The project already contains a consolidated telemetry dataset:

```text
oe_subparts/oi_monoco/telemetry_all.pkl
```

This file is approximately **145 MB** and loads quickly (about one second in the current environment).

## Runtime policy

Use `telemetry_all.pkl` as the **runtime replay source**.

Do **not** re-run FastF1 downloads and preprocessing every time the user starts a race replay when the required data is already available locally.

FastF1 remains the original source/ecosystem used to obtain and prepare the data, while the local `.pkl` file is the efficient runtime dataset.

Conceptually:

```text
FastF1
  ↓
Data acquisition / preprocessing
  ↓
telemetry_all.pkl
  ↓
Runtime replay
```

This significantly simplifies and accelerates the interactive demo.

---

# 11. Existing FastF1 Cache

The project also contains FastF1 cached session files under:

```text
oe_subparts/oi_monoco/ff1_cache/
```

The cache currently includes Monaco race sessions for:

- 2022
- 2023
- 2024

with cached data such as:

- Car data
- Position data
- Driver information
- Lap count
- Timing application data
- Session information
- Session status
- Track status
- Race control messages
- Extended timing data

These files are useful for data generation/reprocessing and debugging, but they should not be required for normal replay when `telemetry_all.pkl` contains the required runtime data.

---

# 12. OI Training Pipeline

The OI model support files are under:

```text
oe_subparts/oi_monoco/
```

### `oi_preprocessing.py`

Responsible for preparing raw/retrieved telemetry into model-ready features.

### `oi_training.py`

Responsible for training the OI model.

### `training_dataset.pkl`

Persisted training dataset used by the OI training process.

### `overtake_model_monaco.pkl`

Persisted trained OI binary-classification model.

### `oi_inference.py`

Loads/uses the trained model and produces inference for the current race state.

The production replay should generally use the **trained model and inference path**, not retrain the model during application startup.

---

# 13. Opponent State and Energy Consideration

The system is designed to use telemetry for both the selected attacking car and the car ahead where required data is available.

This matters because the opponent may react to an attempted overtake.

Future energy logic should therefore consider not only:

```text
Do I have enough energy to attack?
```

but also:

```text
Can I successfully complete the overtake
if the car ahead responds with its own available boost/overtake capability?
```

This responsibility belongs primarily to the future EC implementation, while OI remains the learned prediction layer.

---

# 14. Race Replay Architecture

The backend owns the race replay.

The frontend should not independently replay telemetry or maintain a separate clock.

For each telemetry row:

```text
1. Read telemetry row.
2. Update race state.
3. Update Energy Engine.
4. Identify current opponent/gap.
5. Run OI when the configured overtake trigger condition is met.
6. Run EC.
7. Run RC.
8. Combine through OE.
9. Construct one application-state payload.
10. Send the payload through WebSocket.
11. Move to the next telemetry update.
```

This establishes a single source of truth for replay time.

---

# 15. Central Synchronized Update

A central wrapper should conceptually look like:

```python
def process_telemetry_row(row):
    race_state = update_race_state(row)

    energy_state = energy_engine.update(row)

    oe_state = overtake_engine.update(
        row=row,
        energy_state=energy_state,
    )

    return {
        "race": race_state,
        "energy": energy_state,
        "overtake": oe_state,
    }
```

This is an architectural example, not a requirement to use these exact function names.

The key rule is:

> **One telemetry row → one synchronized state → one WebSocket update.**

---

# 16. WebSocket Architecture

The backend communicates with `frontend-react/` using WebSockets.

The backend sends a combined state containing the information necessary to update the three major UI areas.

Conceptual payload:

```json
{
  "timestamp": "...",
  "lap": 42,
  "race": {
    "position": 7,
    "rank": 7,
    "car_position": {
      "x": 0,
      "y": 0
    }
  },
  "energy": {
    "soc": 72.4,
    "overtake_bonus_left": 0.8,
    "energy_harvested_lap": 1.2,
    "energy_deployed_lap": 2.4,
    "p_regen_instant": 0,
    "p_deploy_instant": 0,
    "mode": "...",
    "harvest_cap_remaining": 0.4,
    "soc_confidence": 0.96,
    "soc_delta_lap": -0.8
  },
  "overtake": {
    "oi_prediction": true,
    "ec": true,
    "rc": true,
    "should_overtake": true
  }
}
```

The exact schema should follow the actual backend implementation and existing field names.

---

# 17. Critical Frontend Synchronization Requirement

The frontend contains three primary synchronized areas:

## A. Monaco Track + Positions / Ranks

This includes:

- Selected driver's position on the Monaco track.
- Other cars where visualized.
- Current race order/rank.
- Lap/race progress.
- Race state.

## B. Energy Metrics / Stats

These are supplied by EE and may include:

- SOC
- Overtake Bonus Left
- Energy Harvested Per Lap
- Energy Deployed Per Lap
- P Regen Instant
- P Deploy Instant
- Mode
- Harvest Cap Remaining
- SOC Confidence
- SOC Delta This Lap
- Other important EE fields

## C. Overtake Prediction

This displays the final OE result.

Example:

```text
SHOULD OVERTAKE
```

or:

```text
DO NOT OVERTAKE
```

The UI may also expose the internal results for transparency/debugging:

```text
OI: PASS
EC: PASS
RC: PASS
```

### Synchronization rule

All three areas must update from **the same telemetry update**.

They must not use independent timers or independent replay loops.

For example:

```text
Telemetry Row #1520
       ↓
 ┌───────────────┬────────────────┬────────────────────┐
 │ Track         │ Energy         │ Overtake           │
 │ Position      │ Metrics        │ Prediction         │
 │ Rank          │ Updated        │ Updated            │
 └───────────────┴────────────────┴────────────────────┘
```

If the backend is processing telemetry row #1520, all three frontend areas must represent row #1520/state derived from that update.

---

# 18. Frontend Layout

The current frontend is built around the Monaco visualization in:

```text
frontend-react/src/monaco.jsx
```

The dashboard should use two primary columns.

## Left column

The left side should contain:

- Monaco circuit visualization.
- Race replay.
- Current car positions.
- Race ranking/order.
- Lap/race progress information.
- Replay speed slider.

## Right column

The right side should contain:

### Top section: Energy Metrics

Display the important EE values.

### Bottom section: Overtake Prediction

Display the final OE recommendation prominently.

Example:

```text
┌──────────────────────────────────┐
│        SHOULD OVERTAKE           │
└──────────────────────────────────┘
```

or:

```text
┌──────────────────────────────────┐
│       DO NOT OVERTAKE            │
└──────────────────────────────────┘
```

---

# 19. Race Speed Slider

The existing Monaco track component includes a speed slider.

The slider must control the **entire telemetry replay speed** rather than only the visual track animation.

Changing speed should affect:

- Track movement.
- Position/rank updates.
- Energy metric updates.
- OI inference timing.
- EC evaluation timing.
- RC evaluation timing.
- Final OE decision updates.

The speed slider should therefore control how quickly the backend progresses through telemetry updates or otherwise control the shared replay cadence.

### Important

Do not make separate frontend timers such as:

```text
Track timer
Energy timer
Overtake timer
```

These would allow the systems to drift out of synchronization.

Instead:

```text
One replay clock
      ↓
One telemetry update
      ↓
One combined state
      ↓
All frontend components update together
```

---

# 20. Overtake Trigger

The OI/OE logic should only be evaluated when an actual overtaking opportunity is relevant.

The trigger should be represented by a configurable value rather than repeated hard-coded values.

For example:

```python
OVERTAKE_TRIGGER_GAP = 2.0
```

When the car ahead enters the configured gap:

```text
Car-ahead gap
      ↓
Within configured threshold?
      ↓
Yes
      ↓
Run OI inference
      ↓
Run EC
      ↓
Run RC
      ↓
OE produces final decision
```

The exact trigger semantics should follow the project's current agreed behavior, but the value itself should remain configurable.

---

# 21. Energy / Overtake Concept

The project models the idea that an overtake can consume or require significant energy and that the decision should not be based on the ML classifier alone.

The intended future decision is therefore multidimensional:

```text
OI:
Is this an overtaking situation that historically/model-wise
looks favorable?

EC:
Is the action feasible and sensible given current energy?

RC:
Is the action compliant with the relevant rules?
```

Only after these layers are considered should OE produce the final recommendation.

The project may also later incorporate long-term strategy:

```text
Overtake now
       vs.
Conserve / harvest energy
       ↓
Future race opportunities
```

That long-term strategy belongs to the future EC implementation.

---

# 22. Current EC / RC Placeholder State

At the present stage:

```text
EC = True
RC = True
```

Therefore, the current OE output is effectively dominated by OI:

```text
should_overtake ≈ oi_prediction
```

provided the trigger/availability conditions are satisfied.

This is intentional and should not be treated as the finished energy/rules logic.

---

# 23. Current Data and Model Assets

| Asset | Purpose |
|---|---|
| `telemetry_all.pkl` | Consolidated runtime telemetry replay dataset |
| `training_dataset.pkl` | Prepared OI model training dataset |
| `overtake_model_monaco.pkl` | Trained Monaco-specific OI classifier |
| `ff1_cache/` | FastF1 cached Monaco session data |
| `oi_preprocessing.py` | OI feature/data preprocessing |
| `oi_training.py` | OI model training |
| `oi_inference.py` | OI inference |
| `ee.py` | Energy-state calculations |
| `oe.py` | Overtake Engine orchestration |
| `ec.py` | Energy Conservation placeholder/future logic |
| `rc.py` | Rule Compliance placeholder/future logic |
| `server.py` | Backend server / WebSocket integration |

---

# 24. `server.py` Responsibilities

`server.py` should act as the backend integration layer.

Its responsibilities should include:

- Starting the backend service.
- Exposing the race-selection/replay functionality.
- Validating supported Monaco races.
- Managing WebSocket connections.
- Starting/stopping or controlling telemetry replay.
- Accepting replay speed changes.
- Passing telemetry rows through the synchronized backend pipeline.
- Sending combined race + energy + overtake state to the frontend.

`server.py` should not become a second implementation of EE/OI/EC/RC. It should orchestrate communication and replay.

---

# 25. Recommended Backend State Model

A useful conceptual state model is:

```text
Replay State
├── race
│   ├── year
│   ├── circuit = Monaco
│   ├── lap
│   ├── timestamp
│   ├── selected_driver
│   ├── selected_driver_position
│   ├── ranking
│   └── car/track positions
│
├── energy
│   ├── SOC
│   ├── overtake bonus
│   ├── harvest/deployment metrics
│   ├── power metrics
│   └── confidence / deltas
│
└── overtake
    ├── opponent
    ├── gap
    ├── oi_prediction
    ├── ec_result
    ├── rc_result
    └── should_overtake
```

This state can then be serialized and transmitted as one WebSocket message.

---

# 26. Data Flow in Detail

## Step 1 — User selects Monaco race

The user selects 2022, 2023, or 2024 Monaco GP.

## Step 2 — Backend validates the race

The backend verifies that the request belongs to the supported Monaco-only dataset.

## Step 3 — Backend loads local data

The backend uses `telemetry_all.pkl` rather than downloading FastF1 data again.

## Step 4 — User selects attacking driver

The selected driver becomes the attacking car.

The car immediately ahead becomes the opponent.

## Step 5 — Replay begins

Telemetry is processed sequentially.

## Step 6 — EE updates

The Energy Engine consumes the current telemetry row and updates energy state.

## Step 7 — Overtake opportunity is checked

The current gap to the car ahead is evaluated.

## Step 8 — OI inference

When the configured trigger condition is met, the OI model is run.

## Step 9 — EC evaluation

Currently this returns `True`.

Later it will perform actual energy feasibility/strategy calculations.

## Step 10 — RC evaluation

Currently this returns `True`.

Later it will perform rules validation.

## Step 11 — OE combines results

The final overtake decision is produced.

## Step 12 — WebSocket payload generated

Race, energy, and overtake state are packaged together.

## Step 13 — React updates

All three frontend areas update from that one state message.

## Step 14 — Replay continues

The same process repeats for the next telemetry update.

---

# 27. Error Handling Requirements

The application should gracefully handle:

- Unsupported race/year selection.
- Non-Monaco race requests.
- Missing telemetry rows.
- Missing telemetry fields.
- Missing opponent data.
- Missing energy values.
- OI model/inference failures.
- WebSocket connection failures.
- End of replay.
- Invalid driver selection.
- Empty or malformed dataset sections.

A single missing metric should not crash the entire React application.

Where possible, retain the rest of the synchronized state and represent unavailable values safely as null/unknown rather than inventing values.

---

# 28. Code Quality and Integration Principles

When extending the project:

- Inspect and reuse existing code before rewriting it.
- Preserve the existing EE physics implementation.
- Preserve the trained OI model and its feature pipeline.
- Reuse the existing Monaco frontend component.
- Avoid duplicating calculations in React.
- Keep OI, EC, and RC modular.
- Keep OE as the orchestration layer.
- Keep replay timing centralized.
- Keep WebSocket state synchronized.
- Make configuration values such as supported years and the overtake trigger easy to change.
- Prefer explicit data structures and clear interfaces between modules.

---

# 29. Important Non-Goals for the Current Version

The following are intentionally **not fully implemented yet**:

### EC full energy strategy

The current EC implementation calculates the expected value of holding versus striking using a track-specific Reversal Discount (addressing 2026 reversible passes) and now processes both the attacking and opponent energy states live.

### RC full rules engine

The current RC implementation enforces track-aware 2026 regulations, specifically the Monaco 9MJ/lap harvest cap and bespoke >200km/h power taper curves.

### Long-term energy strategy

Future EC logic may evaluate whether to spend energy now or preserve it for later race opportunities.

### General-circuit support

The current system is **not intended to support other F1 circuits** because the current OI model is Monaco-specific and the frontend track is Monaco-specific.

---

# 30. Future Extensions

The architecture should allow the following future additions without major rewrites:

1. Full EC energy-feasibility calculations.
2. Long-term energy strategy and opportunity cost.
3. Full RC rules validation.
4. More detailed opponent-energy estimation.
5. Improved explanation of why OE recommended an overtake or no overtake.
6. Additional Monaco seasons after retraining/validation of OI.
7. Additional circuit models in the future, but only after training and validating circuit-specific or generalized OI models and providing corresponding track/data support.
8. More detailed telemetry charts and replay controls.
9. Model confidence/probability display in addition to the binary OI decision.

---

# 31. Example End-to-End Scenario

Suppose the user chooses:

```text
Circuit: Monaco Grand Prix
Year: 2023
Attacking Driver: Driver A
```

The backend loads the 2023 Monaco telemetry from `telemetry_all.pkl`.

During replay:

```text
Driver A
   ↓
Current position: P2
   ↓
Driver B directly ahead: P1
   ↓
Gap enters trigger threshold
   ↓
OI model runs
   ↓
OI = True
   ↓
EC = True  (current placeholder)
   ↓
RC = True  (current placeholder)
   ↓
OE = SHOULD OVERTAKE
```

At that exact telemetry update, the WebSocket sends:

```text
Track position → updated
Race ranking  → updated
Energy stats  → updated
OE prediction → SHOULD OVERTAKE
```

The four pieces of displayed information therefore describe the same point in the race.

---

# 32. Final System Contract

The project should satisfy the following core rules:

### Circuit

```text
Monaco only
```

### Runtime dataset

```text
telemetry_all.pkl
```

### Attacking car

```text
User-selected driver
```

with P2 as a possible default when selection is unavailable.

### Opponent

```text
Car immediately ahead of the selected driver
```

### Energy processing

```text
Telemetry → EE.update()
```

### Overtake processing

```text
Telemetry + relevant energy/race state
        ↓
       OE
   ┌────┼────┐
   ↓    ↓    ↓
  OI   EC   RC
   └────┼────┘
        ↓
 Final decision
```

### Current EC

```text
return True
```

### Current RC

```text
return True
```

### Frontend transport

```text
Backend → WebSocket → React
```

### Synchronization

```text
One telemetry update
        ↓
One combined backend state
        ↓
One WebSocket update
        ↓
Track + Positions + Energy + Overtake update together
```

### Speed control

The existing Monaco track speed slider controls the **shared replay cadence**, not an independent visual animation.

---

# 33. Success Criteria

The integration is successful when all of the following are true:

- The user can select only supported Monaco GP races.
- The selected Monaco race is loaded from the existing local dataset.
- The user can select an attacking driver.
- The opponent is automatically identified as the car ahead.
- Telemetry is replayed sequentially.
- EE updates on every telemetry update.
- OE receives the appropriate state and evaluates OI/EC/RC as required.
- The frontend receives a synchronized combined state through WebSockets.
- The Monaco track and positions/ranks update correctly.
- Energy metrics update at the same telemetry timestep.
- Overtake prediction updates at the same telemetry timestep.
- The speed slider changes the rate of the whole replay.
- There is no independent frontend clock causing race, energy, and prediction state to drift apart.
- EC and RC can later be replaced with real implementations without redesigning the rest of the application.
- OI remains explicitly associated with the Monaco-trained model.

---

# 34. One-Line Project Description

> **A Monaco-specific F1 telemetry replay system that combines a real-time Energy Engine with a machine-learning Overtake Intelligence model, Energy Conservation, and Rule Compliance to produce synchronized overtake decisions through a React/WebSocket dashboard.**
