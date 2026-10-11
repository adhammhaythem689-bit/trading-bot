"""
Step 10: periodic re-learning.

Runs the self-analysis (07) and adaptive validation (08) automatically on a
schedule, and appends a dated row to relearn_history.csv tracking:
  - how many condition combinations exist
  - how many are "reliable" (n >= MIN_SAMPLES)
  - whether the filter helped or hurt on unseen data that run

This is how we honestly track progress toward "the self-learning system has
enough real data to trust" -- watch reliable_combos climb over weeks/months
as the paper trader keeps accumulating real trades.

Usage:
    python 10_auto_relearn.py            # run forever, re-check once per day
    python 10_auto_relearn.py --once      # run one time now and exit
"""
import subprocess
import re
import csv
import os
import sys
import time
from datetime import datetime, timezone

HISTORY_FILE = "relearn_history.csv"
CHECK_INTERVAL_SECONDS = 24 * 60 * 60  # once per day


def run_and_capture(script):
    result = subprocess.run([sys.executable, script], capture_output=True, text=True)
    return result.stdout + result.stderr


def parse_results(analyze_output, adaptive_output):
    total_combos = re.search(r"(\d+) of (\d+) combinations have enough trades", analyze_output)
    reliable_n = int(total_combos.group(1)) if total_combos else None
    total_n = int(total_combos.group(2)) if total_combos else None

    total_trades_match = re.search(r"Total trades analyzed: (\d+)", analyze_output)
    total_trades = int(total_trades_match.group(1)) if total_trades_match else None

    improved = "IMPROVED" in adaptive_output
    no_change = "did NOT improve" in adaptive_output and "8.73% vs 8.73%" not in adaptive_output

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_trades": total_trades,
        "reliable_combos": reliable_n,
        "total_combos": total_n,
        "filter_helped_on_test": improved,
    }


def run_once():
    print(f"[{datetime.now(timezone.utc).isoformat()}] Re-running self-analysis...")
    analyze_output = run_and_capture("07_analyze_trades.py")
    adaptive_output = run_and_capture("08_adaptive_backtest.py")

    row = parse_results(analyze_output, adaptive_output)
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
