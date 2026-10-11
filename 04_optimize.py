"""
Step 4: parameter sweep.

Instead of guessing a short/long MA pair, test a grid of combinations against
the same historical data and rank them. This also surfaces an important
lesson: picking "the best" combo on this exact data is itself a form of
overfitting (curve-fitting to the past), so we hold out the last chunk of
data as a validation set the winning combo was never tuned on.
"""
import pandas as pd
import numpy as np
import itertools

STARTING_BALANCE = 1000.0
FEE_RATE = 0.001

df_full = pd.read_csv("btc_usdt_1h.csv", parse_dates=["timestamp"])

# split: tune on the first 75%, validate on the last 25% (data the combo never saw)
split_idx = int(len(df_full) * 0.75)
train_df = df_full.iloc[:split_idx].reset_index(drop=True)
test_df = df_full.iloc[split_idx:].reset_index(drop=True)


def run_backtest(df, short_window, long_window):
    df = df.copy()
    df["short_ma"] = df["close"].rolling(window=short_window).mean()
    df["long_ma"] = df["close"].rolling(window=long_window).mean()
    df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)
    df["position_change"] = df["signal"].diff()
    df = df.dropna(subset=["short_ma", "long_ma"]).reset_index(drop=True)

    cash, btc, in_position = STARTING_BALANCE, 0.0, False
    entry_price = 0.0
    trades = []
    equity_curve = []

    for _, row in df.iterrows():
        price = row["close"]
        if row["position_change"] == 1 and not in_position:
            btc = (cash * (1 - FEE_RATE)) / price
            entry_price = price
            cash = 0.0
            in_position = True
        elif row["position_change"] == -1 and in_position:
            cash = (btc * price) * (1 - FEE_RATE)
            trades.append((price - entry_price) / entry_price * 100)
            btc = 0.0
            in_position = False
        equity_curve.append(cash if not in_position else btc * price)

    if not equity_curve:
        return None

    final_equity = equity_curve[-1]
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.cummax()
    drawdown = (equity_series - running_max) / running_max * 100
    max_dd = drawdown.min()
    num_trades = len(trades)
    win_rate = (np.array(trades) > 0).mean() * 100 if num_trades else 0
    total_return = (final_equity - STARTING_BALANCE) / STARTING_BALANCE * 100

    return {
        "short": short_window, "long": long_window,
        "return_pct": total_return, "num_trades": num_trades,
        "win_rate": win_rate, "max_drawdown": max_dd,
    }


short_windows = [6, 12, 24, 36]
long_windows = [24, 48, 72, 96, 120]

results = []
for s, l in itertools.product(short_windows, long_windows):
    if s >= l:
        continue
    res = run_backtest(train_df, s, l)
    if res:
        results.append(res)

results_df = pd.DataFrame(results).sort_values("return_pct", ascending=False)

print("=" * 70)
print("TRAINING SET results (first 75% of data) -- ranked by return")
print("=" * 70)
print(results_df.to_string(index=False))

start_price = train_df["close"].iloc[0]
end_price = train_df["close"].iloc[-1]
train_buy_hold = (end_price / start_price - 1) * 100
print(f"\nBuy-and-hold on training set: {train_buy_hold:+.2f}%")

# take the best combo from training and validate it on unseen data
best = results_df.iloc[0]
print("\n" + "=" * 70)
print(f"VALIDATING best combo (short={int(best['short'])}, long={int(best['long'])}) on UNSEEN test data")
print("=" * 70)
val = run_backtest(test_df, int(best["short"]), int(best["long"]))
print(pd.Series(val))

test_start = test_df["close"].iloc[0]
test_end = test_df["close"].iloc[-1]
test_buy_hold = (test_end / test_start - 1) * 100
print(f"\nBuy-and-hold on test set: {test_buy_hold:+.2f}%")

print("\n--- VERDICT ---")
if val["return_pct"] > test_buy_hold:
    print("Best combo STILL beats buy-and-hold on data it never saw. That's a real signal.")
else:
    print("Best combo LOSES to buy-and-hold on unseen data. The training result was likely overfit/luck.")

results_df.to_csv("optimization_results.csv", index=False)
print("\nSaved full sweep results to optimization_results.csv")
