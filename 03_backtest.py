"""
Step 3: baseline backtest (no risk management) -- now built on the shared
engine instead of its own copy of the simulation loop.
"""
import pandas as pd
from engine.config import BASELINE_NO_RISK_CONFIG
from engine.data import load_ohlcv_csv
from engine.features import prepare
from engine.backtest import run_backtest
from engine.metrics import compute_metrics, buy_and_hold_return_pct

config = BASELINE_NO_RISK_CONFIG
df, warnings = load_ohlcv_csv("btc_usdt_1h.csv")
for w in warnings:
    print(f"Data quality warning: {w}")

prepared = prepare(df, config)
result = run_backtest(prepared, config)
metrics = compute_metrics(result, config.starting_balance)
buy_hold_pct = buy_and_hold_return_pct(prepared)

print("=" * 60)
print(f"Backtest period: {prepared['timestamp'].iloc[0]} to {prepared['timestamp'].iloc[-1]}")
print(f"Starting balance: ${config.starting_balance:,.2f}")
print(f"Config: {config.fingerprint()}")
print("=" * 60)
print(f"\n--- STRATEGY (MA {config.short_window}/{config.long_window} crossover, no risk mgmt) ---")
print(f"Final equity:      ${metrics['final_equity']:,.2f}")
print(f"Total return:      {metrics['return_pct']:+.2f}%")
print(f"Number of trades:  {metrics['num_trades']}")
print(f"Win rate:          {metrics['win_rate']:.1f}%")
print(f"Avg win:           {metrics['avg_win_pct']:+.2f}%")
print(f"Avg loss:          {metrics['avg_loss_pct']:+.2f}%")
print(f"Profit factor:     {metrics['profit_factor']:.2f}")
print(f"Max drawdown:      {metrics['max_drawdown_pct']:.2f}%")

print(f"\n--- BUY & HOLD (benchmark) ---")
print(f"Total return:      {buy_hold_pct:+.2f}%")

print(f"\n--- VERDICT ---")
if metrics["return_pct"] > buy_hold_pct:
    print(f"Strategy BEAT buy-and-hold by {metrics['return_pct'] - buy_hold_pct:.2f} percentage points.")
else:
    print(f"Strategy LOST to buy-and-hold by {buy_hold_pct - metrics['return_pct']:.2f} percentage points.")
print("(Past performance on this one window is not evidence of future results.)")

prepared.assign(equity=result.equity_curve).to_csv("backtest_equity_curve.csv", index=False)
pd.DataFrame(result.trades).to_csv("backtest_trades.csv", index=False)
print("\nSaved equity curve to backtest_equity_curve.csv")
print("Saved trade log to backtest_trades.csv")
