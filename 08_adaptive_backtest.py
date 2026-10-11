"""
Step 8: adaptive backtest -- built on the shared engine.

Trains the self-learning filter on the first 75% of history, then validates
on the last 25% (data it never saw), comparing against the same strategy
with the filter disabled. Same chronological train/test discipline as 04.
"""
from engine.config import DEFAULT_CONFIG
from engine.data import load_ohlcv_csv
from engine.features import prepare
from engine.learning import label_trades_with_conditions, learn_filters
from engine.backtest import run_backtest
from engine.metrics import compute_metrics, buy_and_hold_return_pct

config = DEFAULT_CONFIG
df_full, warnings = load_ohlcv_csv("btc_usdt_1h.csv")
for w in warnings:
    print(f"Data quality warning: {w}")

split_idx = int(len(df_full) * 0.75)
train_df = df_full.iloc[:split_idx].reset_index(drop=True)
test_df = df_full.iloc[split_idx:].reset_index(drop=True)

train_prepared = prepare(train_df, config)
test_prepared = prepare(test_df, config)

labeled, bins = label_trades_with_conditions(train_prepared, config)
learned_filters = learn_filters(labeled, config.min_samples)
print(f"Learned {len(learned_filters)} condition combinations from training data.")
print(f"Of those, {sum(1 for v in learned_filters.values() if v['reliable'])} are reliable (n>={config.min_samples}).")

baseline_result = run_backtest(test_prepared, config)
adaptive_result = run_backtest(test_prepared, config, learned_filters=learned_filters, bins=bins)

baseline = compute_metrics(baseline_result, config.starting_balance)
adaptive = compute_metrics(adaptive_result, config.starting_balance)
buy_hold_pct = buy_and_hold_return_pct(test_prepared)

print("\n" + "=" * 70)
print("RESULTS ON UNSEEN TEST DATA (last 25%, filter never trained on this)")
print("=" * 70)
print(f"{'':20s} {'Baseline (no filter)':>22s} {'Adaptive (with filter)':>24s}")
print(f"{'Return':20s} {baseline['return_pct']:>21.2f}% {adaptive['return_pct']:>23.2f}%")
print(f"{'Num trades':20s} {baseline['num_trades']:>22d} {adaptive['num_trades']:>24d}")
print(f"{'Win rate':20s} {baseline['win_rate']:>21.1f}% {adaptive['win_rate']:>23.1f}%")
print(f"{'Max drawdown':20s} {baseline['max_drawdown_pct']:>21.2f}% {adaptive['max_drawdown_pct']:>23.2f}%")
print(f"{'Trades skipped':20s} {'--':>22s} {adaptive['skipped_by_filter']:>24d}")
print(f"\nBuy & hold on this test period: {buy_hold_pct:+.2f}%")

print("\n--- VERDICT ---")
if adaptive["return_pct"] > baseline["return_pct"]:
    print(f"The learned filter IMPROVED returns by {adaptive['return_pct'] - baseline['return_pct']:.2f} points on unseen data.")
else:
    print(f"The learned filter did NOT improve returns on unseen data "
          f"({adaptive['return_pct']:.2f}% vs {baseline['return_pct']:.2f}%).")
print("With this little data, treat this as a single noisy test, not proof either way.")
