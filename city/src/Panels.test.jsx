import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { EmployeePanel, BuildingPanel } from "./Panels";
import hourlyRun from "./__fixtures__/latest_hourly.json";

describe("EmployeePanel", () => {
  it("shows the employee's real outputs from the run log", () => {
    render(<EmployeePanel employeeId="price_fetcher" runs={{ hourly: hourlyRun, daily: null }} snapshot={null} onClose={() => {}} />);
    const step = hourlyRun.steps.find((s) => s.step === "fetch_prices");
    expect(screen.getByText(String(step.outputs.candles))).toBeInTheDocument();
    expect(screen.getByText(step.outputs.source)).toBeInTheDocument();
    expect(screen.getByText(hourlyRun.run_id)).toBeInTheDocument();
  });

  it("says there's no run logged instead of inventing work", () => {
    render(<EmployeePanel employeeId="trader" runs={{ hourly: null, daily: null }} snapshot={null} onClose={() => {}} />);
    expect(screen.getAllByText(/No run logged yet/i).length).toBeGreaterThan(0);
  });

  it("shows the actual error for a failed step and explains steps that never started", () => {
    const failed = structuredClone(hourlyRun);
    for (const s of failed.steps) {
      if (s.step === "fetch_prices") { s.status = "error"; s.error = "ExchangeNotAvailable: kraken 503"; s.outputs = {}; }
      else { s.status = "not_reached"; s.outputs = {}; }
    }
    failed.status = "error";

    const { unmount } = render(<EmployeePanel employeeId="price_fetcher" runs={{ hourly: failed }} snapshot={null} onClose={() => {}} />);
    expect(screen.getByText(/kraken 503/)).toBeInTheDocument();
    unmount();

    render(<EmployeePanel employeeId="trader" runs={{ hourly: failed }} snapshot={null} onClose={() => {}} />);
    expect(screen.getByText(/never started because an earlier step/i)).toBeInTheDocument();
  });

  it("shows the backtest analyst's exported results with the export time", () => {
    const snapshot = {
      generated_at: "2026-10-11T15:32:47Z",
      departments: { backtesting: {
        strategy_name: "ma_crossover", strategy_version: "1.1", period: "p",
        metrics: { return_pct: 11.46, num_trades: 32, win_rate: 34.4, max_drawdown_pct: -21.7 },
        buy_and_hold_pct: 27.94, beat_buy_and_hold: false,
      } },
    };
    render(<EmployeePanel employeeId="backtest_analyst" runs={{}} snapshot={snapshot} onClose={() => {}} />);
    expect(screen.getByText("11.46%")).toBeInTheDocument();
    expect(screen.getByText("27.94%")).toBeInTheDocument();
    expect(screen.getByText(/Not scheduled/i)).toBeInTheDocument();
  });
});

describe("BuildingPanel", () => {
  it("lists staff and lets you open one", () => {
    let picked = null;
    render(<BuildingPanel buildingId="news" statuses={{ news_reader: "done", mood_analyst: "done" }}
      onClose={() => {}} onSelectEmployee={(id) => { picked = id; }} onEnter={() => {}} />);
    fireEvent.click(screen.getByText("Mood Analyst"));
    expect(picked).toBe("mood_analyst");
  });

  it("explains why an unimplemented building is empty", () => {
    render(<BuildingPanel buildingId="ml_lab" statuses={{}} onClose={() => {}} onSelectEmployee={() => {}} onEnter={() => {}} />);
    expect(screen.getByText(/No machine-learning model has been trained/i)).toBeInTheDocument();
  });
});
