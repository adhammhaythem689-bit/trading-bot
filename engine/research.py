"""
Research simulator + walk-forward validation for the candidate strategies.

Execution model (stricter than the original engine/backtest.py):
  - a strategy's target at candle t is filled at candle t+1's OPEN
  - every buy and sell pays COST_PER_SIDE (exchange fee + slippage)
  - optional stop-loss: fills at the stop price, or at the open if the
    candle opened below it (a gap). Hourly candles can't show the exact
    path inside the hour, so this is an approximation, stated as such.
  - after a stop-loss, no re-entry until the strategy's target goes to 0
    and back to 1 (otherwise it would buy straight back in)
  - long-only, 100% of equity when in a position, no leverage

Walk-forward: settings are chosen on the TRAIN window only (best Sharpe),
then run on the next TEST window the selection never saw. Test windows are
stitched together; that stitched result is the only number reported as
"out-of-sample".
"""
import math
import numpy as np
import pandas as pd

COST_PER_SIDE = 0.0015  # 0.10% fee + 0.05% slippage
HOURS_PER_YEAR = 24 * 365


def simulate(df, target, cost=COST_PER_SIDE, stop_loss=None, start_equity=1000.0):
    o, l, c = df["open"].to_numpy(), df["low"].to_numpy(), df["close"].to_numpy()
    ts = df["timestamp"].to_numpy()
    wanted = target.shift(1).fillna(0).to_numpy()  # decided at the previous close

    cash, units, entry_price, entry_i = start_equity, 0.0, 0.0, None
    stopped = False
    equity, trades = np.empty(len(df)), []
    in_pos_count = 0

    def close_trade(i, price, reason):
        nonlocal cash, units
        cash = units * price * (1 - cost)
        gross_in = trades_open["cash_in"]
        trades.append({"entry_time": ts[entry_i], "entry_price": entry_price, "exit_time": ts[i],
                       "exit_price": price, "pnl_pct": (cash / gross_in - 1) * 100, "reason": reason,
                       "hours": i - entry_i})
        units = 0.0

    trades_open = {}
    for i in range(len(df)):
        want = wanted[i]
        if stopped and want == 0:
            stopped = False
        if stopped:
            want = 0

        if want == 1 and units == 0:
            trades_open = {"cash_in": cash}
            units = cash * (1 - cost) / o[i]
            entry_price, entry_i, cash = o[i], i, 0.0
        elif want == 0 and units > 0:
            close_trade(i, o[i], "signal")

        if units > 0 and stop_loss is not None:
            stop_price = entry_price * (1 - stop_loss)
            if l[i] <= stop_price:
                close_trade(i, min(o[i], stop_price), "stop_loss")
                stopped = True

        if units > 0:
            in_pos_count += 1
        equity[i] = cash + units * c[i]

    open_trade = None
    if units > 0:
        open_trade = {"entry_time": ts[entry_i], "entry_price": entry_price,
                      "unrealized_pct": (equity[-1] / trades_open["cash_in"] - 1) * 100}
    return {"equity": equity, "trades": trades, "open_trade": open_trade,
            "exposure": in_pos_count / max(1, len(df))}


def metrics(equity, trades, start_equity=1000.0):
    equity = np.asarray(equity, dtype=float)
    if len(equity) == 0:
        return {}
    rets = np.diff(np.concatenate([[start_equity], equity])) / np.concatenate([[start_equity], equity[:-1]])
    peak = np.maximum.accumulate(np.concatenate([[start_equity], equity]))
    dd = (np.concatenate([[start_equity], equity]) - peak) / peak
    pnl = np.array([t["pnl_pct"] for t in trades]) if trades else np.array([])
    wins, losses = pnl[pnl > 0], pnl[pnl <= 0]
    sd = rets.std()
    return {
        "return_pct": (equity[-1] / start_equity - 1) * 100,
        "max_drawdown_pct": dd.min() * 100,
        "trades": int(len(pnl)),
        "win_rate": float((pnl > 0).mean() * 100) if len(pnl) else None,
        "avg_win_pct": float(wins.mean()) if len(wins) else None,
        "avg_loss_pct": float(losses.mean()) if len(losses) else None,
        "profit_factor": float(wins.sum() / -losses.sum()) if len(losses) and losses.sum() < 0 else None,
        "sharpe": float(rets.mean() / sd * math.sqrt(HOURS_PER_YEAR)) if sd > 0 else 0.0,
    }


def buy_and_hold(df, cost=COST_PER_SIDE, start_equity=1000.0):
    units = start_equity * (1 - cost) / df["open"].iloc[0]
    equity = units * df["close"].to_numpy()
    equity[-1] *= (1 - cost)  # selling at the end, so both strategies pay the same exit cost
    return equity


def walk_forward(df, strategy, train_hours=270 * 24, test_hours=90 * 24, cost=COST_PER_SIDE, stop_loss=None):
    fn, grid = strategy["fn"], strategy["grid"]
    folds, stitched, all_trades = [], [], []
    equity_start = 1000.0
    start = train_hours
    while start + test_hours <= len(df):
        window = df.iloc[start - train_hours:start + test_hours].reset_index(drop=True)
        train = window.iloc[:train_hours].reset_index(drop=True)
        test = window.iloc[train_hours:].reset_index(drop=True)

        best, best_score = None, -np.inf
        for params in grid:
            target = fn(window, **params)
            res = simulate(train, target.iloc[:train_hours].reset_index(drop=True), cost, stop_loss)
            score = metrics(res["equity"], res["trades"])["sharpe"]
            if score > best_score:
                best, best_score = params, score

        target = fn(window, **best).iloc[train_hours:].reset_index(drop=True)
        res = simulate(test, target, cost, stop_loss, start_equity=equity_start)
        bh = buy_and_hold(test, cost, start_equity=1000.0)
        m = metrics(res["equity"], res["trades"], start_equity=equity_start)
        folds.append({
            "test_period": f"{test['timestamp'].iloc[0]} to {test['timestamp'].iloc[-1]}",
            "chosen_params": best, "train_sharpe": round(best_score, 2),
            "return_pct": round(m["return_pct"], 2), "trades": m["trades"],
            "buy_hold_pct": round((bh[-1] / 1000.0 - 1) * 100, 2),
        })
        stitched.append(res["equity"])
        all_trades += res["trades"]
        equity_start = res["equity"][-1]
        start += test_hours

    equity = np.concatenate(stitched) if stitched else np.array([])
    return {"folds": folds, "equity": equity, "trades": all_trades,
            "metrics": metrics(equity, all_trades) if len(equity) else {}}
