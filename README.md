# OQ (Overtake Quotient) - F1 Overtake Intelligence

OQ is a full-stack application designed to analyze and predict Formula 1 overtakes, specifically tuned for the Monaco Grand Prix. It simulates the 2026 FIA power unit regulations and energy management strategies.

## Architecture

The project consists of two main components:

1. **Backend (Python)**: FastAPI application providing WebSockets for live race telemetry replay, powered by FastF1.
2. **Frontend (React)**: Interactive dashboard visualizing race telemetry, driver positioning, battery state of charge (SOC), and overtake decisions in real-time.

## Overtake Engine (OE)

The core logic of the application resides in the Overtake Engine (`oe.py`), which orchestrates three sub-engines to make tactical decisions:

1. **Rule Compliance (RC)**: Evaluates whether an overtake attempt is legally permissible under the 2026 FIA regulations (MGU-K power limits, delta-SOC limits, harvest caps, and power taper curves).
2. **Energy Conservation (EC)**: Evaluates the energy economics using Expected Value (EV) math. Decides between `STRIKE NOW`, `HOLD THEN STRIKE LATER`, or `HARVEST NOW` based on battery SOC, gap urgency, and reversal risk.
3. **Overtake Intelligence (OI)**: A Machine Learning (RandomForest) model that predicts the probability of an overtake sticking based on physical telemetry features (Speed, Gap, DRS, etc.). _Note: Currently acts as an advisory signal._

## Setup Instructions

### Backend Setup

1. Navigate to the project root.
2. Create and activate a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the FastAPI server:
   ```bash
   python server.py
   ```
   _Note: The first time you run a specific race/driver combination, it will download telemetry via FastF1 to `telemetry_cache/`. Subsequent loads will be near-instantaneous._

### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd frontend-react
   ```
2. Install dependencies:
   ```bash
   npm install
   ```
3. Start the development server:
   ```bash
   npm run dev
   ```

## Features

- **Live Replay**: Replay Monaco GP sessions (2018-2024) at 1x to 10x speed.
- **Energy Panel**: Side-by-side comparison of your energy state vs. the car ahead, including Harvest and Deploy lap budgets.
- **SOC Trend**: Live-updating SVG chart plotting battery SOC% over time alongside a log of energy-related events.
- **Overtake Panel**: Actionable, granular decision readouts (Strike, Hold, Harvest, Deny) with OI, EC, and RC indicators.
