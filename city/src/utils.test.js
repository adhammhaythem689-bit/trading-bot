import { describe, it, expect } from "vitest";
import { isSnapshotStale } from "./utils";

describe("isSnapshotStale", () => {
  const now = new Date("2026-01-01T12:00:00Z").getTime();

  it("is not stale when well within the threshold", () => {
    const generated = new Date("2026-01-01T11:50:00Z").toISOString(); // 10 min old
    expect(isSnapshotStale(generated, 90, now)).toBe(false);
  });

  it("is stale when older than the threshold", () => {
    const generated = new Date("2026-01-01T10:00:00Z").toISOString(); // 120 min old
    expect(isSnapshotStale(generated, 90, now)).toBe(true);
  });

  it("is exactly at the boundary is not stale (strictly greater-than)", () => {
    const generated = new Date("2026-01-01T10:30:00Z").toISOString(); // exactly 90 min old
    expect(isSnapshotStale(generated, 90, now)).toBe(false);
  });

  it("returns false for missing timestamp rather than throwing", () => {
    expect(isSnapshotStale(null, 90, now)).toBe(false);
    expect(isSnapshotStale(undefined, 90, now)).toBe(false);
  });
});
