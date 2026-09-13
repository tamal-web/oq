import React, { useState, useEffect, useRef, useCallback } from "react";
import RaceSelector from "./RaceSelector";
import MonacoTrack from "./monaco";
import EnergyPanel from "./EnergyPanel";
import OvertakePanel from "./OvertakePanel";
import DecisionHistoryTable from "./DecisionHistoryTable";
import SocTrendPage from "./SocTrendPage";

const WS_BASE = "ws://localhost:8000/ws/race";

export default function App() {
  const wsRef = useRef(null);
  const [phase, setPhase] = useState("selector"); // 'selector', 'loading', 'racing', 'finished'
  const [activeView, setActiveView] = useState("racing"); // 'racing', 'soc'
  
  const [statusMessage, setStatusMessage] = useState("");
  const [raceState, setRaceState] = useState(null);
  const [energyState, setEnergyState] = useState(null);
  const [opponentEnergyState, setOpponentEnergyState] = useState(null);
  const [overtakeState, setOvertakeState] = useState(null);
  const [sessionTime, setSessionTime] = useState(null);
  const [playing, setPlaying] = useState(true);
  const [speed, setSpeed] = useState(1.0);

  // History for SOC Trend Page
  const historyRef = useRef({
    socData: [],
    events: [],
    lastMode: null,
    lastLap: null,
    lastLogTime: -999,
  });

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  const handleStart = useCallback((year, driver) => {
    // Close any existing connection
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setPhase("loading");
    setActiveView("racing");
    setStatusMessage(`Connecting to Monaco ${year} replay…`);
    setRaceState(null);
    setEnergyState(null);
    setOpponentEnergyState(null);
    setOvertakeState(null);
    setSessionTime(null);
    setPlaying(true);
    setSpeed(1.0);

    // Reset history
    historyRef.current = {
      socData: [],
      events: [],
      lastMode: null,
      lastLap: null,
      lastLogTime: -999,
    };

    const ws = new WebSocket(`${WS_BASE}/${year}/${driver}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatusMessage(`Loading Monaco ${year} telemetry…`);
    };

    ws.onmessage = (event) => {
      let msg;
      try {
        msg = JSON.parse(event.data);
      } catch {
        return;
      }

      const { type } = msg;

      if (type === "status") {
        setStatusMessage(msg.message || "");
        if (msg.status === "loading") setPhase("loading");
        // 'ready' stays loading until first tick
      } else if (type === "tick") {
        const t = msg.session_time_s;
        const e = msg.energy || {};
        const r = msg.race || {};
        const ref = historyRef.current;

        // Downsample SOC chart data to 1 Hz
        if (t != null && t - ref.lastLogTime >= 1.0) {
          ref.socData.push({ t, soc: e.soc_pct || 0 });
          ref.lastLogTime = t;
        }

        // Record mode change events
        if (e.mode && e.mode !== ref.lastMode) {
          ref.events.push({
            t,
            lap: r.lap || 1,
            mode: e.mode,
            soc: e.soc_pct || 0,
            details: `Energy mode switched to ${e.mode}`
          });
          ref.lastMode = e.mode;
        }

        // Record lap change events
        if (r.lap && r.lap !== ref.lastLap) {
          if (ref.lastLap !== null) {
            ref.events.push({
              t,
              lap: r.lap,
              mode: e.mode || 'NORMAL',
              soc: e.soc_pct || 0,
              details: `Started Lap ${r.lap}`
            });
          }
          ref.lastLap = r.lap;
        }

        setRaceState(r);
        setEnergyState(e);
        setOpponentEnergyState(msg.opponent_energy || null);
        setOvertakeState(msg.overtake || null);
        setSessionTime(t ?? null);
        setPhase((prev) => (prev !== "racing" ? "racing" : prev));
      } else if (type === "finished") {
        setPhase("finished");
      } else if (type === "error") {
        setStatusMessage(msg.message || "Unknown error from server.");
        setPhase("selector");
      }
    };

    ws.onerror = () => {
      setStatusMessage(
        "WebSocket connection failed. Is the backend running on port 8000?",
      );
      setPhase("selector");
    };

    ws.onclose = () => {
      if (wsRef.current === ws) wsRef.current = null;
    };
  }, []);

  const handleSpeedChange = useCallback((newSpeed) => {
    setSpeed(newSpeed);
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(
        JSON.stringify({ type: "set_speed", speed: newSpeed }),
      );
    }
  }, []);

  const handlePlayPause = useCallback(() => {
    setPlaying((prev) => {
      const next = !prev;
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: next ? "resume" : "pause" }));
      }
      return next;
    });
  }, []);

  // ── Selector phase ────────────────────────────────────────────────────────
  if (phase === "selector") {
    return <RaceSelector onStart={handleStart} />;
  }

  // ── Loading phase ─────────────────────────────────────────────────────────
  if (phase === "loading") {
    return (
      <div
        style={{
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background:
            "linear-gradient(160deg, #0d2f3f 0%, #12181c 55%, #17191d 100%)",
          fontFamily: '-apple-system, "Segoe UI", Roboto, Inter, sans-serif',
        }}
      >
        <div
          style={{
            background: "rgba(10,20,26,0.85)",
            border: "1px solid rgba(255,255,255,0.1)",
            borderRadius: 16,
            padding: "48px 52px",
            textAlign: "center",
            maxWidth: 440,
            color: "#eef1f0",
          }}
        >
          <div
            style={{
              width: 48,
              height: 48,
              border: "3px solid rgba(255,255,255,0.12)",
              borderTopColor: "#e8002d",
              borderRadius: "50%",
              margin: "0 auto 24px",
              animation: "spin 0.8s linear infinite",
            }}
          />
          <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
          <div style={{ fontSize: 18, fontWeight: 700, marginBottom: 10 }}>
            Monaco Grand Prix
          </div>
          <div style={{ fontSize: 13, color: "#8fb6c4", lineHeight: 1.6 }}>
            {statusMessage || "Loading telemetry…"}
          </div>
        </div>
      </div>
    );
  }

  // ── Racing / finished phase ───────────────────────────────────────────────
  return (
    <div
      style={{
        minHeight: "100vh",
        background:
          "linear-gradient(160deg, #0d2f3f 0%, #12181c 55%, #17191d 100%)",
        padding: 16,
        boxSizing: "border-box",
        fontFamily: '-apple-system, "Segoe UI", Roboto, Inter, sans-serif',
      }}
    >
      {/* Top bar */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 4px 12px",
          borderBottom: "1px solid rgba(255,255,255,0.08)",
          marginBottom: 16,
        }}
      >
        <div>
          <span
            style={{
              fontSize: 11,
              color: "#e8002d",
              fontWeight: 700,
              letterSpacing: 1,
              marginRight: 10,
            }}
          >
            MONACO ONLY
          </span>
          <span style={{ fontSize: 13, color: "#8fb6c4" }}>
            F1 Overtake Intelligence · Monaco Grand Prix
          </span>
        </div>
        <div
          style={{
            display: "flex",
            gap: "0.5rem",
          }}
        >
          {activeView === "racing" ? (
            <button
              onClick={() => setActiveView("soc")}
              style={{
                background: "rgba(0,210,160,0.15)",
                border: "1px solid rgba(0,210,160,0.4)",
                borderRadius: 6,
                color: "#00d2a0",
                fontSize: 12,
                padding: "5px 12px",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              SOC Trend & History
            </button>
          ) : (
            <button
              onClick={() => setActiveView("racing")}
              style={{
                background: "rgba(255,180,0,0.15)",
                border: "1px solid rgba(245,185,66,0.4)",
                borderRadius: 6,
                color: "#f5b942",
                fontSize: 12,
                padding: "5px 12px",
                cursor: "pointer",
                fontWeight: 600,
              }}
            >
              ← Back to Racing Map
            </button>
          )}

          <button
            onClick={() => {
              if (wsRef.current) wsRef.current.close();
              setPhase("selector");
            }}
            style={{
              background: "rgba(255,255,255,0.05)",
              border: "1px solid rgba(255,255,255,0.1)",
              borderRadius: 6,
              color: "#8fb6c4",
              fontSize: 12,
              padding: "5px 12px",
              cursor: "pointer",
            }}
          >
            Exit Replay
          </button>
        </div>
      </div>

      {/* Main layout */}
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          alignItems: "flex-start",
        }}
      >
        {activeView === "soc" ? (
          <SocTrendPage 
            socData={historyRef.current.socData} 
            energyEvents={historyRef.current.events}
            sessionTime={sessionTime} 
          />
        ) : (
          <>
            {/* Left — track + timing */}
            <div style={{ flex: "1 1 560px", minWidth: 280 }}>
              <MonacoTrack
                cars={raceState?.cars || []}
                lap={raceState?.lap || 1}
                totalLaps={raceState?.total_laps || 78}
                playing={playing}
                speed={speed}
                onSpeedChange={handleSpeedChange}
                onPlayPause={handlePlayPause}
                status={phase}
                statusMessage={statusMessage}
              />
            </div>

            {/* Right — energy + overtake + history */}
            <div
              style={{
                flex: "0 0 450px",
                minWidth: 320,
                display: "flex",
                flexDirection: "column",
                gap: 14,
              }}
            >
              {/* Important: Overtake Panel should be shown on top */}
              <OvertakePanel overtake={overtakeState} />
              <EnergyPanel
                energy={energyState}
                opponentEnergy={opponentEnergyState}
              />
              <DecisionHistoryTable
                overtake={overtakeState}
                sessionTime={sessionTime}
              />
            </div>
          </>
        )}
      </div>
    </div>
  );
}
