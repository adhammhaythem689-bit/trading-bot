"""
Step 5: same MA crossover strategy, now with risk management (position
sizing, stop-loss, kill switch) -- built on the shared engine.
"""
import pandas as pd
from engine.config import DEFAULT_CONFIG
from engine.data import load_ohlcv_csv
from engine.features import prepare
from engine.backtest import run_backtest
from engine.metrics import compute_metrics, buy_and_hold_return_pct

config = DEFAULT_CONFIG
df, warnings = load_ohlcv_csv("btc_usdt_1h.csv")
for w in warnings:
    print(f"Data quality warning: {w}")

prepared = prepare(df, config)
result = run_backtest(prepared, config)
metrics = compute_metrics(result, config.starting_balance)
buy_hold_pct = buy_and_hold_return_pct(prepared)

print("=" * 60)
print("STRATEGY WITH RISK MANAGEMENT")
print(f"Config: {config.fingerprint()}")
print("=" * 60)
print(f"Risk per trade:     {config.risk_per_trade*100:.1f}% of equity")
print(f"Stop-loss:          {config.stop_loss_pct*100:.1f}% below entry")
print(f"Max-drawdown kill:  {config.max_drawdown_kill*100:.1f}%")
print(f"\nFinal equity:       ${metrics['final_equity']:,.2f}")
print(f"Total return:       {metrics['return_pct']:+.2f}%")
print(f"Number of trades:   {metrics['num_trades']}")
print(f"Win rate:           {metrics['win_rate']:.1f}%")
print(f"Profit factor:      {metrics['profit_factor']:.2f}")
print(f"Max drawdown:       {metrics['max_drawdown_pct']:.2f}%")
print(f"Trading halted?:    {metrics['trading_halted']}")
if result.halted_at:
    print(f"Halted at:          {result.halted_at}")

print(f"\nBuy & hold return:  {buy_hold_pct:+.2f}%")

prepared.assign(equity=result.equity_curve).to_csv("backtest_with_risk_equity_curve.csv", index=False)
pd.DataFrame(result.trades).to_csv("backtest_with_risk_trades.csv", index=False)
