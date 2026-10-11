# Research City — vertical slice

A small interactive visualization of the trading research pipeline. This is
deliberately scoped down from the full spec in the master prompt: it shows
the **5 departments that actually have real, running implementations**
(Market Data, Backtesting, Validation, Self-Learning Analysis, Operations),
plus 2 placeholder buildings (Strategy Discovery, Machine Learning) that are
honestly labeled "NOT IMPLEMENTED" rather than showing fake activity, since
the underlying project genuinely only has one strategy family (MA crossover)
so far.

## What's real here

Every number in every inspector panel comes from `export_city_data.py`
reading the project's actual output files (`btc_usdt_1h.csv`,
`paper_state.json`, `paper_trade_log.csv`, `optimization_results.csv`,
`relearn_history.csv`). Nothing is fabricated. An idle department shows
"No backtest run yet" rather than inventing a task.

## What's NOT real (yet), by design

- **Live updates**: this is a polling snapshot, not a WebSocket/SSE stream.
  GitHub Actions runs on an hourly/daily schedule with no persistent server
  process to push events from, so "live" here honestly means "re-run the
  exporter, then refresh the page."
- **Demo mode**: not implemented. The banner always shows "REAL DATA" because
  that's all that exists right now.
- **Pathfinding / walking animation between buildings**: bots are stationary
  with a small idle animation, not navigating a full city yet.
- **Full 3D models**: deliberately simple primitive shapes (boxes, capsules),
  not sculpted character models, to keep this fast to build and render.

## Running it

From the `trading-bot/` directory (one level up from here):

```bash
python export_city_data.py   # regenerates city/public/city_data.json from real project data
cd city
npm install
npm run dev                  # opens http://localhost:5173
```

## Running the tests

```bash
cd city
npm run test
```

Covers: stale-data detection, inspector panels rendering real vs. idle vs.
not-implemented states correctly, and that every department is honestly
flagged as implemented or not.
