import React, { useEffect, useRef, useState, useCallback, useId } from "react";

/**
 * MonacoTrack
 * Prop-driven Monaco Grand Prix circuit visualiser.
 * Receives car positions from the WebSocket via props — no internal animation loop.
 *
 * Props:
 *   cars          — array of car objects from the backend tick message
 *   lap           — current lap number of the selected driver
 *   totalLaps     — total race laps
 *   playing       — boolean playback state
 *   speed         — replay speed multiplier
 *   onSpeedChange — callback(newSpeed: number)
 *   onPlayPause   — callback()
 *   status        — 'loading' | 'racing' | 'finished' | null
 *   statusMessage — string shown on the loading overlay
 */

// ── Track geometry ────────────────────────────────────────────────────────────
// Real Circuit de Monaco outline (current GP layout, 2015–present).
const TRACK_PATH =
  "M118.34 246.687c-5.14.774-6.994 2.392-9.853 7.317-4.586 7.898-9.192 18.211-11.413 27.357-2.486 10.243-2.829 25.557-1.95 39.458.445 7.034 2.23 10.04 8.243 12.045 7.17 2.387 8.339 2.488 9.949 9.801 1.61 7.319 6.389 33.36 8.047 42.434 1.188 6.495 2.042 8.91-3.805 11.704-6.436 3.07-7.9 3.95-6.729 9.07 1.17 5.12 6.805 23.714 11.023 30.435 11.51 18.336 19.262 23.945 27.311 26.726 5.165 1.784 11.935 2.284 13.315 7.946 1.317 5.416 1.181 7.937-2.341 9.074-13.167 4.244-26.043 5.56-38.334 5.268-4.24-.102-4.829-.294-4.245-5.56.442-3.967.44-9.514-3.803-14.047-3.322-3.553-10.24-13.756-16.093-28.531-9.486-23.955-16.97-48.602-19.168-60.132-2.924-15.363-5.422-36.152-6.435-49.746-1.903-25.458-.928-45.988 3.217-55.89 5.267-12.585 6.437-17.12 5.999-21.07-.878-7.9-.355-10.97 4.242-12.437 14.192-4.535 27.36-4.242 37.456-5.852 10.094-1.609 27.134-4.495 33.651-6.439 8.34-2.486 23.423-7.227 36.577-9.363 11.704-1.903 21.801-3.073 32.774-8.34 6.195-2.974 21.8-11.119 28.384-13.169 6.585-2.046 18.713-4.606 25.75-6.143 8.048-1.759 17.221-3.118 23.994-4.534 9.32-1.953 25.118-13.113 27.46-27.898 2.535-15.996-2.563-24.582-12.876-33.749-7.022-6.243-11.658-11.657-12.68-15.461-1.987-7.38.472-12.368 3.803-16.97 4.974-6.877 50.625-68.034 53.99-72.277 3.366-4.244 6.436-3.658 9.95-.88 3.509 2.783 7.415 5.432 7.023 10.39-.438 5.56-.515 9.95 1.757 13.607 2.632 4.244 3.365 5.121 6.585 9.51 2.136 2.914 3.949 5.707 5.121 9.51 1.097 3.565 6.103 5.143 8.922 2.633 2.632-2.341 3.073-6.585-.876-9.51-1.636-1.211-3.58-2.506-5.269-5.12-2.926-4.537-5.415-7.9-7.168-10.681-1.389-2.204-3.13-11.026 2.778-12.73 8.632-2.487 19.607-5.853 25.31-7.608 2.719-.835 11.123-.146 11.123 8.34 0 8.485-.294 17.848-1.17 25.896-.394 3.597-3.482 47.7-22.192 77.593-23.132 36.952-62.28 63.471-70.912 68.28-19.604 10.923-39.682 17.952-46.525 19.703-12.584 3.218-28.287 4.485-42.725 6.437-3.529.476-5.299 3.87-5.074 5.463.586 4.098-.946 5.21-4.484 5.852-8.585 1.563-10.73 2.731-12.486-.388-1.8-3.2-3.085-2.424-7.805-1.759-15.215 2.147-86.663 12.827-97.344 14.435z";

const CORNER_LABELS = [
  { frac: 0.0,  text: "Start / Finish",      dy: -10 },
  { frac: 0.07, text: "Sainte Dévote",        dy: 14  },
  { frac: 0.19, text: "Swimming Pool",         dy: 14  },
  { frac: 0.33, text: "La Rascasse",           dy: -10 },
  { frac: 0.44, text: "Casino Square",         dy: -10 },
  { frac: 0.58, text: "Grand Hotel Hairpin",   dy: -10 },
  { frac: 0.71, text: "Portier",               dy: 14  },
  { frac: 0.86, text: "Tunnel",                dy: 14  },
];

export default function MonacoTrack({
  cars = [],
  lap = 1,
  totalLaps = 78,
  playing = true,
  speed = 1,
  onSpeedChange,
  onPlayPause,
  status = null,
  statusMessage = '',
}) {
  const pathRef = useRef(null);
  const uid = useId().replace(/[:]/g, "");
  const [pathLen, setPathLen] = useState(0);

  useEffect(() => {
    if (pathRef.current) setPathLen(pathRef.current.getTotalLength());
  }, []);

  const pointAt = useCallback(
    (progress) => {
      if (!pathRef.current || pathLen === 0) return { x: 0, y: 0, angle: 0 };
      const norm = ((progress % 1) + 1) % 1;
      const d = norm * pathLen;
      const p1 = pathRef.current.getPointAtLength(d);
      const p2 = pathRef.current.getPointAtLength(Math.min(pathLen, d + 1));
      const angle = (Math.atan2(p2.y - p1.y, p2.x - p1.x) * 180) / Math.PI;
      return { x: p1.x, y: p1.y, angle };
    },
    [pathLen]
  );

  // Sort cars by position for the leaderboard panel
  const ranked = [...cars].sort((a, b) => (a.position || 99) - (b.position || 99));
  const leaderLap = ranked[0]?.lap ?? lap;
  const raceOver = status === 'finished';

  const isLoading = status === 'loading';

  return (
    <div
      className={`mlr-${uid} mlr-root`}
      style={{ fontFamily: '-apple-system, "Segoe UI", Roboto, Inter, sans-serif' }}
    >
      <div
        style={{
          display: "flex",
          flexWrap: "wrap",
          gap: 16,
          background: "linear-gradient(160deg, #0d2f3f 0%, #12181c 55%, #17191d 100%)",
          padding: 20,
          borderRadius: 14,
          color: "#eef1f0",
        }}
      >
        {/* ── Track panel ──────────────────────────────────────────── */}
        <div style={{ flex: "1 1 460px", minWidth: 280 }}>
          {/* Header */}
          <div
            style={{
              display: "flex",
              alignItems: "baseline",
              justifyContent: "space-between",
              marginBottom: 8,
            }}
          >
            <div>
              <div style={{ fontSize: 12, letterSpacing: 1, color: "#8fb6c4" }}>
                Formula 1 · Circuit de Monaco
              </div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>
                Monaco Grand Prix — Live Replay
              </div>
            </div>
            <div style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>
              <div style={{ fontSize: 12, color: "#8fb6c4" }}>Lap</div>
              <div style={{ fontSize: 22, fontWeight: 700 }}>
                {Math.min(lap, totalLaps)} / {totalLaps}
              </div>
            </div>
          </div>

          {/* SVG track */}
          <div style={{ position: 'relative' }}>
            <svg
              viewBox="40 -10 420 520"
              style={{
                width: "100%",
                height: "auto",
                borderRadius: 10,
                background:
                  "radial-gradient(circle at 30% 20%, #123a4d 0%, #0c222c 55%, #0a1a22 100%)",
                display: 'block',
              }}
            >
              {/* Track shadow / kerb bed */}
              <path d={TRACK_PATH} fill="none" stroke="#c81e2c" strokeWidth="10.6"
                strokeLinecap="round" strokeLinejoin="round" opacity="0.9" />
              {/* Track surface */}
              <path d={TRACK_PATH} fill="none" stroke="#3d4249" strokeWidth="9"
                strokeLinecap="round" strokeLinejoin="round" />
              {/* Kerb dashes */}
              <path d={TRACK_PATH} fill="none" stroke="#e8e8e2" strokeWidth="9.6"
                strokeLinecap="butt" strokeLinejoin="round"
                strokeDasharray="2 5.5" opacity="0.16" />
              {/* Centreline */}
              <path d={TRACK_PATH} fill="none" stroke="#f2e9c9" strokeWidth="0.5"
                strokeDasharray="3 4" opacity="0.55" />
              {/* Hidden measuring path */}
              <path ref={pathRef} d={TRACK_PATH} fill="none" stroke="none" />

              {/* Start / finish line */}
              {pathLen > 0 && (() => {
                const { x, y, angle } = pointAt(0);
                return (
                  <g transform={`translate(${x} ${y}) rotate(${angle})`}>
                    <rect x="-1" y="-6" width="2" height="12" fill="#fff" />
                  </g>
                );
              })()}

              {/* Corner labels */}
              {pathLen > 0 && CORNER_LABELS.map((c) => {
                const { x, y } = pointAt(c.frac);
                return (
                  <text key={c.text} x={x} y={y + c.dy} fontSize="6.5"
                    fill="#9fc4d4" textAnchor="middle" opacity="0.85">
                    {c.text}
                  </text>
                );
              })}

              {/* Cars */}
              {pathLen > 0 && cars.map((c) => {
                const prog = typeof c.progress === 'number' ? c.progress : 0;
                const { x, y, angle } = pointAt(prog);
                const isSelected = c.is_selected;
                const w = isSelected ? 7.0 : 5.8;
                const h = isSelected ? 3.6 : 3.0;
                return (
                  <g key={c.code} transform={`translate(${x} ${y}) rotate(${angle})`}>
                    {/* Highlight ring for selected driver */}
                    {isSelected && (
                      <rect x={-(w / 2) - 1.5} y={-(h / 2) - 1.5}
                        width={w + 3} height={h + 3} rx="2"
                        fill="none" stroke="#fff" strokeWidth="0.7" opacity="0.7" />
                    )}
                    <g transform="translate(0,0)">
                      <rect x={-(w / 2)} y={-(h / 2)} width={w} height={h}
                        rx="1.1" fill={c.color || '#888'} stroke={c.accent || '#444'} strokeWidth="0.4" />
                      <rect x={-(w / 2) - 0.6} y="-0.5" width="0.8" height="1" fill="#111" />
                      <rect x={w / 2 - 0.2} y="-0.5" width="0.8" height="1" fill="#111" />
                    </g>
                    <text x="0" y={-(h / 2) - 1.5} fontSize="2.6" fill="#fff"
                      textAnchor="middle" transform={`rotate(${-angle})`}
                      style={{ fontWeight: 700, paintOrder: 'stroke', stroke: '#000', strokeWidth: 0.7 }}>
                      {c.code}
                    </text>
                  </g>
                );
              })}
            </svg>

            {/* Loading overlay */}
            {isLoading && (
              <div style={{
                position: 'absolute', inset: 0,
                background: 'rgba(10,20,26,0.75)',
                borderRadius: 10,
                display: 'flex', flexDirection: 'column',
                alignItems: 'center', justifyContent: 'center',
                gap: 12,
              }}>
                <div style={{
                  width: 36, height: 36,
                  border: '3px solid rgba(255,255,255,0.15)',
                  borderTopColor: '#e8002d',
                  borderRadius: '50%',
                  animation: 'spin 0.8s linear infinite',
                }} />
                <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
                <div style={{ color: '#8fb6c4', fontSize: 13, textAlign: 'center', maxWidth: 260 }}>
                  {statusMessage || 'Loading telemetry…'}
                </div>
              </div>
            )}
          </div>

          {/* Controls */}
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 12, flexWrap: "wrap" }}>
            <button
              onClick={onPlayPause}
              disabled={raceOver}
              style={{
                background: raceOver ? "#3a3f44" : "#e8002d",
                color: "#fff", border: "none", borderRadius: 8,
                padding: "8px 16px", fontWeight: 700,
                cursor: raceOver ? "default" : "pointer", letterSpacing: 0.4,
              }}
            >
              {raceOver ? "Race Finished" : playing ? "Pause" : "Resume"}
            </button>

            <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, color: "#c7d8de" }}>
              Speed
              <input
                type="range" min="0.25" max="8" step="0.25"
                value={speed}
                onChange={(e) => onSpeedChange && onSpeedChange(parseFloat(e.target.value))}
              />
              <span style={{ fontVariantNumeric: "tabular-nums", width: 36, display: "inline-block" }}>
                {Number(speed).toFixed(2)}x
              </span>
            </label>
          </div>
        </div>

        {/* ── Leaderboard panel ─────────────────────────────────────── */}
        <div style={{ flex: "1 1 200px", minWidth: 180 }}>
          <div style={{ fontSize: 12, letterSpacing: 1, color: "#8fb6c4", marginBottom: 8 }}>
            LIVE TIMING
          </div>
          <div style={{
            background: "rgba(10,20,26,0.55)",
            border: "1px solid rgba(255,255,255,0.08)",
            borderRadius: 10, overflow: "hidden",
          }}>
            {ranked.length === 0 ? (
              <div style={{ padding: '12px 10px', color: '#4a6470', fontSize: 13 }}>
                Waiting for race data…
              </div>
            ) : ranked.map((c) => {
              const lapDiff = leaderLap - (c.lap || 1);
              const gapLabel = c.position === 1 ? 'Leader'
                : lapDiff > 0 ? `+${lapDiff} lap${lapDiff > 1 ? 's' : ''}`
                : `Lap ${c.lap || 1}`;
              return (
                <div key={c.code} style={{
                  display: "flex", alignItems: "center", gap: 10,
                  padding: "7px 10px",
                  borderBottom: "1px solid rgba(255,255,255,0.06)",
                  fontVariantNumeric: "tabular-nums",
                  background: c.is_selected ? 'rgba(232,0,45,0.08)' : 'transparent',
                }}>
                  <div style={{ width: 18, textAlign: "right", color: "#8fb6c4", fontSize: 13 }}>
                    {c.position}
                  </div>
                  <div style={{ width: 4, height: 18, borderRadius: 2, background: c.color }} />
                  <div style={{ flex: 1, fontSize: 13, fontWeight: c.is_selected ? 800 : 600 }}>
                    {c.full_name || c.code}
                    {c.is_selected && <span style={{ color: '#e8002d', marginLeft: 4 }}>★</span>}
                    {' '}
                    <span style={{ color: "#8a9aa1", fontWeight: 400 }}>#{c.number}</span>
                  </div>
                  <div style={{ fontSize: 12, color: "#9fb7c0" }}>{gapLabel}</div>
                </div>
              );
            })}
          </div>
          <div style={{ fontSize: 11, color: "#6d8b96", marginTop: 10, lineHeight: 1.5 }}>
            Track layout: Circuit de Monaco (current GP configuration).
            {' '}Car positions from FastF1 historical telemetry.
          </div>
        </div>
      </div>
    </div>
  );
}
