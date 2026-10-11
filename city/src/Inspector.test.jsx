import { describe, it, expect } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import Inspector from "./Inspector";

describe("Inspector", () => {
  it("renders nothing when no department is selected", () => {
    const { container } = render(<Inspector selectedId={null} cityData={null} onClose={() => {}} />);
    expect(container.firstChild).toBeNull();
  });

  it("shows an idle/'no job' state for a department with no data, instead of inventing activity", () => {
    render(<Inspector selectedId="backtesting" cityData={{ departments: {} }} onClose={() => {}} />);
    expect(screen.getByText(/No backtest run yet/i)).toBeInTheDocument();
  });

  it("renders real backtest metrics when provided, not placeholder values", () => {
    const cityData = {
      departments: {
        backtesting: {
          status: "complete", strategy_name: "ma_crossover", strategy_version: "1.1",
          params: { short_window: 24, long_window: 72 },
          period: "2024-01-01 to 2026-01-01",
          metrics: { return_pct: 11.46, num_trades: 32, win_rate: 34.4, max_drawdown_pct: -21.7, profit_factor: 1.7 },
          buy_and_hold_pct: 27.94, beat_buy_and_hold: false, equity_sparkline: [1000, 1050, 1100],
        },
      },
    };
    render(<Inspector selectedId="backtesting" cityData={cityData} onClose={() => {}} />);
    expect(screen.getByText("11.46%")).toBeInTheDocument();
    expect(screen.getByText("32")).toBeInTheDocument();
    expect(screen.getByText("27.94%")).toBeInTheDocument();
  });

  it("marks a not-yet-implemented department honestly instead of fabricating a status", () => {
    const cityData = { departments: { machine_learning: { status: "not_implemented", note: "No ML models trained yet." } } };
    render(<Inspector selectedId="machine_learning" cityData={cityData} onClose={() => {}} />);
    expect(screen.getByText(/not_implemented/i)).toBeInTheDocument();
    expect(screen.getByText(/No ML models trained yet/i)).toBeInTheDocument();
  });

  it("offers an enter-workstation action that reports the selected department", () => {
    let entered = null;
    const cityData = { departments: { backtesting: { status: "complete" } } };
    render(<Inspector selectedId="backtesting" cityData={cityData} onClose={() => {}} onEnterRoom={(id) => { entered = id; }} />);
    fireEvent.click(screen.getByText(/Enter workstation/i));
    expect(entered).toBe("backtesting");
  });

  it("calls onClose when the close button is clicked", () => {
    let closed = false;
    const cityData = { departments: { operations: { status: "running" } } };
    render(<Inspector selectedId="operations" cityData={cityData} onClose={() => { closed = true; }} />);
    fireEvent.click(screen.getByText("×"));
    expect(closed).toBe(true);
  });

  it("shows an explicit low-confidence caveat on validation results, not a bare pass/fail", () => {
    const cityData = {
      departments: {
        validation: {
          status: "inconclusive", method: "Chronological 75/25 split",
          best_training_combo: "short=24, long=72", training_return_pct: 19.1,
          caveat: "Single train/test split only; walk-forward testing not yet implemented.",
        },
      },
    };
    render(<Inspector selectedId="validation" cityData={cityData} onClose={() => {}} />);
    expect(screen.getByText(/walk-forward testing not yet implemented/i)).toBeInTheDocument();
  });
});
