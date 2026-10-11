export function isSnapshotStale(generatedAt, staleMinutes, now = Date.now()) {
  if (!generatedAt) return false;
  const ageMs = now - new Date(generatedAt).getTime();
  return ageMs > staleMinutes * 60 * 1000;
}

export function employeeSteps(run, employeeId) {
  return run && Array.isArray(run.steps) ? run.steps.filter((s) => s.employee === employeeId) : [];
}

// Worst status wins: one failed step means the employee failed this run.
const STATUS_ORDER = ["error", "running", "not_reached", "skipped", "done"];
export function employeeStatus(steps) {
  if (!steps || steps.length === 0) return "no_data";
  for (const status of STATUS_ORDER) {
    if (steps.some((s) => s.status === status)) return status;
  }
  return "no_data";
}

export const STATUS_LABELS = {
  done: "Finished",
  skipped: "Nothing to do",
  error: "Failed",
  not_reached: "Didn't start",
  running: "Working",
  no_data: "No run logged yet",
};

export const STATUS_COLORS = {
  done: "#34d399",
  skipped: "#9ca3af",
  error: "#ef4444",
  not_reached: "#4b5563",
  running: "#38bdf8",
  no_data: "#374151",
};

export function nextHourlyRun(now = new Date()) {
  const d = new Date(now);
  d.setUTCMinutes(5, 0, 0);
  if (d <= now) d.setUTCHours(d.getUTCHours() + 1);
  return d;
}

export function previousHourlySlot(now = new Date()) {
  const d = nextHourlyRun(now);
  d.setUTCHours(d.getUTCHours() - 1);
  return d;
}

export function previousDailySlot(now = new Date()) {
  const d = nextDailyRun(now);
  d.setUTCDate(d.getUTCDate() - 1);
  return d;
}

// GitHub's scheduler typically starts the job 10-20 minutes after the cron
// time. If the latest slot has passed with no run since, the run is "due",
// not "next in 50 min".
export function isRunDue(run, previousSlot) {
  if (!run) return true;
  return new Date(run.started_at) < previousSlot;
}

export function nextDailyRun(now = new Date()) {
  const d = new Date(now);
  d.setUTCHours(0, 15, 0, 0);
  if (d <= now) d.setUTCDate(d.getUTCDate() + 1);
  return d;
}

export function timeAgo(iso, now = Date.now()) {
  if (!iso) return "never";
  const secs = Math.round((now - new Date(iso).getTime()) / 1000);
  if (secs < 60) return "just now";
  const mins = Math.round(secs / 60);
  if (mins < 60) return `${mins} min ago`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} h ago`;
  return `${Math.round(hours / 24)} days ago`;
}

export function timeUntil(date, now = Date.now()) {
  const mins = Math.max(0, Math.round((new Date(date).getTime() - now) / 60000));
  if (mins < 1) return "any moment";
  if (mins < 60) return `in ${mins} min`;
  return `in ${Math.floor(mins / 60)} h ${mins % 60} min`;
}

export function formatTime(iso) {
  if (!iso) return "—";
  return new Date(iso).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

// An hourly run older than this means the schedule is late or stopped, say so.
export const HOURLY_LATE_MINUTES = 150;
export const DAILY_LATE_MINUTES = 26 * 60;

export function humanizeKey(key) {
  return key.replace(/_/g, " ").replace(/\bpct\b/, "%").replace(/\bma\b/, "MA");
}

export function formatValue(value) {
  if (value === null || value === undefined) return "Not available";
  if (Array.isArray(value)) return value.length ? value.join(" · ") : "none";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);
  return String(value);
}
