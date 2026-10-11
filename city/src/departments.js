// Static layout + metadata for each department building/bot. Positions are
// the only "made up" values here, everything else comes from city_data.json.
export const DEPARTMENTS = [
  {
    id: "data_collection",
    name: "Market Data Center",
    role: "Data Collection",
    color: "#38bdf8",
    position: [-6, 0, -4],
  },
  {
    id: "backtesting",
    name: "Historical Simulation Lab",
    role: "Backtesting",
    color: "#34d399",
    position: [-2, 0, -4],
  },
  {
    id: "validation",
    name: "Validation Center",
    role: "Validation & Risk",
    color: "#fbbf24",
    position: [2, 0, -4],
  },
  {
    id: "self_learning",
    name: "Pattern Research Lab",
    role: "Self-Learning Analysis",
    color: "#a78bfa",
    position: [6, 0, -4],
  },
  {
    id: "operations",
    name: "Operations Center",
    role: "Paper-Trading Operations",
    color: "#f472b6",
    position: [0, 0, 2],
  },
  {
    id: "strategy_discovery",
    name: "Strategy Research Lab",
    role: "Strategy Discovery",
    color: "#6b7280",
    position: [-4, 0, 5],
    plannedOnly: true,
  },
  {
    id: "machine_learning",
    name: "Model Research Lab",
    role: "Machine Learning",
    color: "#6b7280",
    position: [4, 0, 5],
    plannedOnly: true,
  },
];
