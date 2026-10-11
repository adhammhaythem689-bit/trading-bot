import { describe, it, expect } from "vitest";
import { BUILDINGS, EMPLOYEES, employeesIn } from "./employees";
import hourlyRun from "./__fixtures__/latest_hourly.json";
import dailyRun from "./__fixtures__/latest_daily.json";

describe("employee registry", () => {
  it("ids are unique", () => {
    const ids = EMPLOYEES.map((e) => e.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("every employee works in a building that exists and is implemented", () => {
    for (const e of EMPLOYEES) {
      const b = BUILDINGS.find((x) => x.id === e.building);
      expect(b, e.id).toBeTruthy();
      expect(b.plannedOnly, e.id).toBeFalsy();
    }
  });

  it("not-implemented buildings have nobody in them", () => {
    for (const b of BUILDINGS.filter((x) => x.plannedOnly)) {
      expect(employeesIn(b.id)).toHaveLength(0);
      expect(b.note).toBeTruthy();
    }
  });
});

// The fixtures are real run logs written by engine/runlog.py. If someone
// renames or adds a step in Python without updating the city, these fail.
describe("registry matches the real run logs", () => {
  for (const [name, run, type] of [["hourly", hourlyRun, "hourly"], ["daily", dailyRun, "daily"]]) {
    it(`every ${name} step's employee exists with run type ${type}`, () => {
      for (const step of run.steps) {
        const e = EMPLOYEES.find((x) => x.id === step.employee);
        expect(e, step.employee).toBeTruthy();
        expect(e.run).toBe(type);
      }
    });

    it(`every ${name} employee appears in the ${name} log`, () => {
      const inLog = new Set(run.steps.map((s) => s.employee));
      for (const e of EMPLOYEES.filter((x) => x.run === type)) {
        expect(inLog.has(e.id), e.id).toBe(true);
      }
    });
  }
});
