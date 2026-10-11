import { useEffect, useMemo, useState } from "react";
import { Canvas } from "@react-three/fiber";
import CityScene from "./CityScene";
import RoomView from "./RoomView";
import { EmployeePanel, BuildingPanel } from "./Panels";
import { EMPLOYEES } from "./employees";
import { useLiveData, IS_GITHUB_SOURCE, DATA_BASE } from "./liveData";
import {
  employeeSteps, employeeStatus, nextHourlyRun, nextDailyRun, timeAgo, timeUntil, formatTime,
  STATUS_COLORS, HOURLY_LATE_MINUTES, DAILY_LATE_MINUTES, isSnapshotStale,
} from "./utils";

const REPLAY_STEP_MS = 1800;

function useNow(intervalMs = 15000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return now;
}

function Chip({ children, bg = "#111827", color = "#d1d5db", title }) {
  return (
    <div title={title} style={{ background: bg, color, padding: "5px 11px", borderRadius: 999, fontSize: 12, whiteSpace: "nowrap" }}>
      {children}
    </div>
  );
}

function RunChip({ label, run, now, nextAt, lateMinutes }) {
  if (!run) return <Chip>{label}: no run logged yet · next {timeUntil(nextAt, now)}</Chip>;
  const late = isSnapshotStale(run.finished_at, lateMinutes, now);
  const color = STATUS_COLORS[run.status] || "#9ca3af";
  return (
    <Chip title={run.summary || ""} bg={late ? "#78350f" : "#111827"}>
      <span style={{ color }}>●</span> {label}: {run.status} {timeAgo(run.finished_at, now)}
      {late ? " · LATE, schedule may be stuck" : ` · next ${timeUntil(nextAt, now)}`}
    </Chip>
  );
}

export default function App() {
  const live = useLiveData();
  const now = useNow();
  const [selection, setSelection] = useState(null);
  const [roomId, setRoomId] = useState(null);
  const [replay, setReplay] = useState(null); // { runType, index }

  const runs = useMemo(() => ({ hourly: live.hourly, daily: live.daily }), [live.hourly, live.daily]);

  const statuses = useMemo(() => {
    const out = {};
    for (const e of EMPLOYEES) {
      out[e.id] = e.run === "manual"
        ? (live.snapshot?.departments?.backtesting?.metrics ? "done" : "no_data")
        : employeeStatus(employeeSteps(runs[e.run], e.id));
    }
    return out;
  }, [runs, live.snapshot]);

  const replaySteps = replay ? runs[replay.runType]?.steps || [] : [];
  // a replay that has stepped past the last step is simply over
  const replayActive = Boolean(replay) && replay.index < replaySteps.length;
  const replayStep = replayActive ? replaySteps[replay.index] : null;
  const previousReplayStep = replayActive && replay.index > 0 ? replaySteps[replay.index - 1] : null;

  useEffect(() => {
    if (!replayActive) return;
    const t = setTimeout(() => setReplay((r) => r && { ...r, index: r.index + 1 }), REPLAY_STEP_MS);
    return () => clearTimeout(t);
  }, [replayActive, replay]);

  const startReplay = (runType) => {
    setRoomId(null);
    setReplay({ runType, index: 0 });
  };

  const replayRun = replay ? runs[replay.runType] : null;
  const replayEmployee = replayStep ? EMPLOYEES.find((e) => e.id === replayStep.employee) : null;

  return (
    <div style={{ position: "relative", width: "100vw", height: "100vh", background: "#060810", fontFamily: "system-ui, sans-serif" }}>
      <div style={{ position: "absolute", top: 12, left: 12, right: 12, zIndex: 16, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
        <Chip bg={IS_GITHUB_SOURCE ? "#064e3b" : "#7c2d12"} color="#fff">
          <b>{IS_GITHUB_SOURCE ? "LIVE FROM GITHUB" : "LOCAL TEST DATA"}</b>
        </Chip>
        <RunChip label="Hourly run" run={live.hourly} now={now} nextAt={nextHourlyRun(new Date(now))} lateMinutes={HOURLY_LATE_MINUTES} />
        <RunChip label="Daily run" run={live.daily} now={now} nextAt={nextDailyRun(new Date(now))} lateMinutes={DAILY_LATE_MINUTES} />
        <Chip title="GitHub can cache files for up to 5 minutes">
          {live.loading ? "Loading…" : `Checked ${IS_GITHUB_SOURCE ? "GitHub" : "local data"} ${timeAgo(live.fetchedAt, now)}`}
        </Chip>
        {live.error && <Chip bg="#7f1d1d" color="#fecaca">Couldn't reach GitHub: {live.error} · showing last known data</Chip>}
        <div style={{ flex: 1 }} />
        <button onClick={() => startReplay("hourly")} disabled={!live.hourly}
          style={btnStyle(!live.hourly)}>▶ Replay last hourly run</button>
        <button onClick={() => startReplay("daily")} disabled={!live.daily}
          style={btnStyle(!live.daily)}>▶ Replay last daily run</button>
      </div>

      {replay && replayStep && (
        <div style={{
          position: "absolute", bottom: 16, left: "50%", transform: "translateX(-50%)", zIndex: 16,
          width: "min(560px, calc(100% - 32px))",
          background: "#0f1420f2", border: "1px solid #374151", borderRadius: 10, padding: "10px 16px",
          color: "#e5e7eb", fontSize: 13, textAlign: "center", boxSizing: "border-box",
        }}>
          <div style={{ fontSize: 11, color: "#fbbf24", fontWeight: 700, letterSpacing: 0.6 }}>
            REPLAY of the {formatTime(replayRun.started_at)} run · step {replay.index + 1}/{replaySteps.length}
          </div>
          <div style={{ marginTop: 4 }}>
            <b>{replayEmployee?.title}</b>: {replayStep.description}{" "}
            <span style={{ color: STATUS_COLORS[replayStep.status] }}>({replayStep.status}{replayStep.duration_ms != null ? `, ${replayStep.duration_ms} ms` : ""})</span>
          </div>
          <button onClick={() => setReplay(null)} style={{ ...btnStyle(false), marginTop: 6, fontSize: 11 }}>Stop replay</button>
        </div>
      )}

      <div style={{ position: "absolute", bottom: 12, left: 12, zIndex: 16, color: "#6b7280", fontSize: 11, maxWidth: 520,
        display: replayActive ? "none" : "block" }}>
        Every employee is one real step of the scheduled runs on GitHub. Between runs, which is most of the hour,
        they're waiting and show their latest result. Click someone to see exactly what they did.
        {!IS_GITHUB_SOURCE && ` Data source: ${DATA_BASE}`}
      </div>

      <Canvas shadows camera={{ position: [0, 11, 15], fov: 45 }}>
        <CityScene
          statuses={statuses}
          selection={selection}
          onSelect={setSelection}
          replayStep={replayStep}
          previousReplayStep={previousReplayStep}
        />
      </Canvas>

      {selection?.type === "employee" && (
        <EmployeePanel employeeId={selection.id} runs={runs} snapshot={live.snapshot} onClose={() => setSelection(null)} />
      )}
      {selection?.type === "building" && (
        <BuildingPanel
          buildingId={selection.id}
          statuses={statuses}
          onClose={() => setSelection(null)}
          onSelectEmployee={(id) => setSelection({ type: "employee", id })}
          onEnter={(id) => { setReplay(null); setRoomId(id); }}
        />
      )}

      {roomId && (
        <RoomView buildingId={roomId} runs={runs} snapshot={live.snapshot} statuses={statuses} onBack={() => setRoomId(null)} />
      )}
    </div>
  );
}

function btnStyle(disabled) {
  return {
    background: disabled ? "#1f2937" : "#2563eb", color: disabled ? "#6b7280" : "#fff", border: "none",
    borderRadius: 8, padding: "6px 12px", fontSize: 12, fontWeight: 600, cursor: disabled ? "default" : "pointer",
  };
}
