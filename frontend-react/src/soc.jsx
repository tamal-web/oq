export default function SOCPage({ onNavigate }) {
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
          <button
            onClick={() => onNavigate("main")}
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
            ← Back
          </button>

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
            ← Back to selector
          </button>
        </div>
      </div>
    </div>
  );
}
