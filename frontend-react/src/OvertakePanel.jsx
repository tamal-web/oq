import React from "react";

// Pulse animation injected once into the document
const PULSE_CSS = `
@keyframes ot-pulse {
  0%   { box-shadow: 0 0 0 0 rgba(0,210,160,0.55); }
  70%  { box-shadow: 0 0 0 14px rgba(0,210,160,0); }
  100% { box-shadow: 0 0 0 0 rgba(0,210,160,0); }
}
@keyframes ot-deny-flash {
  0%, 100% { opacity: 1; }
  50%       { opacity: 0.85; }
}
`;

let styleInjected = false;
function injectStyle() {
  if (styleInjected || typeof document === "undefined") return;
  const el = document.createElement("style");
  el.textContent = PULSE_CSS;
  document.head.appendChild(el);
  styleInjected = true;
}

const s = {
  root: {
    background: "rgba(10,20,26,0.55)",
    border: "1px solid rgba(255,255,255,0.08)",
    borderRadius: 10,
    padding: "16px 18px",
    color: "#eef1f0",
    fontFamily: '-apple-system, "Segoe UI", Roboto, Inter, sans-serif',
  },
  label: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 1.5,
    color: "#8fb6c4",
    textTransform: "uppercase",
    marginBottom: 14,
  },
  banner: (state) => {
    let bg = "rgba(255,255,255,0.04)";
    let border = "rgba(255,255,255,0.08)";
    let anim = "none";

    if (state.startsWith("strike")) {
      bg = "rgba(0,210,160,0.15)";
      border = "rgba(0,210,160,0.5)";
      anim = "ot-pulse 1.6s ease-in-out infinite";
    } else if (state === "deny") {
      bg = "rgba(232,0,45,0.15)";
      border = "rgba(232,0,45,0.4)";
      anim = "ot-deny-flash 2s ease-in-out infinite";
    } else if (state === "hold") {
      bg = "rgba(255, 170, 0, 0.15)";
      border = "rgba(255, 170, 0, 0.5)";
    } else if (state === "harvest") {
      bg = "rgba(0, 150, 255, 0.15)";
      border = "rgba(0, 150, 255, 0.5)";
    }

    return {
      borderRadius: 10,
      padding: "20px 16px",
      height: "50px",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      textAlign: "center",
      marginBottom: 16,
      background: bg,
      border: `2px solid ${border}`,
      animation: anim,
    };
  },
  bannerText: (state) => {
    let color = "#4a6470";
    if (state.startsWith("strike")) color = "#00d2a0";
    else if (state === "deny") color = "#e8002d";
    else if (state === "hold") color = "#ffaa00";
    else if (state === "harvest") color = "#0096ff";

    return {
      fontSize: 18,
      fontWeight: 900,
      letterSpacing: 0.5,
      color: color,
    };
  },
  subRow: {
    display: "flex",
    gap: 10,
    marginBottom: 14,
  },
  indicator: (pass) => ({
    flex: 1,
    display: "flex",
    alignItems: "center",
    gap: 6,
    background: "rgba(255,255,255,0.03)",
    border: `1px solid ${pass === null ? "rgba(255,255,255,0.06)" : pass ? "rgba(0,210,160,0.25)" : "rgba(232,0,45,0.25)"}`,
    borderRadius: 6,
    padding: "8px 10px",
    fontSize: 12,
    fontWeight: 700,
  }),
  dot: (pass) => ({
    width: 8,
    height: 8,
    borderRadius: "50%",
    background: pass === null ? "#4a6470" : pass ? "#00d2a0" : "#e8002d",
    flexShrink: 0,
  }),
  indicatorLabel: { color: "#8fb6c4", fontSize: 11, fontWeight: 600 },
  indicatorValue: (pass) => ({
    color: pass === null ? "#4a6470" : pass ? "#00d2a0" : "#e8002d",
    marginLeft: "auto",
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0.5,
  }),
  gapRow: {
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
    background: "rgba(255,255,255,0.03)",
    border: "1px solid rgba(255,255,255,0.06)",
    borderRadius: 6,
    padding: "8px 12px",
    fontSize: 12,
    color: "#8fb6c4",
  },
  gapValue: {
    fontSize: 16,
    fontWeight: 700,
    color: "#eef1f0",
    fontVariantNumeric: "tabular-nums",
  },
};

function Indicator({ label, pass }) {
  return (
    <div style={s.indicator(pass)}>
      <div style={s.dot(pass)} />
      <span style={s.indicatorLabel}>{label}</span>
      <span style={s.indicatorValue(pass)}>
        {pass === null ? "--" : pass ? "PASS" : "FAIL"}
      </span>
    </div>
  );
}

export default function OvertakePanel({ overtake }) {
  injectStyle();

  const o = overtake || {};
  const withinTrigger = o.within_trigger ?? false;
  const shouldOvertake = o.should_overtake ?? false;
  const oiAdvisory = o.oi_advisory ?? o.oi_prediction ?? false;
  const ecDecision = o.ec_decision || null;

  // STRONG = RC + EC + OI all agree; WEAK = RC + EC pass but OI uncertain
  let bannerState = "idle";
  if (withinTrigger) {
    if (ecDecision === "STRIKE_NOW") {
      bannerState = oiAdvisory ? "strike_strong" : "strike_weak";
    } else if (ecDecision === "HOLD_THEN_STRIKE_LATER") {
      bannerState = "hold";
    } else if (ecDecision === "HARVEST_NOW") {
      bannerState = "harvest";
    } else if (shouldOvertake) {
      bannerState = oiAdvisory ? "strike_strong" : "strike_weak";
    } else {
      bannerState = "deny";
    }
  }

  let bannerText = "—  NO TARGET IN RANGE  —";
  if (bannerState === "strike_strong") bannerText = "⚡ STRIKE NOW — HIGH CONFIDENCE";
  if (bannerState === "strike_weak") bannerText = "⚡ STRIKE NOW — PROCEED WITH CAUTION";
  if (bannerState === "hold") bannerText = "⏳ HOLD & STRIKE LATER";
  if (bannerState === "harvest") bannerText = "🔋 HARVEST NOW";
  if (bannerState === "deny") bannerText = "✗ DO NOT OVERTAKE";

  // OI is advisory — show its state but label it clearly
  const oi = overtake ? (o.oi_advisory ?? o.oi_prediction ?? null) : null;
  const ec = overtake ? (o.ec ?? null) : null;
  const rc = overtake ? (o.rc ?? null) : null;

  const gapS = o.gap_seconds ?? null;

  return (
    <div style={s.root}>
      <div style={s.label}>Overtake Engine</div>

      {/* Decision banner */}
      <div style={s.banner(bannerState)}>
        <div style={s.bannerText(bannerState)}>{bannerText}</div>
      </div>

      {/* OI / EC / RC indicators */}
      <div style={s.subRow}>
        <Indicator label="OI *" pass={withinTrigger ? oi : null} />
        <Indicator label="EC" pass={withinTrigger ? ec : null} />
        <Indicator label="RC" pass={withinTrigger ? rc : null} />
      </div>
      {withinTrigger && (
        <div style={{ fontSize: 10, color: '#4a6470', marginBottom: 6, marginTop: -2 }}>
          * OI is advisory only (model under retraining)
        </div>
      )}

      {/* Gap display */}
      <div style={s.gapRow}>
        <span>Gap to car ahead</span>
        <span style={s.gapValue}>
          {gapS !== null && gapS !== undefined
            ? `${Number(gapS).toFixed(2)} s`
            : "— s"}
        </span>
      </div>
    </div>
  );
}
