import React from 'react';

const s = {
  root: {
    display: 'flex',
    flexDirection: 'column',
    gap: 20,
    width: '100%',
    color: '#eef1f0',
  },
  card: {
    background: 'rgba(10,20,26,0.55)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    padding: '20px',
  },
  title: {
    fontSize: 16,
    fontWeight: 700,
    marginBottom: 16,
    color: '#fff',
  },
  chartContainer: {
    width: '100%',
    height: 300,
    position: 'relative',
    background: 'rgba(0,0,0,0.2)',
    borderRadius: 8,
    border: '1px solid rgba(255,255,255,0.05)',
    overflow: 'hidden',
  },
  tableContainer: {
    maxHeight: 400,
    overflowY: 'auto',
    border: '1px solid rgba(255,255,255,0.05)',
    borderRadius: 8,
    background: 'rgba(0,0,0,0.2)',
  },
  table: {
    width: '100%',
    borderCollapse: 'collapse',
    fontSize: 13,
  },
  th: {
    textAlign: 'left',
    padding: '10px 14px',
    background: 'rgba(255,255,255,0.03)',
    borderBottom: '1px solid rgba(255,255,255,0.1)',
    color: '#8fb6c4',
    fontWeight: 700,
    position: 'sticky',
    top: 0,
    backdropFilter: 'blur(10px)',
  },
  td: {
    padding: '10px 14px',
    borderBottom: '1px solid rgba(255,255,255,0.03)',
    fontVariantNumeric: 'tabular-nums',
  },
  badge: (mode) => ({
    display: 'inline-block',
    padding: '3px 8px',
    borderRadius: 4,
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 0.5,
    background:
      mode === 'OVERTAKE' ? 'rgba(255,180,0,0.2)' :
      mode === 'HARVEST'  ? 'rgba(0,210,160,0.2)' :
                            'rgba(255,255,255,0.08)',
    color:
      mode === 'OVERTAKE' ? '#f5b942' :
      mode === 'HARVEST'  ? '#00d2a0' :
                            '#8fb6c4',
  }),
};

function formatTime(s) {
  if (s == null) return '--:--';
  const mins = Math.floor(s / 60);
  const secs = Math.floor(s % 60).toString().padStart(2, '0');
  return `${mins}:${secs}`;
}

export default function SocTrendPage({ socData = [], energyEvents = [], sessionTime }) {
  // Chart dimensions
  const width = 800; // SVG viewBox width
  const height = 200; // SVG viewBox height
  
  // Calculate SVG path
  let pathD = "";
  if (socData.length > 0) {
    const tMin = socData[0].t;
    const tMax = Math.max(tMin + 60, socData[socData.length - 1].t); // Ensure at least 60s scale
    const tRange = tMax - tMin;
    
    pathD = socData.map((d, i) => {
      const x = ((d.t - tMin) / tRange) * width;
      // Y is inverted (0 is top, height is bottom). SOC is 0-100%.
      const y = height - (d.soc / 100) * height;
      return `${i === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ');
  }

  return (
    <div style={s.root}>
      
      {/* Chart Card */}
      <div style={s.card}>
        <div style={s.title}>Live SOC Trend (State of Charge %)</div>
        <div style={s.chartContainer}>
          <svg viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
            {/* Grid lines */}
            <line x1="0" y1={height * 0.25} x2={width} y2={height * 0.25} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
            <line x1="0" y1={height * 0.50} x2={width} y2={height * 0.50} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
            <line x1="0" y1={height * 0.75} x2={width} y2={height * 0.75} stroke="rgba(255,255,255,0.05)" strokeWidth="1" />
            
            {/* The Line */}
            {pathD && (
              <path 
                d={pathD} 
                fill="none" 
                stroke="#00d2a0" 
                strokeWidth="2.5" 
                strokeLinejoin="round" 
              />
            )}
            
            {/* Current value dot */}
            {socData.length > 0 && (
              (() => {
                const last = socData[socData.length - 1];
                const tMin = socData[0].t;
                const tMax = Math.max(tMin + 60, last.t);
                const x = ((last.t - tMin) / (tMax - tMin)) * width;
                const y = height - (last.soc / 100) * height;
                return <circle cx={x} cy={y} r="4" fill="#fff" stroke="#00d2a0" strokeWidth="2" />;
              })()
            )}
          </svg>
          
          {/* Y-Axis Labels */}
          <div style={{ position: 'absolute', top: 5, left: 10, fontSize: 10, color: '#8fb6c4' }}>100%</div>
          <div style={{ position: 'absolute', top: '50%', left: 10, fontSize: 10, color: '#8fb6c4', transform: 'translateY(-50%)' }}>50%</div>
          <div style={{ position: 'absolute', bottom: 5, left: 10, fontSize: 10, color: '#8fb6c4' }}>0%</div>
        </div>
      </div>

      {/* History Table Card */}
      <div style={s.card}>
        <div style={s.title}>Energy State Change History</div>
        <div style={s.tableContainer}>
          <table style={s.table}>
            <thead>
              <tr>
                <th style={s.th}>Time</th>
                <th style={s.th}>Lap</th>
                <th style={s.th}>Event / Mode</th>
                <th style={s.th}>SOC %</th>
                <th style={s.th}>Details</th>
              </tr>
            </thead>
            <tbody>
              {energyEvents.length === 0 ? (
                <tr>
                  <td colSpan="5" style={{ ...s.td, textAlign: 'center', color: '#556e7a', padding: '20px' }}>
                    Waiting for energy events...
                  </td>
                </tr>
              ) : (
                [...energyEvents].reverse().map((ev, idx) => (
                  <tr key={idx}>
                    <td style={s.td}>{formatTime(ev.t)}</td>
                    <td style={s.td}>{ev.lap}</td>
                    <td style={s.td}>
                      <span style={s.badge(ev.mode)}>{ev.mode}</span>
                    </td>
                    <td style={s.td}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                        <div style={{ width: 40, height: 4, background: 'rgba(255,255,255,0.1)', borderRadius: 2 }}>
                          <div style={{ width: `${ev.soc}%`, height: '100%', background: '#00d2a0', borderRadius: 2 }} />
                        </div>
                        {ev.soc.toFixed(1)}%
                      </div>
                    </td>
                    <td style={{ ...s.td, color: '#8fb6c4', fontSize: 12 }}>
                      {ev.details}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

    </div>
  );
}
