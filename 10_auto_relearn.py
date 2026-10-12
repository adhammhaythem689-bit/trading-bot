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
from engine.runlog import RunLogger
from engine.history import extend_history
import requests

HISTORY_FILE = "relearn_history.csv"
PRICE_HISTORY_FILE = "btc_usdt_1h.csv"
LEARNED_FILTERS_FILE = "learned_filters.json"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60  # once per day


DAILY_STEPS = [
    ("refresh_history", "historian", "Add newly closed hourly candles from Binance to the stored history"),
    ("load_history", "historian", "Load the stored BTC price history and check its quality"),
    ("find_patterns", "pattern_researcher", "Tag past trades by market conditions and count trustworthy patterns"),
    ("validate_filter", "validator", "Test whether the pattern filter helps on data it never saw"),
    ("save_filters", "pattern_researcher", "Save the pattern table the hourly trader reads"),
]


def run_once():
    log = RunLogger("daily", DAILY_STEPS)
    try:
        _run_steps(log)
    finally:
        log.write()


def _run_steps(log):
    print(f"[{datetime.now(timezone.utc).isoformat()}] Re-running self-analysis...")
    config = DEFAULT_CONFIG

    with log.step("refresh_history") as s:
        try:
            result = extend_history(PRICE_HISTORY_FILE)
            s.output(source="Binance BTC/USDT (data-api.binance.vision)", **result)
            print(f"  History: +{result['appended']} new candles, {result['replaced']} re-fetched, "
                  f"now ends {result['last_candle']}")
        except requests.RequestException as e:
            # don't fall back to another exchange's prices; analyze the existing file instead
            s.output(source="Binance BTC/USDT (data-api.binance.vision)", appended=0)
            s.warn(f"Couldn't reach Binance, history not refreshed this run: {e}")
            print(f"  Warning: history not refreshed: {e}")

    with log.step("load_history") as s:
        df_full, warnings = load_ohlcv_csv(PRICE_HISTORY_FILE)
        for w in warnings:
            print(f"  Data quality warning: {w}")
        s.output(candles=len(df_full), first_candle=df_full["timestamp"].iloc[0],
                 last_candle=df_full["timestamp"].iloc[-1],
                 warnings=[f"{w.kind}: {w.detail}" for w in warnings])

    with log.step("find_patterns") as s:
        split_idx = int(len(df_full) * 0.75)
        train_df = df_full.iloc[:split_idx].reset_index(drop=True)
        test_df = df_full.iloc[split_idx:].reset_index(drop=True)
        train_prepared = prepare(train_df, config)
        test_prepared = prepare(test_df, config)

        labeled, bins = label_trades_with_conditions(train_prepared, config)
        learned_filters = learn_filters(labeled, config.min_samples)
        reliable_count = sum(1 for v in learned_filters.values() if v["reliable"])
        most_seen = sorted(learned_filters.items(), key=lambda kv: kv[1]["n"], reverse=True)[:3]
        s.output(training_period=f"{train_df['timestamp'].iloc[0]} to {train_df['timestamp'].iloc[-1]}",
                 trades_tagged=len(labeled), patterns_found=len(learned_filters),
                 reliable_patterns=reliable_count, trades_needed_per_pattern=config.min_samples,
                 most_common=[f"{combo} (n={info['n']}, win {info['win_rate']}%)" for combo, info in most_seen])

    with log.step("validate_filter") as s:
        baseline = compute_metrics(run_backtest(test_prepared, config), config.starting_balance)
        adaptive = compute_metrics(run_backtest(test_prepared, config, learned_filters=learned_filters, bins=bins),
                                    config.starting_balance)
        filter_helped = adaptive["return_pct"] > baseline["return_pct"]
        s.output(test_period=f"{test_df['timestamp'].iloc[0]} to {test_df['timestamp'].iloc[-1]}",
                 without_filter_return_pct=round(baseline["return_pct"], 2),
                 with_filter_return_pct=round(adaptive["return_pct"], 2),
                 trades_skipped_by_filter=adaptive["skipped_by_filter"],
                 verdict="filter helped" if filter_helped else
                         "no difference, no pattern is trusted yet" if reliable_count == 0 else "filter did not help")

    with log.step("save_filters") as s:
        # computed on the FULL dataset for the saved lookup table, since this
        # is what 06_paper_trade.py actually loads and uses
        full_prepared = prepare(df_full, config)
        full_labeled, full_bins = label_trades_with_conditions(full_prepared, config)
        full_filters = learn_filters(full_labeled, config.min_samples)
        with open(LEARNED_FILTERS_FILE, "w") as f:
            json.dump(full_filters, f, indent=2)
        s.output(file=LEARNED_FILTERS_FILE, patterns_saved=len(full_filters),
                 reliable_saved=sum(1 for v in full_filters.values() if v["reliable"]))

    log.finish("done", f"{reliable_count}/{len(learned_filters)} patterns trusted, "
                       f"filter helped: {filter_helped}")

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
