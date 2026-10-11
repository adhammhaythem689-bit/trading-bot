"""
Step 3: full backtest of the moving-average crossover strategy.

Simulates actually trading the signals with a starting balance, including a
realistic trading fee, and reports the metrics that actually matter:
total return, win rate, max drawdown, number of trades, and a comparison
against simple buy-and-hold (the benchmark any strategy has to beat).
"""
import pandas as pd
import numpy as np

SHORT_WINDOW = 12
LONG_WINDOW = 48
STARTING_BALANCE = 1000.0
FEE_RATE = 0.001  # 0.1% per trade, typical spot taker fee

df = pd.read_csv("btc_usdt_1h.csv", parse_dates=["timestamp"])

df["short_ma"] = df["close"].rolling(window=SHORT_WINDOW).mean()
df["long_ma"] = df["close"].rolling(window=LONG_WINDOW).mean()
df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)
df["position_change"] = df["signal"].diff()
df = df.dropna(subset=["short_ma", "long_ma"]).reset_index(drop=True)

# --- simulate the strategy ---
cash = STARTING_BALANCE
btc = 0.0
in_position = False
entry_price = 0.0
trades = []  # each trade: (entry_time, exit_time, entry_price, exit_price, pnl_pct)
equity_curve = []

for _, row in df.iterrows():
    price = row["close"]

    if row["position_change"] == 1 and not in_position:
        # buy signal: convert all cash to BTC, minus fee
        btc = (cash * (1 - FEE_RATE)) / price
        entry_price = price
        entry_time = row["timestamp"]
        cash = 0.0
        in_position = True

    elif row["position_change"] == -1 and in_position:
        # sell signal: convert all BTC back to cash, minus fee
        cash = (btc * price) * (1 - FEE_RATE)
        pnl_pct = (price - entry_price) / entry_price * 100
        trades.append({
            "entry_time": entry_time, "exit_time": row["timestamp"],
            "entry_price": entry_price, "exit_price": price, "pnl_pct": pnl_pct
        })
        btc = 0.0
        in_position = False

    # mark-to-market equity at every step (cash, or btc value if holding)
    equity = cash if not in_position else btc * price
    equity_curve.append(equity)

df["equity"] = equity_curve

# if still holding BTC at the end, close out the position at the last price for reporting
final_equity = df["equity"].iloc[-1]

# --- buy-and-hold benchmark ---
start_price = df["close"].iloc[0]
end_price = df["close"].iloc[-1]
buy_hold_equity = STARTING_BALANCE * (end_price / start_price)

# --- metrics ---
trades_df = pd.DataFrame(trades)
num_trades = len(trades_df)
win_rate = (trades_df["pnl_pct"] > 0).mean() * 100 if num_trades else 0
avg_win = trades_df.loc[trades_df["pnl_pct"] > 0, "pnl_pct"].mean() if num_trades else 0
avg_loss = trades_df.loc[trades_df["pnl_pct"] <= 0, "pnl_pct"].mean() if num_trades else 0

# max drawdown on the equity curve
running_max = df["equity"].cummax()
drawdown = (df["equity"] - running_max) / running_max * 100
max_drawdown = drawdown.min()

strategy_return_pct = (final_equity - STARTING_BALANCE) / STARTING_BALANCE * 100
buy_hold_return_pct = (buy_hold_equity - STARTING_BALANCE) / STARTING_BALANCE * 100

print("=" * 60)
print(f"Backtest period: {df['timestamp'].iloc[0]} to {df['timestamp'].iloc[-1]}")
print(f"Starting balance: ${STARTING_BALANCE:,.2f}")
print("=" * 60)
print(f"\n--- STRATEGY (MA {SHORT_WINDOW}/{LONG_WINDOW} crossover) ---")
print(f"Final equity:      ${final_equity:,.2f}")
print(f"Total return:      {strategy_return_pct:+.2f}%")
print(f"Number of trades:  {num_trades}")
print(f"Win rate:          {win_rate:.1f}%")
print(f"Avg win:           {avg_win:+.2f}%")
print(f"Avg loss:          {avg_loss:+.2f}%")
print(f"Max drawdown:      {max_drawdown:.2f}%")
print(f"Still in position: {in_position}")

print(f"\n--- BUY & HOLD (benchmark) ---")
print(f"Final equity:      ${buy_hold_equity:,.2f}")
print(f"Total return:      {buy_hold_return_pct:+.2f}%")

print(f"\n--- VERDICT ---")
if strategy_return_pct > buy_hold_return_pct:
    print(f"Strategy BEAT buy-and-hold by {strategy_return_pct - buy_hold_return_pct:.2f} percentage points.")
else:
    print(f"Strategy LOST to buy-and-hold by {buy_hold_return_pct - strategy_return_pct:.2f} percentage points.")
print("(Past performance on this one window is not evidence of future results.)")

df.to_csv("backtest_equity_curve.csv", index=False)
trades_df.to_csv("backtest_trades.csv", index=False)
print("\nSaved equity curve to backtest_equity_curve.csv")
print("Saved trade log to backtest_trades.csv")
