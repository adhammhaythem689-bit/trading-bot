import { describe, it, expect } from "vitest";
import { DEPARTMENTS } from "./departments";
import { SCREEN_DRAWERS, drawNotImplementedScreen } from "./screenTextures";

describe("DEPARTMENTS registry", () => {
  it("every department has a unique id", () => {
    const ids = DEPARTMENTS.map((d) => d.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every department has a position, color, name, and role", () => {
    for (const dept of DEPARTMENTS) {
      expect(dept.position).toHaveLength(3);
      expect(dept.color).toMatch(/^#/);
      expect(dept.name).toBeTruthy();
      expect(dept.role).toBeTruthy();
    }
  });

  it("departments with no real backend implementation are flagged plannedOnly", () => {
    const notBuiltYet = ["strategy_discovery", "machine_learning"];
    for (const id of notBuiltYet) {
      const dept = DEPARTMENTS.find((d) => d.id === id);
      expect(dept.plannedOnly).toBe(true);
    }
  });

  it("every department has a workstation monitor drawer", () => {
    for (const dept of DEPARTMENTS) {
      expect(typeof SCREEN_DRAWERS[dept.id]).toBe("function");
    }
  });

  it("unimplemented departments use the NOT IMPLEMENTED monitor, never a fake chart", () => {
    expect(SCREEN_DRAWERS.strategy_discovery).toBe(drawNotImplementedScreen);
    expect(SCREEN_DRAWERS.machine_learning).toBe(drawNotImplementedScreen);
  });

  it("implemented departments are not marked plannedOnly", () => {
    const implemented = ["data_collection", "backtesting", "validation", "operations", "self_learning"];
    for (const id of implemented) {
      const dept = DEPARTMENTS.find((d) => d.id === id);
      expect(dept.plannedOnly).toBeUndefined();
    }
  });
});
