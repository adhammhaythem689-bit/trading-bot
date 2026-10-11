"""
Step 4: parameter sweep -- built on the shared engine.

Instead of guessing a short/long MA pair, test a grid of combinations against
the same historical data and rank them. This also surfaces an important
lesson: picking "the best" combo on this exact data is itself a form of
overfitting (curve-fitting to the past), so we hold out the last chunk of
data as a validation set the winning combo was never tuned on.
"""
import pandas as pd
import itertools
from dataclasses import replace
from engine.config import BASELINE_NO_RISK_CONFIG
from engine.data import load_ohlcv_csv
from engine.features import prepare
from engine.backtest import run_backtest
from engine.metrics import compute_metrics, buy_and_hold_return_pct

df_full, warnings = load_ohlcv_csv("btc_usdt_1h.csv")
for w in warnings:
    print(f"Data quality warning: {w}")

split_idx = int(len(df_full) * 0.75)
train_df = df_full.iloc[:split_idx].reset_index(drop=True)
test_df = df_full.iloc[split_idx:].reset_index(drop=True)

short_windows = [6, 12, 24, 36]
long_windows = [24, 48, 72, 96, 120]

results = []
for s, l in itertools.product(short_windows, long_windows):
    if s >= l:
        continue
    config = replace(BASELINE_NO_RISK_CONFIG, short_window=s, long_window=l)
    prepared = prepare(train_df, config)
    result = run_backtest(prepared, config)
    metrics = compute_metrics(result, config.starting_balance)
    results.append({"short": s, "long": l, "return_pct": metrics["return_pct"],
                     "num_trades": metrics["num_trades"], "win_rate": metrics["win_rate"],
                     "max_drawdown": metrics["max_drawdown_pct"]})

results_df = pd.DataFrame(results).sort_values("return_pct", ascending=False)

print("=" * 70)
print("TRAINING SET results (first 75% of data) -- ranked by return")
print("=" * 70)
print(results_df.to_string(index=False))

train_prepared_full = prepare(train_df, BASELINE_NO_RISK_CONFIG)
train_buy_hold = buy_and_hold_return_pct(train_prepared_full)
print(f"\nBuy-and-hold on training set: {train_buy_hold:+.2f}%")

# take the best combo from training and validate it on unseen data
best = results_df.iloc[0]
print("\n" + "=" * 70)
print(f"VALIDATING best combo (short={int(best['short'])}, long={int(best['long'])}) on UNSEEN test data")
print("=" * 70)
best_config = replace(BASELINE_NO_RISK_CONFIG, short_window=int(best["short"]), long_window=int(best["long"]))
test_prepared = prepare(test_df, best_config)
val_result = run_backtest(test_prepared, best_config)
val_metrics = compute_metrics(val_result, best_config.starting_balance)
print(pd.Series(val_metrics))

test_buy_hold = buy_and_hold_return_pct(test_prepared)
print(f"\nBuy-and-hold on test set: {test_buy_hold:+.2f}%")

print("\n--- VERDICT ---")
if val_metrics["return_pct"] > test_buy_hold:
    print("Best combo STILL beats buy-and-hold on data it never saw. That's a real signal.")
else:
    print("Best combo LOSES to buy-and-hold on unseen data. The training result was likely overfit/luck.")

results_df.to_csv("optimization_results.csv", index=False)
print("\nSaved full sweep results to optimization_results.csv")
