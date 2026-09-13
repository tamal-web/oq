import React, { useState, useEffect } from 'react';

const styles = {
  root: {
    minHeight: '100vh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'linear-gradient(160deg, #0d2f3f 0%, #12181c 55%, #17191d 100%)',
    fontFamily: '-apple-system, "Segoe UI", Roboto, Inter, sans-serif',
  },
  card: {
    background: 'rgba(10,20,26,0.85)',
    border: '1px solid rgba(255,255,255,0.1)',
    borderRadius: 16,
    padding: '40px 44px',
    maxWidth: 580,
    width: '100%',
    color: '#eef1f0',
  },
  badge: {
    display: 'inline-block',
    background: '#e8002d',
    color: '#fff',
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: 1.5,
    padding: '3px 8px',
    borderRadius: 4,
    marginBottom: 12,
  },
  title: {
    fontSize: 28,
    fontWeight: 800,
    color: '#fff',
    margin: '0 0 4px',
    letterSpacing: -0.5,
  },
  subtitle: {
    fontSize: 13,
    color: '#8fb6c4',
    marginBottom: 32,
  },
  sectionLabel: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 1.5,
    color: '#8fb6c4',
    textTransform: 'uppercase',
    marginBottom: 10,
  },
  circuitRow: {
    display: 'flex',
    alignItems: 'center',
    gap: 10,
    background: 'rgba(232,0,45,0.08)',
    border: '1px solid rgba(232,0,45,0.25)',
    borderRadius: 8,
    padding: '12px 16px',
    marginBottom: 28,
  },
  circuitIcon: {
    fontSize: 20,
  },
  circuitText: {
    flex: 1,
  },
  circuitName: {
    fontSize: 15,
    fontWeight: 700,
    color: '#fff',
  },
  circuitNote: {
    fontSize: 11,
    color: '#8fb6c4',
    marginTop: 2,
  },
  yearGrid: {
    display: 'flex',
    gap: 12,
    marginBottom: 28,
  },
  yearBtn: (selected) => ({
    flex: 1,
    padding: '12px 0',
    background: selected ? '#e8002d' : 'rgba(255,255,255,0.05)',
    border: selected ? '1px solid #e8002d' : '1px solid rgba(255,255,255,0.1)',
    borderRadius: 8,
    color: selected ? '#fff' : '#8fb6c4',
    fontSize: 16,
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.15s',
  }),
  driverGrid: {
    display: 'flex',
    flexWrap: 'wrap',
    gap: 8,
    marginBottom: 28,
    minHeight: 44,
  },
  driverBtn: (selected, color) => ({
    padding: '8px 14px',
    background: selected ? color : 'rgba(255,255,255,0.05)',
    border: `1px solid ${selected ? color : 'rgba(255,255,255,0.1)'}`,
    borderRadius: 6,
    color: '#fff',
    fontSize: 13,
    fontWeight: 700,
    cursor: 'pointer',
    transition: 'all 0.15s',
    letterSpacing: 0.3,
  }),
  startBtn: (disabled) => ({
    width: '100%',
    padding: '14px 0',
    background: disabled ? 'rgba(255,255,255,0.05)' : '#e8002d',
    border: 'none',
    borderRadius: 10,
    color: disabled ? '#556e7a' : '#fff',
    fontSize: 15,
    fontWeight: 800,
    letterSpacing: 0.5,
    cursor: disabled ? 'not-allowed' : 'pointer',
    transition: 'all 0.15s',
  }),
  footer: {
    marginTop: 20,
    fontSize: 11,
    color: '#4a6470',
    textAlign: 'center',
    lineHeight: 1.6,
  },
  loadingText: {
    color: '#8fb6c4',
    fontSize: 13,
    fontStyle: 'italic',
  },
};

export default function RaceSelector({ onStart }) {
  const [years, setYears] = useState([]);
  const [selectedYear, setSelectedYear] = useState(null);
  const [selectedDriver, setSelectedDriver] = useState(null);
  const [drivers, setDrivers] = useState([]);
  const [loadingDrivers, setLoadingDrivers] = useState(false);
  const [loadingYears, setLoadingYears] = useState(true);

  // Fetch supported years on mount
  useEffect(() => {
    fetch('http://localhost:8000/races')
      .then((r) => r.json())
      .then((data) => {
        setYears(data.years || []);
        setLoadingYears(false);
      })
      .catch(() => {
        setYears([]);
        setLoadingYears(false);
      });
  }, []);

  // Fetch drivers when year changes
  useEffect(() => {
    if (!selectedYear) {
      setDrivers([]);
      setSelectedDriver(null);
      return;
    }
    setLoadingDrivers(true);
    setSelectedDriver(null);
    fetch(`http://localhost:8000/drivers/${selectedYear}`)
      .then((r) => r.json())
      .then((data) => {
        setDrivers(data.drivers || []);
        setLoadingDrivers(false);
      })
      .catch(() => {
        setDrivers([]);
        setLoadingDrivers(false);
      });
  }, [selectedYear]);

  const canStart = selectedYear !== null && selectedDriver !== null;

  return (
    <div style={styles.root}>
      <div style={styles.card}>
        <div style={styles.badge}>MONACO ONLY</div>
        <h1 style={styles.title}>F1 Overtake Intelligence</h1>
        <p style={styles.subtitle}>
          2026 Energy Regulations · Monaco Grand Prix · Historical Race Replay
        </p>

        {/* Circuit — fixed, not selectable */}
        <div style={styles.sectionLabel}>Circuit</div>
        <div style={styles.circuitRow}>
          <span style={styles.circuitIcon}>🏎</span>
          <div style={styles.circuitText}>
            <div style={styles.circuitName}>Monaco Grand Prix</div>
            <div style={styles.circuitNote}>
              Circuit de Monaco · OI model is Monaco-specific
            </div>
          </div>
          <div style={{ fontSize: 11, color: '#e8002d', fontWeight: 700 }}>FIXED</div>
        </div>

        {/* Year selector */}
        <div style={styles.sectionLabel}>Race Year</div>
        <div style={{ marginBottom: 28 }}>
          {loadingYears ? (
            <span style={styles.loadingText}>Loading supported years...</span>
          ) : (
            <select
              style={{
                width: '100%',
                padding: '12px 16px',
                background: 'rgba(255,255,255,0.05)',
                border: '1px solid rgba(255,255,255,0.1)',
                borderRadius: 8,
                color: '#fff',
                fontSize: 16,
                fontWeight: 700,
                outline: 'none',
                cursor: 'pointer',
              }}
              value={selectedYear || ''}
              onChange={(e) => setSelectedYear(e.target.value ? parseInt(e.target.value, 10) : null)}
            >
              <option value="" style={{ color: '#000' }}>-- Select Monaco GP Year --</option>
              {[...years].reverse().map((y) => (
                <option key={y} value={y} style={{ color: '#000' }}>
                  {y} Monaco Grand Prix
                </option>
              ))}
            </select>
          )}
        </div>

        {/* Driver selector */}
        <div style={styles.sectionLabel}>Your Driver (Attacker)</div>
        <div style={styles.driverGrid}>
          {!selectedYear && (
            <span style={styles.loadingText}>Select a year to load drivers…</span>
          )}
          {selectedYear && loadingDrivers && (
            <span style={styles.loadingText}>Loading drivers…</span>
          )}
          {selectedYear && !loadingDrivers && drivers.length === 0 && (
            <span style={styles.loadingText}>No drivers found (is the server running?)</span>
          )}
          {drivers.map((d) => (
            <button
              key={d.code}
              style={styles.driverBtn(selectedDriver === d.code, d.color)}
              onClick={() => setSelectedDriver(d.code)}
              title={d.team}
            >
              {d.full_name}
            </button>
          ))}
        </div>

        {/* Start */}
        <button
          style={styles.startBtn(!canStart)}
          disabled={!canStart}
          onClick={() => canStart && onStart(selectedYear, selectedDriver)}
        >
          {canStart ? `▶  Start Monaco ${selectedYear} Replay as ${selectedDriver}` : '▶  Select Year & Driver'}
        </button>

        <p style={styles.footer}>
          Monaco Grand Prix only · OI model trained on 2022–2024 Monaco GP data
          <br />
          Car ahead is identified automatically from race position data
        </p>
      </div>
    </div>
  );
}
