"""
Step 11: strategy research.

Runs every candidate in engine/strategies.py through walk-forward validation
on the stored BTC history and compares the stitched out-of-sample results
against buy & hold and the current bot (SMA 24/72, fixed, no tuning) over
exactly the same period, with the same costs.

Writes research/report.json. Nothing here touches the live paper trader.

Usage: python 11_strategy_research.py
"""
import json
import os
from datetime import datetime, timezone

import numpy as np

from engine.data import load_ohlcv_csv
from engine.strategies import STRATEGIES, sma_cross
from engine.research import (COST_PER_SIDE, walk_forward, simulate, metrics, buy_and_hold)
from engine.runlog import jsonable

TRAIN_HOURS = 270 * 24
TEST_HOURS = 90 * 24
OUT = os.path.join("research", "report.json")


def oos_slice(df):
    n_folds = (len(df) - TRAIN_HOURS) // TEST_HOURS
    return df.iloc[TRAIN_HOURS:TRAIN_HOURS + n_folds * TEST_HOURS].reset_index(drop=True), n_folds


def summarize(m):
    return {k: (round(v, 2) if isinstance(v, float) else v) for k, v in m.items()}


def main():
    df, warnings = load_ohlcv_csv("btc_usdt_1h.csv")
    oos, n_folds = oos_slice(df)
    print(f"History: {len(df)} candles ({df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]})")
    print(f"Out-of-sample: {n_folds} folds of {TEST_HOURS // 24} days, "
          f"{oos['timestamp'].iloc[0]} to {oos['timestamp'].iloc[-1]}")

    bh = buy_and_hold(oos)
    bh_m = metrics(bh, [])
    bh_m["trades"] = 1

    # the current bot, fixed settings, same execution model, same period
    warm = df.iloc[TRAIN_HOURS - 200:TRAIN_HOURS + len(oos)].reset_index(drop=True)
    target = sma_cross(warm, 24, 72).iloc[200:].reset_index(drop=True)
    cur = simulate(oos, target, stop_loss=0.03)
    cur_m = metrics(cur["equity"], cur["trades"])

    results, configs_tried = {}, 0
    for name, strat in STRATEGIES.items():
        configs_tried += len(strat["grid"])
        for sl_label, sl in (("no stop", None), ("3% stop", 0.03)):
            key = f"{name} ({sl_label})"
            wf = walk_forward(df, strat, TRAIN_HOURS, TEST_HOURS, stop_loss=sl)
            wf_hi = walk_forward(df, strat, TRAIN_HOURS, TEST_HOURS, cost=0.003, stop_loss=sl)
            folds_beating = sum(f["return_pct"] > f["buy_hold_pct"] for f in wf["folds"])
            results[key] = {
                "strategy": name, "family": strat["family"], "label": strat["label"],
                "stop_loss": sl, "out_of_sample": summarize(wf["metrics"]),
                "out_of_sample_double_costs_return_pct": round(wf_hi["metrics"]["return_pct"], 2),
                "folds": wf["folds"], "folds_beating_buy_hold": folds_beating,
            }
    configs_tried *= 2  # every grid was run with and without a stop

    ranked = sorted(results.items(), key=lambda kv: kv[1]["out_of_sample"]["sharpe"], reverse=True)

    print(f"\n{'strategy':36s} {'return':>8s} {'2x cost':>8s} {'maxDD':>7s} {'trades':>6s} "
          f"{'win%':>5s} {'sharpe':>6s} {'folds>B&H':>9s}")
    print(f"{'BUY & HOLD':36s} {bh_m['return_pct']:>7.1f}% {'':>8s} {bh_m['max_drawdown_pct']:>6.1f}% "
          f"{1:>6d} {'':>5s} {bh_m['sharpe']:>6.2f}")
    print(f"{'CURRENT BOT (SMA 24/72, 3% stop)':36s} {cur_m['return_pct']:>7.1f}% {'':>8s} "
          f"{cur_m['max_drawdown_pct']:>6.1f}% {cur_m['trades']:>6d} {cur_m['win_rate'] or 0:>5.0f} "
          f"{cur_m['sharpe']:>6.2f}")
    for key, r in ranked:
        m = r["out_of_sample"]
        print(f"{key:36s} {m['return_pct']:>7.1f}% {r['out_of_sample_double_costs_return_pct']:>7.1f}% "
              f"{m['max_drawdown_pct']:>6.1f}% {m['trades']:>6d} {m['win_rate'] or 0:>5.0f} "
              f"{m['sharpe']:>6.2f} {r['folds_beating_buy_hold']:>5d}/{n_folds}")
    print(f"\n{configs_tried} parameter configurations were tried in total. With that many tries, "
          f"one or two looking good by luck is expected.")

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "history": {"candles": len(df), "first": df["timestamp"].iloc[0], "last": df["timestamp"].iloc[-1],
                    "warnings": [f"{w.kind}: {w.detail}" for w in warnings]},
        "method": {
            "walk_forward": f"choose settings on {TRAIN_HOURS // 24} days (best Sharpe), test on the next "
                            f"{TEST_HOURS // 24} days, repeat; {n_folds} folds stitched",
            "execution": "signal at a candle's close, filled at the next candle's open",
            "cost_per_side_pct": COST_PER_SIDE * 100, "double_cost_check_pct": 0.3,
            "position": "long-only, 100% of equity, no leverage",
            "configs_tried": configs_tried,
        },
        "out_of_sample_period": f"{oos['timestamp'].iloc[0]} to {oos['timestamp'].iloc[-1]}",
        "buy_and_hold": summarize(bh_m),
        "current_bot": summarize(cur_m),
        "candidates": dict(ranked),
    }
    os.makedirs("research", exist_ok=True)
    with open(OUT, "w") as f:
        json.dump(jsonable(report), f, indent=2)
    print(f"Saved {OUT}")


if __name__ == "__main__":
    main()
