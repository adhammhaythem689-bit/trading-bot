import { describe, it, expect } from "vitest";
import {
  isSnapshotStale, employeeStatus, employeeSteps, nextHourlyRun, nextDailyRun, timeAgo, formatValue,
  previousHourlySlot, isRunDue, triggerLabel,
} from "./utils";

describe("isSnapshotStale", () => {
  const now = new Date("2026-01-01T12:00:00Z").getTime();
  it("flags only data older than the threshold", () => {
    expect(isSnapshotStale("2026-01-01T11:50:00Z", 90, now)).toBe(false);
    expect(isSnapshotStale("2026-01-01T10:00:00Z", 90, now)).toBe(true);
  });
  it("returns false for a missing timestamp instead of throwing", () => {
    expect(isSnapshotStale(null, 90, now)).toBe(false);
  });
});

describe("employeeStatus", () => {
  it("is no_data when the employee has no logged steps", () => {
    expect(employeeStatus([])).toBe("no_data");
  });
  it("reports failure if any of their steps failed", () => {
    expect(employeeStatus([{ status: "done" }, { status: "error" }])).toBe("error");
  });
  it("reports done only when every step finished", () => {
    expect(employeeStatus([{ status: "done" }, { status: "done" }])).toBe("done");
  });
  it("a warning outranks done but not a failure", () => {
    expect(employeeStatus([{ status: "warning" }, { status: "done" }])).toBe("warning");
    expect(employeeStatus([{ status: "warning" }, { status: "error" }])).toBe("error");
  });

  it("reports skipped and not_reached honestly", () => {
    expect(employeeStatus([{ status: "skipped" }])).toBe("skipped");
    expect(employeeStatus([{ status: "not_reached" }])).toBe("not_reached");
  });
});

describe("employeeSteps", () => {
  it("returns an empty list when there is no run log", () => {
    expect(employeeSteps(null, "trader")).toEqual([]);
  });
  it("returns only that employee's steps", () => {
    const run = { steps: [{ employee: "a", step: "x" }, { employee: "b", step: "y" }, { employee: "a", step: "z" }] };
    expect(employeeSteps(run, "a").map((s) => s.step)).toEqual(["x", "z"]);
  });
});

describe("schedule helpers", () => {
  it("next hourly run is the next :07 UTC", () => {
    expect(nextHourlyRun(new Date("2026-01-01T12:03:00Z")).toISOString()).toBe("2026-01-01T12:07:00.000Z");
    expect(nextHourlyRun(new Date("2026-01-01T12:07:00Z")).toISOString()).toBe("2026-01-01T13:07:00.000Z");
    expect(nextHourlyRun(new Date("2026-01-01T23:30:00Z")).toISOString()).toBe("2026-01-02T00:07:00.000Z");
  });
  it("next daily run is the next 00:15 UTC", () => {
    expect(nextDailyRun(new Date("2026-01-01T00:10:00Z")).toISOString()).toBe("2026-01-01T00:15:00.000Z");
    expect(nextDailyRun(new Date("2026-01-01T09:00:00Z")).toISOString()).toBe("2026-01-02T00:15:00.000Z");
  });
  it("a run is due when its slot passed without one, not 'next in 50 min'", () => {
    const now = new Date("2026-01-01T12:18:00Z");
    const slot = previousHourlySlot(now);
    expect(slot.toISOString()).toBe("2026-01-01T12:07:00.000Z");
    const t = now.getTime();
    expect(isRunDue({ started_at: "2026-01-01T11:17:00Z" }, slot, t)).toBe(true);
    expect(isRunDue({ started_at: "2026-01-01T12:16:00Z" }, slot, t)).toBe(false);
    expect(isRunDue(null, slot, t)).toBe(true);
  });

  it("a slot from hours ago is not 'due', the next slot is", () => {
    const slot = new Date("2026-01-01T00:15:00Z");
    const later = new Date("2026-01-01T16:00:00Z").getTime();
    expect(isRunDue(null, slot, later)).toBe(false);
  });

  it("timeAgo reads naturally", () => {
    const now = new Date("2026-01-01T12:00:00Z").getTime();
    expect(timeAgo("2026-01-01T11:59:40Z", now)).toBe("just now");
    expect(timeAgo("2026-01-01T11:48:00Z", now)).toBe("12 min ago");
    expect(timeAgo("2026-01-01T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo(null, now)).toBe("never");
  });
});

describe("triggerLabel", () => {
  it("tells apart the reliable external pinger from GitHub's flaky schedule", () => {
    expect(triggerLabel("repository_dispatch")).toMatch(/external pinger/i);
    expect(triggerLabel("schedule")).toMatch(/github schedule/i);
    expect(triggerLabel("workflow_dispatch")).toMatch(/manually/i);
  });
  it("falls back to the raw value for anything unrecognized, never blank", () => {
    expect(triggerLabel("something_new")).toBe("something_new");
    expect(triggerLabel(undefined)).toBe("unknown");
  });
});

describe("formatValue", () => {
  it("never shows a blank for missing values", () => {
    expect(formatValue(null)).toBe("Not available");
    expect(formatValue([])).toBe("none");
    expect(formatValue(true)).toBe("yes");
    expect(formatValue({ short: 48, long: 168 })).toBe("short 48, long 168");
  });
});
