"""
Data adapter for the research-city visualization.

Reads the project's REAL output files (no fabricated data) and writes a
single consolidated snapshot to city/public/city_data.json, which the
React app fetches. This is a polling snapshot, not a live event stream,
GitHub Actions runs on a schedule with no persistent process to push
events from, so "live" here honestly means "re-run this exporter and
refresh the page" rather than WebSockets.

Usage: python export_city_data.py
"""
import json
import os
from datetime import datetime, timezone
import pandas as pd

from engine.config import DEFAULT_CONFIG
from engine.data import load_ohlcv_csv
from engine.features import prepare
from engine.backtest import run_backtest
from engine.metrics import compute_metrics, buy_and_hold_return_pct

OUT_PATH = os.path.join("city", "public", "city_data.json")


def na(value):
    """JSON-safe: turn NaN/None into the honest string the UI should show."""
    if value is None:
        return "Not available"
    try:
        if pd.isna(value):
            return "Not available"
    except (TypeError, ValueError):
        pass
    return value


def build_data_department():
    if not os.path.exists("btc_usdt_1h.csv"):
        return {"status": "idle", "last_sync": None, "candle_count": 0, "warnings": []}
    df, warnings = load_ohlcv_csv("btc_usdt_1h.csv")
    return {
        "status": "idle",  # the fetcher only runs when 01_fetch_data.py is run manually, not scheduled
        "source": "Binance (historical) / Kraken (live)",
        "candle_count": len(df),
        "latest_candle": str(df["timestamp"].iloc[-1]) if len(df) else "Not available",
        "earliest_candle": str(df["timestamp"].iloc[0]) if len(df) else "Not available",
        "warnings": [f"{w.kind}: {w.detail}" for w in warnings],
    }


def build_backtest_department():
    if not os.path.exists("btc_usdt_1h.csv"):
        return {"status": "idle"}
    config = DEFAULT_CONFIG
    df, _ = load_ohlcv_csv("btc_usdt_1h.csv")
    prepared = prepare(df, config)
    result = run_backtest(prepared, config)
    metrics = compute_metrics(result, config.starting_balance)
    buy_hold = buy_and_hold_return_pct(prepared)

    equity = result.equity_curve
    sample_n = 60
    step = max(1, len(equity) // sample_n)
    sparkline = equity[::step]

    return {
        "status": "complete",
        "strategy_name": config.name,
        "strategy_version": config.version,
        "params": {"short_window": config.short_window, "long_window": config.long_window,
                    "risk_per_trade": config.risk_per_trade, "stop_loss_pct": config.stop_loss_pct},
        "period": f"{prepared['timestamp'].iloc[0]} to {prepared['timestamp'].iloc[-1]}",
        "metrics": {
            "return_pct": round(metrics["return_pct"], 2),
            "num_trades": metrics["num_trades"],
            "win_rate": round(metrics["win_rate"], 1),
            "max_drawdown_pct": round(metrics["max_drawdown_pct"], 2),
            "profit_factor": round(metrics["profit_factor"], 2) if metrics["profit_factor"] != float("inf") else "inf",
        },
        "buy_and_hold_pct": round(buy_hold, 2),
        "beat_buy_and_hold": metrics["return_pct"] > buy_hold,
        "equity_sparkline": [round(v, 2) for v in sparkline],
    }


def build_validation_department():
    if not os.path.exists("optimization_results.csv"):
        return {"status": "idle"}
    opt = pd.read_csv("optimization_results.csv")
    best = opt.iloc[0]
    return {
        "status": "inconclusive",  # honest: 04_optimize.py's own verdict logic should drive this long-term
        "method": "Chronological 75/25 train/test split",
        "best_training_combo": f"short={int(best['short'])}, long={int(best['long'])}",
        "training_return_pct": round(float(best["return_pct"]), 2),
        "caveat": "Single train/test split only; walk-forward testing (multiple splits) not yet implemented. "
                   "Do not treat this as strong evidence of an edge.",
    }


def build_operations_department():
    if not os.path.exists("paper_state.json"):
        return {"status": "idle"}
    with open("paper_state.json") as f:
        state = json.load(f)

    recent_trades = []
    if os.path.exists("paper_trade_log.csv"):
        log = pd.read_csv("paper_trade_log.csv")
        recent_trades = log.tail(10).to_dict("records")

    return {
        "status": "halted" if state.get("trading_halted") else "running",
        "cash": round(state.get("cash", 0), 2),
        "btc": round(state.get("btc", 0), 6),
        "in_position": state.get("in_position", False),
        "trading_halted": state.get("trading_halted", False),
        "last_candle_ts": state.get("last_candle_ts", "Not available"),
        "recent_log": recent_trades,
    }


def build_relearn_department():
    if not os.path.exists("relearn_history.csv"):
        return {"status": "idle"}
    history = pd.read_csv("relearn_history.csv")
    latest = history.iloc[-1]
    return {
        "status": "complete",
        "total_trades": int(latest["total_trades"]),
        "reliable_combos": int(latest["reliable_combos"]),
        "total_combos": int(latest["total_combos"]),
        "filter_helped_last_run": bool(latest["filter_helped_on_test"]),
        "history_points": history.tail(30)[["timestamp", "reliable_combos", "total_combos"]].to_dict("records"),
    }


city_data = {
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "mode": "real",  # "real" or "demo" -- the UI must render a banner based on this
    "departments": {
        "data_collection": build_data_department(),
        "backtesting": build_backtest_department(),
        "validation": build_validation_department(),
        "operations": build_operations_department(),
        "self_learning": build_relearn_department(),
        "strategy_discovery": {"status": "not_implemented",
                                 "note": "Only one strategy family (MA crossover) exists so far. "
                                          "RSI/momentum/mean-reversion/volatility strategies are planned, not built."},
        "machine_learning": {"status": "not_implemented",
                               "note": "No ML models have been trained. Current trade volume (~100s of trades) "
                                        "is far too small to train one without severe overfitting."},
    },
}

os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
with open(OUT_PATH, "w") as f:
    json.dump(city_data, f, indent=2, default=str)

print(f"Wrote {OUT_PATH}")
print(json.dumps(city_data, indent=2, default=str)[:2000])
