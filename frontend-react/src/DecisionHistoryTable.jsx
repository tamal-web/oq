import React, { useState, useEffect } from 'react';

const s = {
  root: {
    background: 'rgba(10,20,26,0.55)',
    border: '1px solid rgba(255,255,255,0.08)',
    borderRadius: 10,
    padding: '16px 18px',
    color: '#eef1f0',
    fontFamily: '-apple-system, "Segoe UI", Roboto, Inter, sans-serif',
    marginTop: 14,
    display: 'flex',
    flexDirection: 'column',
    maxHeight: 320,
  },
  label: {
    fontSize: 11,
    fontWeight: 700,
    letterSpacing: 1.5,
    color: '#8fb6c4',
    textTransform: 'uppercase',
    marginBottom: 14,
    flexShrink: 0,
  },
  table: {
    width: '100%',
    display: 'grid',
    gridTemplateColumns: '110px 130px 1fr 1fr 1fr',
    gap: '8px',
    fontSize: 12,
  },
  headerRow: {
    display: 'grid',
    gridTemplateColumns: '110px 130px 1fr 1fr 1fr',
    gap: '8px',
    paddingBottom: 8,
    borderBottom: '1px solid rgba(255,255,255,0.1)',
    color: '#8fb6c4',
    fontWeight: 600,
    letterSpacing: 0.5,
    flexShrink: 0,
  },
  scrollArea: {
    overflowY: 'auto',
    flexGrow: 1,
    paddingRight: 4,
    marginTop: 8,
  },
  row: {
    display: 'grid',
    gridTemplateColumns: '110px 130px 1fr 1fr 1fr',
    gap: '8px',
    padding: '6px 0',
    borderBottom: '1px solid rgba(255,255,255,0.04)',
    alignItems: 'center',
  },
  passCell: {
    color: '#00d2a0',
    fontWeight: 900,
    fontSize: 14,
  },
  failCell: {
    color: '#e8002d',
    fontSize: 10,
    lineHeight: 1.2,
  }
};

const formatTime = (s) => {
  if (s == null) return '--';
  const mins = Math.floor(s / 60);
  const secs = (s % 60).toFixed(1);
  return `${mins}:${secs.padStart(4, '0')}`;
};

export default function DecisionHistoryTable({ overtake, sessionTime }) {
  const [history, setHistory] = useState([]);

  useEffect(() => {
    setHistory((prev) => {
      if (!overtake || sessionTime === null || sessionTime === undefined) return prev;

      // Reset history if time jumps backwards significantly (e.g. new race started)
      if (prev.length > 0 && sessionTime < prev[0].startTime - 5) {
        return [];
      }

      const currentState = {
        oi: overtake.oi_prediction,
        ec: overtake.ec,
        rc: overtake.rc,
        within: overtake.within_trigger,
        decision: overtake.should_overtake,
        oiReason: overtake.oi_reason || "Out of trigger zone",
        ecReason: overtake.ec_reason || "Out of trigger zone",
        rcReason: overtake.rc_reason || "Out of trigger zone",
      };

      if (prev.length === 0) {
        return [{ ...currentState, startTime: sessionTime, endTime: sessionTime }];
      }

      const active = prev[0];
      const isSame =
        active.oi === currentState.oi &&
        active.ec === currentState.ec &&
        active.rc === currentState.rc &&
        active.within === currentState.within;

      if (isSame) {
        // Update end time of active period
        const updatedActive = { ...active, endTime: sessionTime };
        return [updatedActive, ...prev.slice(1)];
      } else {
        // State changed, start a new period at the top
        const newActive = { ...currentState, startTime: sessionTime, endTime: sessionTime };
        return [newActive, ...prev];
      }
    });
  }, [overtake, sessionTime]);

  const renderSub = (pass, reason) => {
    if (pass) return <div style={s.passCell}>✓</div>;
    return <div style={s.failCell}>{reason}</div>;
  };

  const renderDecision = (row) => {
    if (!row.within) return <span style={{ color: '#4a6470', fontWeight: 600 }}>NO TARGET</span>;
    if (row.decision) return <span style={{ color: '#00d2a0', fontWeight: 800 }}>SHOULD OVERTAKE</span>;
    return <span style={{ color: '#e8002d', fontWeight: 700 }}>HOLD</span>;
  };

  return (
    <div style={s.root}>
      <div style={s.label}>Decision History</div>
      <div style={s.headerRow}>
        <div>Period</div>
        <div>Decision</div>
        <div>OI</div>
        <div>EC</div>
        <div>RC</div>
      </div>
      <div style={s.scrollArea}>
        {history.map((row, i) => {
          const isCurrent = i === 0;
          const timeDisplay = isCurrent 
            ? `${formatTime(row.startTime)} —` 
            : `${formatTime(row.startTime)} - ${formatTime(row.endTime)}`;
          
          return (
            <div key={row.startTime} style={{...s.row, opacity: isCurrent ? 1 : 0.6}}>
              <div style={{ color: isCurrent ? '#fff' : '#8fb6c4', fontVariantNumeric: 'tabular-nums' }}>
                {timeDisplay}
              </div>
              <div>{renderDecision(row)}</div>
              {/* Only show sub-component details if we are within trigger zone, else they are all N/A basically, but the UI requested reason if failed */}
              {row.within ? (
                <>
                  <div>{renderSub(row.oi, row.oiReason)}</div>
                  <div>{renderSub(row.ec, row.ecReason)}</div>
                  <div>{renderSub(row.rc, row.rcReason)}</div>
                </>
              ) : (
                <>
                  <div style={s.failCell}>N/A</div>
                  <div style={s.failCell}>N/A</div>
                  <div style={s.failCell}>N/A</div>
                </>
              )}
            </div>
          );
        })}
        {history.length === 0 && (
          <div style={{ padding: '16px 0', color: '#4a6470', fontSize: 13, textAlign: 'center' }}>
            Awaiting telemetry...
          </div>
        )}
      </div>
    </div>
  );
}
