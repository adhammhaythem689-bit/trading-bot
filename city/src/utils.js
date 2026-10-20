export function isSnapshotStale(generatedAt, staleMinutes, now = Date.now()) {
  if (!generatedAt) return false;
  const ageMs = now - new Date(generatedAt).getTime();
  return ageMs > staleMinutes * 60 * 1000;
}

export function employeeSteps(run, employeeId) {
  return run && Array.isArray(run.steps) ? run.steps.filter((s) => s.employee === employeeId) : [];
}

// Worst status wins: one failed step means the employee failed this run.
const STATUS_ORDER = ["error", "running", "not_reached", "warning", "skipped", "done"];
export function employeeStatus(steps) {
  if (!steps || steps.length === 0) return "no_data";
  for (const status of STATUS_ORDER) {
    if (steps.some((s) => s.status === status)) return status;
  }
  return "no_data";
}

export const STATUS_LABELS = {
  done: "Finished",
  warning: "Finished, with a warning",
  skipped: "Nothing to do",
  error: "Failed",
  not_reached: "Didn't start",
  running: "Working",
  no_data: "No run logged yet",
};

export const STATUS_COLORS = {
  done: "#34d399",
  warning: "#fbbf24",
  skipped: "#9ca3af",
  error: "#ef4444",
  not_reached: "#4b5563",
  running: "#38bdf8",
  no_data: "#374151",
};

// The workflow checks at :07, :22, :37 and :52; a new candle (and so a new
// run log) appears at the first check after each hour, :07.
export const HOURLY_CRON_MINUTE = 7;

export function nextHourlyRun(now = new Date()) {
  const d = new Date(now);
  d.setUTCMinutes(HOURLY_CRON_MINUTE, 0, 0);
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
// Only within a grace window, though: a slot from hours ago that never
// produced a log isn't "about to run", the next slot is what's coming.
export function isRunDue(run, previousSlot, now = Date.now(), graceMinutes = 45) {
  if (now - previousSlot.getTime() > graceMinutes * 60 * 1000) return false;
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

// run.trigger comes straight from GITHUB_EVENT_NAME (see engine/runlog.py).
// GitHub's own cron drops most slots; "External pinger" is the one that's
// actually reliable, so it's worth telling apart from a manual debug click.
export const TRIGGER_LABELS = {
  schedule: "GitHub schedule",
  repository_dispatch: "External pinger (repository_dispatch)",
  workflow_dispatch: "Triggered manually",
  local: "Run locally, not on GitHub",
};

export function triggerLabel(trigger) {
  return TRIGGER_LABELS[trigger] || trigger || "unknown";
}

export function humanizeKey(key) {
  return key.replace(/_/g, " ").replace(/\bpct\b/, "%").replace(/\bma\b/, "MA");
}

export function formatValue(value) {
  if (value === null || value === undefined) return "Not available";
  if (Array.isArray(value)) return value.length ? value.join(" · ") : "none";
  if (typeof value === "boolean") return value ? "yes" : "no";
  if (typeof value === "object") {
    return Object.entries(value).map(([k, v]) => `${humanizeKey(k).trim()} ${formatValue(v)}`).join(", ") || "none";
  }
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : String(Math.round(value * 1000) / 1000);
  return String(value);
}
