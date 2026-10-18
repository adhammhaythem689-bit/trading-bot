# Research City

A 3D view of the trading bot's real work. Every employee is one real step of
the scheduled runs on GitHub Actions, and every number they show comes from
the step log that run wrote.

## Who works here

| Building | Employee | Real job (from the run log) |
|---|---|---|
| Market Data Center | Price Fetcher | pulls the latest hourly BTC/USD candles from Kraken |
| | Data Checker | checks them for gaps, duplicates, bad prices |
| Signal Analysis Lab | Indicator Analyst | 24h and 72h moving averages |
| | Signal Watcher | did they cross this hour, and what that means |
| Risk Office | Risk Officer | drawdown vs the 20% kill switch, distance to stop-loss |
| News & Sentiment Desk | News Reader | headline count, sentiment score, sample headlines |
| | Mood Analyst | Fear & Greed index |
| Trading Floor | Trader | buy / sell / hold and the resulting paper portfolio |
| | Record Keeper | saves state for GitHub to commit |
| Pattern Research Lab | Historian | loads the stored 2-year history (daily run) |
| | Pattern Researcher | counts trustworthy market-condition patterns (daily) |
| Validation Center | Validator | does the pattern filter help on unseen data (daily) |
| Historical Simulation Lab | Backtest Analyst | 2-year backtest; not scheduled, from `export_city_data.py` |
| Strategy Research Lab | Trend, Breakout, Dip Researchers | live paper experiments from `12_experiments.py`, each with its own $1,000 |
| Model Research Lab | nobody | not implemented, so nobody works there |

## Where the data comes from

`engine/runlog.py` records each step of `06_paper_trade.py` (hourly) and
`10_auto_relearn.py` (daily): start/end time, status, and outputs. The
workflows commit `runlog/latest_hourly.json` and `runlog/latest_daily.json`.
The repo is public, so the city reads them straight from
`raw.githubusercontent.com` every 2 minutes. Your laptop doesn't run anything.

**What "live" honestly means:** a run takes a few seconds once an hour.
The rest of the time everyone is waiting, showing their latest result. The
top bar shows how long ago each run finished and when the next one is due,
and turns amber if a run is late (GitHub's scheduler sometimes is). GitHub's
CDN can serve files up to ~5 minutes old.

**Replay** plays back the last run's steps in order, with their real status
and duration, and is clearly labeled as a replay.

A failed run still publishes its log, so the employee whose step broke shows
the actual error, and the ones after them show "Didn't start".

## Running it

```bash
cd city
npm install
npm run dev        # http://localhost:5173, reads live data from GitHub
```

### Testing against local data

Create `city/.env.local` with `VITE_DATA_BASE=/dev-data` and put run logs in
`city/public/dev-data/runlog/` (both are gitignored). The city then shows a
"LOCAL TEST DATA" badge instead of "LIVE FROM GITHUB".

## Tests

```bash
npm run test
```

Includes a cross-check against real run logs in `src/__fixtures__/`: if a
step is added or renamed in Python without updating `src/employees.js`, the
tests fail.
