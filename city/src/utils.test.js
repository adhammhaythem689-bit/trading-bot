import { describe, it, expect } from "vitest";
import {
  isSnapshotStale, employeeStatus, employeeSteps, nextHourlyRun, nextDailyRun, timeAgo, formatValue,
  previousHourlySlot, isRunDue,
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
  it("next hourly run is the next :05 UTC", () => {
    expect(nextHourlyRun(new Date("2026-01-01T12:03:00Z")).toISOString()).toBe("2026-01-01T12:05:00.000Z");
    expect(nextHourlyRun(new Date("2026-01-01T12:05:00Z")).toISOString()).toBe("2026-01-01T13:05:00.000Z");
    expect(nextHourlyRun(new Date("2026-01-01T23:30:00Z")).toISOString()).toBe("2026-01-02T00:05:00.000Z");
  });
  it("next daily run is the next 00:15 UTC", () => {
    expect(nextDailyRun(new Date("2026-01-01T00:10:00Z")).toISOString()).toBe("2026-01-01T00:15:00.000Z");
    expect(nextDailyRun(new Date("2026-01-01T09:00:00Z")).toISOString()).toBe("2026-01-02T00:15:00.000Z");
  });
  it("a run is due when its slot passed without one, not 'next in 50 min'", () => {
    const now = new Date("2026-01-01T12:18:00Z");
    const slot = previousHourlySlot(now);
    expect(slot.toISOString()).toBe("2026-01-01T12:05:00.000Z");
    expect(isRunDue({ started_at: "2026-01-01T11:17:00Z" }, slot)).toBe(true);
    expect(isRunDue({ started_at: "2026-01-01T12:16:00Z" }, slot)).toBe(false);
    expect(isRunDue(null, slot)).toBe(true);
  });

  it("timeAgo reads naturally", () => {
    const now = new Date("2026-01-01T12:00:00Z").getTime();
    expect(timeAgo("2026-01-01T11:59:40Z", now)).toBe("just now");
    expect(timeAgo("2026-01-01T11:48:00Z", now)).toBe("12 min ago");
    expect(timeAgo("2026-01-01T09:00:00Z", now)).toBe("3 h ago");
    expect(timeAgo(null, now)).toBe("never");
  });
});

describe("formatValue", () => {
  it("never shows a blank for missing values", () => {
    expect(formatValue(null)).toBe("Not available");
    expect(formatValue([])).toBe("none");
    expect(formatValue(true)).toBe("yes");
  });
});
