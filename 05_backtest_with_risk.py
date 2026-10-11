"""
Step 5: same MA crossover strategy, now with real risk management:

1. Position sizing: only risk a fixed % of the account per trade, not all of it.
2. Stop-loss: exit automatically if a trade drops X% below entry, don't wait
   for the next crossover signal (which can be slow to arrive).
3. Max-drawdown kill switch: if the account falls more than Y% below its
   peak, stop trading entirely until a human reviews it.

This is the version that's actually sane to paper trade.
"""
import pandas as pd
import numpy as np

SHORT_WINDOW = 24
LONG_WINDOW = 72
STARTING_BALANCE = 1000.0
FEE_RATE = 0.001

RISK_PER_TRADE = 0.02      # risk 2% of current equity per trade
STOP_LOSS_PCT = 0.03       # exit if price drops 3% below entry
MAX_DRAWDOWN_KILL = 0.20   # stop trading if equity falls 20% from its peak

df = pd.read_csv("btc_usdt_1h.csv", parse_dates=["timestamp"])
df["short_ma"] = df["close"].rolling(window=SHORT_WINDOW).mean()
df["long_ma"] = df["close"].rolling(window=LONG_WINDOW).mean()
df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)
df["position_change"] = df["signal"].diff()
df = df.dropna(subset=["short_ma", "long_ma"]).reset_index(drop=True)

cash = STARTING_BALANCE
btc = 0.0
in_position = False
entry_price = 0.0
position_value_at_entry = 0.0
trading_halted = False
peak_equity = STARTING_BALANCE

trades = []
equity_curve = []
halt_events = []

for _, row in df.iterrows():
    price = row["close"]
    equity_now = cash + btc * price
    peak_equity = max(peak_equity, equity_now)
    current_drawdown = (equity_now - peak_equity) / peak_equity

    # kill switch: if we're down too much from the peak, stop opening new trades
    if not trading_halted and current_drawdown <= -MAX_DRAWDOWN_KILL:
        trading_halted = True
        halt_events.append(row["timestamp"])

    # stop-loss check while in a position
    if in_position and price <= entry_price * (1 - STOP_LOSS_PCT):
        cash += (btc * price) * (1 - FEE_RATE)
        pnl_pct = (price - entry_price) / entry_price * 100
        trades.append({"exit_time": row["timestamp"], "exit_price": price,
                        "pnl_pct": pnl_pct, "reason": "stop_loss"})
        btc = 0.0
        in_position = False

    # normal signal-based entries/exits, skipped entirely if halted
    elif not trading_halted and row["position_change"] == 1 and not in_position:
        trade_capital = cash * RISK_PER_TRADE / STOP_LOSS_PCT  # size so a stop-out loses ~RISK_PER_TRADE of equity
        trade_capital = min(trade_capital, cash)  # never use more cash than we have
        btc = (trade_capital * (1 - FEE_RATE)) / price
        cash -= trade_capital
        entry_price = price
        in_position = True

    elif row["position_change"] == -1 and in_position:
        proceeds = (btc * price) * (1 - FEE_RATE)
        cash += proceeds
        pnl_pct = (price - entry_price) / entry_price * 100
        trades.append({"exit_time": row["timestamp"], "exit_price": price,
                        "pnl_pct": pnl_pct, "reason": "signal"})
        btc = 0.0
        in_position = False

    equity_curve.append(cash if not in_position else cash + btc * price)

df["equity"] = equity_curve
final_equity = df["equity"].iloc[-1]

trades_df = pd.DataFrame(trades)
num_trades = len(trades_df)
win_rate = (trades_df["pnl_pct"] > 0).mean() * 100 if num_trades else 0
stop_loss_exits = (trades_df["reason"] == "stop_loss").sum() if num_trades else 0

running_max = df["equity"].cummax()
drawdown = (df["equity"] - running_max) / running_max * 100
max_drawdown = drawdown.min()

start_price = df["close"].iloc[0]
end_price = df["close"].iloc[-1]
buy_hold_equity = STARTING_BALANCE * (end_price / start_price)

strategy_return_pct = (final_equity - STARTING_BALANCE) / STARTING_BALANCE * 100
buy_hold_return_pct = (buy_hold_equity - STARTING_BALANCE) / STARTING_BALANCE * 100

print("=" * 60)
print("STRATEGY WITH RISK MANAGEMENT")
print("=" * 60)
print(f"Risk per trade:     {RISK_PER_TRADE*100:.1f}% of equity")
print(f"Stop-loss:          {STOP_LOSS_PCT*100:.1f}% below entry")
print(f"Max-drawdown kill:  {MAX_DRAWDOWN_KILL*100:.1f}%")
print(f"\nFinal equity:       ${final_equity:,.2f}")
print(f"Total return:       {strategy_return_pct:+.2f}%")
print(f"Number of trades:   {num_trades}")
print(f"  - stop-loss exits: {stop_loss_exits}")
print(f"  - signal exits:    {num_trades - stop_loss_exits}")
print(f"Win rate:           {win_rate:.1f}%")
print(f"Max drawdown:       {max_drawdown:.2f}%")
print(f"Trading halted?:    {trading_halted}")
if halt_events:
    print(f"Halted at:          {halt_events[0]}")

print(f"\nBuy & hold return:  {buy_hold_return_pct:+.2f}%")
print("\n(This is weaker than the no-risk-management version by design --")
print(" stop-losses lock in small losses that might have recovered, but")
print(" they cap the worst-case damage, which matters once real money is on the line.)")

df.to_csv("backtest_with_risk_equity_curve.csv", index=False)
trades_df.to_csv("backtest_with_risk_trades.csv", index=False)
