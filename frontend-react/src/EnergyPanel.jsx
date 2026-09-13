import React, { useState } from 'react';

const s = {
  root: {
    background: 'rgba(10,20,26,0.55)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    padding: '16px 18px',
    color: '#eef1f0',
    fontFamily: '-apple-system, "Segoe UI", Roboto, Inter, sans-serif',
  },
  headerRow: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    marginBottom: 14,
  },
  label: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 1.5,
    color: '#8fb6c4',
    textTransform: 'uppercase',
  },
  toggleBtn: (active) => ({
    background: active ? 'rgba(0, 210, 160, 0.15)' : 'rgba(255,255,255,0.05)',
    border: `1px solid ${active ? 'rgba(0, 210, 160, 0.4)' : 'rgba(255,255,255,0.1)'}`,
    color: active ? '#00d2a0' : '#8fb6c4',
    padding: '4px 8px',
    borderRadius: 6,
    fontSize: 10,
    fontWeight: 700,
    cursor: 'pointer',
    letterSpacing: 0.5,
    transition: 'all 0.2s',
  }),
  socRow: {
    marginBottom: 16,
  },
  socHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'baseline',
    marginBottom: 6,
  },
  socTitle: { fontSize: 12, color: '#8fb6c4' },
  socValue: { fontSize: 20, fontWeight: 700, color: '#fff', fontVariantNumeric: 'tabular-nums' },
  barBg: {
    height: 8,
    background: 'rgba(255,255,255,0.08)',
    borderRadius: 4,
    overflow: 'hidden',
  },
  bar: (pct) => ({
    height: '100%',
    width: `${Math.max(0, Math.min(100, pct))}%`,
    background: pct > 60 ? '#00d2a0' : pct > 30 ? '#f5b942' : '#e8002d',
    borderRadius: 4,
    transition: 'width 0.2s ease, background 0.3s ease',
  }),
  oppBar: (pct) => ({
    height: 2,
    width: `${Math.max(0, Math.min(100, pct))}%`,
    background: '#8fb6c4',
    marginTop: 2,
    transition: 'width 0.2s ease',
  }),
  modeRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 8,
    marginBottom: 16,
  },
  modeBadge: (mode) => ({
    padding: '3px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 1,
    background:
      mode === 'OVERTAKE' ? 'rgba(255,180,0,0.2)' :
      mode === 'HARVEST'  ? 'rgba(0,210,160,0.2)' :
                            'rgba(255,255,255,0.08)',
    color:
      mode === 'OVERTAKE' ? '#f5b942' :
      mode === 'HARVEST'  ? '#00d2a0' :
                            '#8fb6c4',
    border: `1px solid ${
      mode === 'OVERTAKE' ? 'rgba(245,185,66,0.4)' :
      mode === 'HARVEST'  ? 'rgba(0,210,160,0.4)' :
                            'rgba(255,255,255,0.1)'
    }`,
  }),
  omBadge: {
    padding: '3px 10px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0.5,
    background: 'rgba(255,180,0,0.15)',
    color: '#f5b942',
    border: '1px solid rgba(245,185,66,0.35)',
  },
  grid: {
    display: 'grid',
    gridTemplateColumns: '1fr 1fr',
    gap: '10px 14px',
  },
  metric: {
    background: 'rgba(255,255,255,0.03)',
    border: '1px solid rgba(255,255,255,0.06)',
    borderRadius: 6,
    padding: '8px 10px',
  },
  metricLabel: {
    fontSize: 10,
    color: '#556e7a',
    fontWeight: 600,
    letterSpacing: 0.5,
    marginBottom: 3,
    textTransform: 'uppercase',
  },
  metricValueContainer: {
    display: 'flex',
    flexDirection: 'column',
    gap: 2,
  },
  metricValue: {
    fontSize: 15,
    fontWeight: 700,
    color: '#eef1f0',
    fontVariantNumeric: 'tabular-nums',
  },
  oppValue: {
    fontSize: 11,
    fontWeight: 600,
    color: '#8fb6c4',
    fontVariantNumeric: 'tabular-nums',
    borderTop: '1px solid rgba(255,255,255,0.05)',
    paddingTop: 2,
    marginTop: 2,
    display: 'flex',
    alignItems: 'center',
    gap: 4
  },
  metricUnit: {
    fontSize: 10,
    color: '#556e7a',
    marginLeft: 2,
  },
};

function Metric({ label, value, unit, oppValue, showOpponent }) {
  return (
    <div style={s.metric}>
      <div style={s.metricLabel}>{label}</div>
      <div style={s.metricValueContainer}>
        <div style={s.metricValue}>
          {value}
          {unit && value !== '--' && <span style={s.metricUnit}>{unit}</span>}
        </div>
        {showOpponent && (
          <div style={s.oppValue}>
            <span style={{ fontSize: 9, opacity: 0.6, letterSpacing: 0.5 }}>VS</span>
            {oppValue}
            {unit && oppValue !== '--' && <span style={s.metricUnit}>{unit}</span>}
          </div>
        )}
      </div>
    </div>
  );
}

function fmt(v, decimals = 2) {
  if (v === null || v === undefined) return '--';
  return Number(v).toFixed(decimals);
}

export default function EnergyPanel({ energy, opponentEnergy }) {
  const [showOpponent, setShowOpponent] = useState(false);

  const e = energy || {};
  const soc = e.soc_pct ?? null;
  const mode = e.mode || 'NORMAL';

  const oe = opponentEnergy || {};
  const oppSoc = oe.soc_pct ?? null;

  return (
    <div style={s.root}>
      <div style={s.headerRow}>
        <div style={s.label}>Energy Engine</div>
        <button 
          style={s.toggleBtn(showOpponent)} 
          onClick={() => setShowOpponent(!showOpponent)}
        >
          {showOpponent ? 'HIDE OPPONENT' : 'COMPARE OPPONENT'}
        </button>
      </div>

      {/* SOC bar */}
      <div style={s.socRow}>
        <div style={s.socHeader}>
          <span style={s.socTitle}>State of Charge</span>
          <span style={s.socValue}>{soc !== null ? `${fmt(soc, 1)}%` : '--'}</span>
        </div>
        <div style={s.barBg}>
          <div style={s.bar(soc ?? 0)} />
        </div>
        {showOpponent && oppSoc !== null && (
          <div style={s.oppBar(oppSoc)} title={`Opponent SOC: ${fmt(oppSoc, 1)}%`} />
        )}
        {soc !== null && (
          <div style={{ fontSize: 11, color: '#556e7a', marginTop: 4 }}>
            {fmt(e.soc_mj, 3)} MJ / 4.0 MJ capacity
            {showOpponent && oe.soc_mj != null && ` (Opponent: ${fmt(oe.soc_mj, 3)} MJ)`}
          </div>
        )}
      </div>

      {/* Mode + Overtake Mode badge */}
      <div style={s.modeRow}>
        <div style={s.modeBadge(mode)}>{mode}</div>
        {e.overtake_mode_earned && (
          <div style={s.omBadge}>⚡ OVERTAKE MODE AVAILABLE</div>
        )}
      </div>

      {/* Metrics grid */}
      <div style={s.grid}>
        <Metric 
          label="Deploy Lap" 
          value={fmt(e.energy_deployed_lap_mj)} 
          oppValue={fmt(oe.energy_deployed_lap_mj)} 
          unit="MJ" 
          showOpponent={showOpponent} 
        />
        <Metric 
          label="Harvest Lap" 
          value={fmt(e.energy_regen_lap_mj)} 
          oppValue={fmt(oe.energy_regen_lap_mj)} 
          unit="MJ" 
          showOpponent={showOpponent} 
        />
        <Metric 
          label="P Deploy" 
          value={fmt(e.p_deploy_instant_kw, 0)} 
          oppValue={fmt(oe.p_deploy_instant_kw, 0)} 
          unit="kW" 
          showOpponent={showOpponent} 
        />
        <Metric 
          label="P Regen" 
          value={fmt(e.p_regen_instant_kw, 0)} 
          oppValue={fmt(oe.p_regen_instant_kw, 0)} 
          unit="kW" 
          showOpponent={showOpponent} 
        />
        <Metric 
          label="Budget Left" 
          value={fmt(e.energy_remaining_lap_mj)} 
          oppValue={fmt(oe.energy_remaining_lap_mj)} 
          unit="MJ" 
          showOpponent={showOpponent} 
        />
        <Metric 
          label="Bonus Left" 
          value={fmt(e.overtake_mode_bonus_remaining_mj)} 
          oppValue={fmt(oe.overtake_mode_bonus_remaining_mj)} 
          unit="MJ" 
          showOpponent={showOpponent} 
        />
      </div>
    </div>
  );
}
