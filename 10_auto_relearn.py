"""
Step 10: periodic re-learning -- built on the shared engine.

Previously this ran 07/08 as subprocesses and parsed their printed text
output with regex to extract numbers, which is fragile (any wording change
silently breaks it). Now it calls the engine functions directly and reads
structured results, no text parsing involved.

Appends a dated row to relearn_history.csv tracking:
  - how many condition combinations exist
  - how many are "reliable" (n >= config.min_samples)
  - whether the filter helped or hurt on unseen data that run

This is how we honestly track progress toward "the self-learning system has
enough real data to trust" -- watch reliable_combos climb over weeks/months
as the paper trader keeps accumulating real trades.

Usage:
    python 10_auto_relearn.py            # run forever, re-check once per day
    python 10_auto_relearn.py --once      # run one time now and exit
"""
import csv
import os
import sys
import time
import json
from datetime import datetime, timezone

from engine.config import DEFAULT_CONFIG
from engine.data import load_ohlcv_csv
from engine.features import prepare
from engine.learning import label_trades_with_conditions, learn_filters
from engine.backtest import run_backtest
from engine.metrics import compute_metrics

HISTORY_FILE = "relearn_history.csv"
LEARNED_FILTERS_FILE = "learned_filters.json"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60  # once per day


def run_once():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Re-running self-analysis...")
    config = DEFAULT_CONFIG
    df_full, warnings = load_ohlcv_csv("btc_usdt_1h.csv")
    for w in warnings:
        print(f"  Data quality warning: {w}")

    split_idx = int(len(df_full) * 0.75)
    train_df = df_full.iloc[:split_idx].reset_index(drop=True)
    test_df = df_full.iloc[split_idx:].reset_index(drop=True)

    train_prepared = prepare(train_df, config)
    test_prepared = prepare(test_df, config)

    labeled, bins = label_trades_with_conditions(train_prepared, config)
    learned_filters = learn_filters(labeled, config.min_samples)
    reliable_count = sum(1 for v in learned_filters.values() if v["reliable"])

    baseline = compute_metrics(run_backtest(test_prepared, config), config.starting_balance)
    adaptive = compute_metrics(run_backtest(test_prepared, config, learned_filters=learned_filters, bins=bins),
                                config.starting_balance)
    filter_helped = adaptive["return_pct"] > baseline["return_pct"]

    # also compute on the FULL dataset (not just training split) for the saved lookup table,
    # since this is what 06_paper_trade.py actually loads and uses
    full_prepared = prepare(df_full, config)
    full_labeled, full_bins = label_trades_with_conditions(full_prepared, config)
    full_filters = learn_filters(full_labeled, config.min_samples)
    with open(LEARNED_FILTERS_FILE, "w") as f:
        json.dump(full_filters, f, indent=2)

    row = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_trades": len(labeled),
        "reliable_combos": reliable_count,
        "total_combos": len(learned_filters),
        "filter_helped_on_test": filter_helped,
        "baseline_return_pct": round(baseline["return_pct"], 2),
        "adaptive_return_pct": round(adaptive["return_pct"], 2),
    }
    print(f"  Total trades: {row['total_trades']}, reliable combos: {row['reliable_combos']}/{row['total_combos']}, "
          f"filter helped on test data: {row['filter_helped_on_test']}")

    header_needed = not os.path.exists(HISTORY_FILE)
    with open(HISTORY_FILE, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row.keys()))
        if header_needed:
            writer.writeheader()
        writer.writerow(row)
    print(f"  Appended to {HISTORY_FILE}")


if __name__ == "__main__":
    run_forever = "--once" not in sys.argv
    if not run_forever:
        run_once()
    else:
        while True:
            run_once()
            print(f"Sleeping {CHECK_INTERVAL_SECONDS}s until next re-learn check...\n")
            time.sleep(CHECK_INTERVAL_SECONDS)
