// Who works where. Every scheduled employee id matches the `employee` field
// written by engine/runlog.py in 06_paper_trade.py (hourly) and
// 10_auto_relearn.py (daily); src/employees.test.js checks this against a
// real run log. Positions/colors are layout only, all task data comes from
// the run logs on GitHub.

export const BUILDINGS = [
  { id: "data", name: "Market Data Center", color: "#38bdf8", position: [-7, 0, -3.5], height: 2.4, seed: 11 },
  { id: "signals", name: "Signal Analysis Lab", color: "#34d399", position: [-3.5, 0, -3.5], height: 3.0, seed: 22 },
  { id: "risk", name: "Risk Office", color: "#f87171", position: [0, 0, -3.5], height: 2.6, seed: 33 },
  { id: "news", name: "News & Sentiment Desk", color: "#fbbf24", position: [3.5, 0, -3.5], height: 2.4, seed: 44 },
  { id: "trading", name: "Trading Floor", color: "#f472b6", position: [7, 0, -3.5], height: 3.4, seed: 55 },
  { id: "research", name: "Pattern Research Lab", color: "#a78bfa", position: [-7, 0, 3.5], height: 2.8, seed: 66 },
  { id: "validation", name: "Validation Center", color: "#2dd4bf", position: [-3.5, 0, 3.5], height: 2.6, seed: 77 },
  { id: "backtest", name: "Historical Simulation Lab", color: "#60a5fa", position: [0, 0, 3.5], height: 3.0, seed: 88 },
  {
    id: "strategy_lab", name: "Strategy Research Lab", color: "#6b7280", position: [3.5, 0, 3.5], height: 2.2, seed: 99,
    plannedOnly: true,
    note: "Nobody works here yet. The project has one strategy (moving-average crossover); RSI, momentum and mean-reversion strategies haven't been built.",
  },
  {
    id: "ml_lab", name: "Model Research Lab", color: "#6b7280", position: [7, 0, 3.5], height: 2.2, seed: 101,
    plannedOnly: true,
    note: "Nobody works here yet. No machine-learning model has been trained; a few hundred trades is far too little data to train one honestly.",
  },
];

export const EMPLOYEES = [
  // hourly run, in pipeline order
  { id: "price_fetcher", title: "Price Fetcher", building: "data", run: "hourly",
    next: "Hands the candles to the Data Checker." },
  { id: "data_checker", title: "Data Checker", building: "data", run: "hourly",
    next: "Passes clean candles to the Indicator Analyst." },
  { id: "indicator_analyst", title: "Indicator Analyst", building: "signals", run: "hourly",
    next: "Gives the averages to the Signal Watcher." },
  { id: "signal_watcher", title: "Signal Watcher", building: "signals", run: "hourly",
    next: "Reports buy / sell / no signal to the Risk Officer and Trader." },
  { id: "risk_officer", title: "Risk Officer", building: "risk", run: "hourly",
    next: "Clears or blocks the Trader based on drawdown and stop-loss." },
  { id: "news_reader", title: "News Reader", building: "news", run: "hourly",
    next: "Logs sentiment for future research. It does not affect trades yet." },
  { id: "mood_analyst", title: "Mood Analyst", building: "news", run: "hourly",
    next: "Logs the Fear & Greed reading. It does not affect trades yet." },
  { id: "trader", title: "Trader", building: "trading", run: "hourly",
    next: "Hands the updated portfolio to the Record Keeper." },
  { id: "record_keeper", title: "Record Keeper", building: "trading", run: "hourly",
    next: "GitHub Actions commits the files, then everyone waits for the next hour." },

  // daily run
  { id: "historian", title: "Historian", building: "research", run: "daily",
    next: "Hands the history to the Pattern Researcher." },
  { id: "pattern_researcher", title: "Pattern Researcher", building: "research", run: "daily",
    next: "Sends the pattern table to the Validator, then saves it for the Trader." },
  { id: "validator", title: "Validator", building: "validation", run: "daily",
    next: "Its verdict is recorded in relearn_history.csv." },

  // not scheduled, data comes from the exported backtest snapshot
  { id: "backtest_analyst", title: "Backtest Analyst", building: "backtest", run: "manual",
    task: "Replays the strategy over 2 years of BTC history, with fees and risk rules",
    next: "Only works when someone runs export_city_data.py; there's no schedule for backtests yet." },
];

export const RUN_SCHEDULES = {
  hourly: "Every hour at :05 UTC (GitHub Actions can start a few minutes late)",
  daily: "Once a day at 00:15 UTC",
  manual: "Not scheduled, runs only when started by hand",
};

export function employeesIn(buildingId) {
  return EMPLOYEES.filter((e) => e.building === buildingId);
}

export function buildingOf(employee) {
  return BUILDINGS.find((b) => b.id === employee.building);
}

// Where an employee stands in the city: in a row in front of their building.
export function employeePosition(employee) {
  const building = buildingOf(employee);
  const coworkers = employeesIn(employee.building);
  const i = coworkers.findIndex((e) => e.id === employee.id);
  const offset = (i - (coworkers.length - 1) / 2) * 0.6;
  return [building.position[0] + offset, 0, building.position[2] + 1.35];
}
