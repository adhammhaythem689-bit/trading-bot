import { BUILDINGS, EMPLOYEES, RUN_SCHEDULES, employeesIn } from "./employees";
import {
  STATUS_LABELS, STATUS_COLORS, employeeSteps, employeeStatus,
  formatTime, formatValue, humanizeKey, timeAgo,
} from "./utils";

const panelStyle = {
  position: "absolute", top: 64, right: 16, width: 360, maxHeight: "calc(100% - 80px)",
  overflowY: "auto", background: "#0f1420f2", border: "1px solid #1f2937", borderRadius: 10,
  padding: 16, color: "#e5e7eb", fontFamily: "system-ui, sans-serif",
  boxShadow: "0 8px 24px rgba(0,0,0,0.45)", zIndex: 15,
};

function StatusPill({ status }) {
  return (
    <span style={{
      background: STATUS_COLORS[status] || "#374151", color: "#0b0e14", padding: "2px 10px",
      borderRadius: 12, fontSize: 11, fontWeight: 700, textTransform: "uppercase",
    }}>
      {STATUS_LABELS[status] || status}
    </span>
  );
}

function Section({ title, children }) {
  return (
    <div style={{ marginTop: 14 }}>
      <div style={{ fontSize: 11, color: "#6b7280", textTransform: "uppercase", letterSpacing: 0.6, marginBottom: 6 }}>{title}</div>
      {children}
    </div>
  );
}

function Row({ label, value, color }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", gap: 12, padding: "4px 0", borderBottom: "1px solid #1a2130" }}>
      <span style={{ color: "#9ca3af", fontSize: 12 }}>{label}</span>
      <span style={{ color: color || "#e5e7eb", fontSize: 12, fontWeight: 500, textAlign: "right", wordBreak: "break-word" }}>{value}</span>
    </div>
  );
}

function Header({ title, subtitle, onClose }) {
  return (
    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
      <div>
        <div style={{ fontSize: 16, fontWeight: 700 }}>{title}</div>
        <div style={{ fontSize: 12, color: "#9ca3af" }}>{subtitle}</div>
      </div>
      <button aria-label="Close" onClick={onClose} style={{ background: "transparent", border: "none", color: "#9ca3af", fontSize: 18, cursor: "pointer" }}>×</button>
    </div>
  );
}

function StepOutputs({ step }) {
  const entries = Object.entries(step.outputs || {});
  return (
    <div style={{ background: "#0b0f19", border: "1px solid #1a2130", borderRadius: 6, padding: 10, marginBottom: 8 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600 }}>{step.description}</span>
        <StatusPill status={step.status} />
      </div>
      {step.started_at && <Row label="Started" value={formatTime(step.started_at)} />}
      {step.duration_ms !== null && step.duration_ms !== undefined && <Row label="Took" value={`${step.duration_ms} ms`} />}
      {step.error && <Row label="Error" value={step.error} color="#f87171" />}
      {step.status === "not_reached" && (
        <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 6 }}>
          This step never started because an earlier step in the same run failed.
        </div>
      )}
      {entries.map(([key, value]) =>
        Array.isArray(value) && value.length && String(value[0]).length > 30 ? (
          <div key={key} style={{ padding: "4px 0", borderBottom: "1px solid #1a2130" }}>
            <div style={{ color: "#9ca3af", fontSize: 12 }}>{humanizeKey(key)}</div>
            {value.map((item, i) => <div key={i} style={{ fontSize: 12, color: "#d1d5db", marginTop: 3 }}>· {item}</div>)}
          </div>
        ) : (
          <Row key={key} label={humanizeKey(key)} value={formatValue(value)} />
        ),
      )}
    </div>
  );
}

function BacktestDetails({ snapshot }) {
  const bt = snapshot?.departments?.backtesting;
  if (!bt || !bt.metrics) return <Row label="Status" value="No backtest exported yet" />;
  return (
    <div style={{ background: "#0b0f19", border: "1px solid #1a2130", borderRadius: 6, padding: 10 }}>
      <Row label="Strategy" value={`${bt.strategy_name} v${bt.strategy_version}`} />
      <Row label="Period" value={bt.period} />
      <Row label="Return" value={`${bt.metrics.return_pct}%`} />
      <Row label="Buy & hold, same period" value={`${bt.buy_and_hold_pct}%`} />
      <Row label="Beat buy & hold?" value={formatValue(bt.beat_buy_and_hold === true || bt.beat_buy_and_hold === "True")} />
      <Row label="Trades" value={bt.metrics.num_trades} />
      <Row label="Win rate" value={`${bt.metrics.win_rate}%`} />
      <Row label="Max drawdown" value={`${bt.metrics.max_drawdown_pct}%`} color="#f87171" />
      <Row label="Exported" value={`${formatTime(snapshot.generated_at)} (${timeAgo(snapshot.generated_at)})`} />
    </div>
  );
}

export function EmployeePanel({ employeeId, runs, snapshot, onClose }) {
  const employee = EMPLOYEES.find((e) => e.id === employeeId);
  if (!employee) return null;
  const building = BUILDINGS.find((b) => b.id === employee.building);
  const run = runs[employee.run];
  const steps = employeeSteps(run, employee.id);
  const status = employee.run === "manual"
    ? (snapshot?.departments?.backtesting?.metrics ? "done" : "no_data")
    : employeeStatus(steps);

  return (
    <div style={panelStyle} data-testid="employee-panel">
      <Header title={employee.title} subtitle={building.name} onClose={onClose} />
      <div style={{ marginTop: 10, display: "flex", gap: 8, alignItems: "center" }}>
        <StatusPill status={status} />
        {run && <span style={{ fontSize: 11, color: "#9ca3af" }}>last run {timeAgo(run.finished_at)}</span>}
      </div>

      <Section title="Job">
        <div style={{ fontSize: 13 }}>{employee.task || steps[0]?.description || "—"}</div>
        <div style={{ fontSize: 12, color: "#9ca3af", marginTop: 4 }}>{RUN_SCHEDULES[employee.run]}</div>
      </Section>

      <Section title={employee.run === "manual" ? "Latest result" : "What they did in the last run"}>
        {employee.run === "manual" ? (
          <BacktestDetails snapshot={snapshot} />
        ) : steps.length === 0 ? (
          <div style={{ fontSize: 12, color: "#9ca3af" }}>
            No run logged yet. The first {employee.run} run after this feature shipped will fill this in.
          </div>
        ) : (
          steps.map((s) => <StepOutputs key={s.step} step={s} />)
        )}
      </Section>

      {run && (
        <Section title="Run">
          <Row label="Run id" value={run.run_id} />
          <Row label="Triggered by" value={run.trigger === "schedule" ? "GitHub schedule" : run.trigger} />
          <Row label="Outcome" value={run.summary || run.status} />
        </Section>
      )}

      <Section title="Next">
        <div style={{ fontSize: 12, color: "#d1d5db" }}>{employee.next}</div>
      </Section>
    </div>
  );
}

export function BuildingPanel({ buildingId, statuses, onClose, onSelectEmployee, onEnter }) {
  const building = BUILDINGS.find((b) => b.id === buildingId);
  if (!building) return null;
  const staff = employeesIn(building.id);

  return (
    <div style={panelStyle} data-testid="building-panel">
      <Header title={building.name} subtitle={building.plannedOnly ? "Not implemented" : `${staff.length} employee${staff.length === 1 ? "" : "s"}`} onClose={onClose} />
      {building.plannedOnly ? (
        <div style={{ marginTop: 12, padding: 10, background: "#1f2937", borderRadius: 6, fontSize: 12, color: "#9ca3af" }}>
          {building.note}
        </div>
      ) : (
        <Section title="Staff">
          {staff.map((e) => (
            <button
              key={e.id}
              onClick={() => onSelectEmployee(e.id)}
              style={{
                display: "flex", justifyContent: "space-between", alignItems: "center", width: "100%",
                background: "#0b0f19", border: "1px solid #1a2130", borderRadius: 6, padding: "8px 10px",
                marginBottom: 6, color: "#e5e7eb", cursor: "pointer", fontSize: 13,
              }}
            >
              <span>{e.title}</span>
              <StatusPill status={statuses[e.id]} />
            </button>
          ))}
        </Section>
      )}
      <button
        onClick={() => onEnter(building.id)}
        style={{
          marginTop: 14, width: "100%", padding: "9px 0", background: building.color, color: "#0b0e14",
          border: "none", borderRadius: 6, fontWeight: 700, fontSize: 13, cursor: "pointer",
        }}
      >
        Go inside →
      </button>
    </div>
  );
}
