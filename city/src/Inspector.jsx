import { DEPARTMENTS } from "./departments";

function Sparkline({ values }) {
  if (!values || values.length < 2) return null;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = max - min || 1;
  const w = 280, h = 60;
  const points = values
    .map((v, i) => `${(i / (values.length - 1)) * w},${h - ((v - min) / range) * h}`)
    .join(" ");
  return (
    <svg width={w} height={h} style={{ display: "block", marginTop: 8 }}>
      <polyline points={points} fill="none" stroke="#34d399" strokeWidth="2" />
    </svg>
  );
}

function StatusPill({ status }) {
  const colors = {
    running: "#34d399", complete: "#34d399", halted: "#ef4444",
    idle: "#6b7280", not_implemented: "#6b7280", inconclusive: "#fbbf24",
  };
  return (
    <span style={{
      background: colors[status] || "#6b7280", color: "#0b0e14", padding: "2px 10px",
      borderRadius: 12, fontSize: 12, fontWeight: 600, textTransform: "uppercase",
    }}>
      {status || "unknown"}
    </span>
  );
}

function Row({ label, value }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", padding: "4px 0", borderBottom: "1px solid #1f2937" }}>
      <span style={{ color: "#9ca3af", fontSize: 13 }}>{label}</span>
      <span style={{ color: "#e5e7eb", fontSize: 13, fontWeight: 500 }}>{String(value)}</span>
    </div>
  );
}

function DataPanel({ data }) {
  return (
    <>
      <Row label="Source" value={data.source || "Not available"} />
      <Row label="Candle count" value={data.candle_count ?? "Not available"} />
      <Row label="Earliest candle" value={data.earliest_candle} />
      <Row label="Latest candle" value={data.latest_candle} />
      {data.warnings && data.warnings.length > 0 && (
        <div style={{ marginTop: 8, color: "#fbbf24", fontSize: 12 }}>
          {data.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
        </div>
      )}
    </>
  );
}

function BacktestPanel({ data }) {
  if (!data.metrics) return <Row label="Status" value="No backtest run yet" />;
  return (
    <>
      <Row label="Strategy" value={`${data.strategy_name} v${data.strategy_version}`} />
      <Row label="Parameters" value={`short=${data.params.short_window}h long=${data.params.long_window}h`} />
      <Row label="Period" value={data.period} />
      <Row label="Return" value={`${data.metrics.return_pct}%`} />
      <Row label="Trades" value={data.metrics.num_trades} />
      <Row label="Win rate" value={`${data.metrics.win_rate}%`} />
      <Row label="Max drawdown" value={`${data.metrics.max_drawdown_pct}%`} />
      <Row label="Profit factor" value={data.metrics.profit_factor} />
      <Row label="Buy & hold" value={`${data.buy_and_hold_pct}%`} />
      <Row label="Beat buy & hold?" value={data.beat_buy_and_hold} />
      <div style={{ color: "#9ca3af", fontSize: 12, marginTop: 8 }}>Equity curve (sampled)</div>
      <Sparkline values={data.equity_sparkline} />
    </>
  );
}

function ValidationPanel({ data }) {
  if (!data.method) return <Row label="Status" value="No validation run yet" />;
  return (
    <>
      <Row label="Method" value={data.method} />
      <Row label="Best training combo" value={data.best_training_combo} />
      <Row label="Training return" value={`${data.training_return_pct}%`} />
      <div style={{ marginTop: 10, padding: 8, background: "#1f2937", borderRadius: 6, fontSize: 12, color: "#fbbf24" }}>
        ⚠ {data.caveat}
      </div>
    </>
  );
}

function OperationsPanel({ data }) {
  if (data.cash === undefined) return <Row label="Status" value="No live state yet" />;
  return (
    <>
      <Row label="Cash" value={`$${data.cash}`} />
      <Row label="BTC held" value={data.btc} />
      <Row label="In position?" value={data.in_position} />
      <Row label="Trading halted?" value={data.trading_halted} />
      <Row label="Last candle checked" value={data.last_candle_ts} />
      {data.recent_log && data.recent_log.length > 0 && (
        <>
          <div style={{ color: "#9ca3af", fontSize: 12, marginTop: 10 }}>Recent ticks</div>
          <div style={{ maxHeight: 140, overflowY: "auto", marginTop: 4 }}>
            {data.recent_log.map((row, i) => (
              <div key={i} style={{ fontSize: 11, color: "#d1d5db", padding: "2px 0", borderBottom: "1px solid #1f2937" }}>
                {row.timestamp} — {row.note}
              </div>
            ))}
          </div>
        </>
      )}
    </>
  );
}

function SelfLearningPanel({ data }) {
  if (data.total_combos === undefined) return <Row label="Status" value="No analysis run yet" />;
  return (
    <>
      <Row label="Total trades analyzed" value={data.total_trades} />
      <Row label="Reliable patterns" value={`${data.reliable_combos} / ${data.total_combos}`} />
      <Row label="Filter helped last test?" value={data.filter_helped_last_run} />
      <div style={{ marginTop: 10, padding: 8, background: "#1f2937", borderRadius: 6, fontSize: 12, color: "#9ca3af" }}>
        A pattern only counts as "reliable" once it has 30+ historical trades. Most patterns
        don't have enough data yet, this grows as the paper trader keeps running.
      </div>
    </>
  );
}

function NotImplementedPanel({ data }) {
  return (
    <div style={{ padding: 12, background: "#1f2937", borderRadius: 6, color: "#9ca3af", fontSize: 13 }}>
      {data.note || "This department has no real implementation yet."}
    </div>
  );
}

const PANELS = {
  data_collection: DataPanel,
  backtesting: BacktestPanel,
  validation: ValidationPanel,
  operations: OperationsPanel,
  self_learning: SelfLearningPanel,
  strategy_discovery: NotImplementedPanel,
  machine_learning: NotImplementedPanel,
};

export default function Inspector({ selectedId, cityData, onClose }) {
  if (!selectedId) return null;
  const dept = DEPARTMENTS.find((d) => d.id === selectedId);
  const data = (cityData && cityData.departments[selectedId]) || {};
  const Panel = PANELS[selectedId] || (() => <div>Unknown department</div>);

  return (
    <div style={{
      position: "absolute", top: 16, right: 16, width: 340, maxHeight: "calc(100% - 32px)",
      overflowY: "auto", background: "#0f1420ee", border: "1px solid #1f2937", borderRadius: 10,
      padding: 16, color: "#e5e7eb", fontFamily: "system-ui, sans-serif", boxShadow: "0 8px 24px rgba(0,0,0,0.4)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
        <div>
          <div style={{ fontSize: 16, fontWeight: 700 }}>{dept.name}</div>
          <div style={{ fontSize: 12, color: "#9ca3af" }}>{dept.role}</div>
        </div>
        <button onClick={onClose} style={{
          background: "transparent", border: "none", color: "#9ca3af", fontSize: 18, cursor: "pointer",
        }}>×</button>
      </div>
      <div style={{ marginTop: 10, marginBottom: 10 }}>
        <StatusPill status={data.status} />
      </div>
      <Panel data={data} />
    </div>
  );
}
