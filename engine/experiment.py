"""
Live paper-trading for research candidates, matching engine/research.py.

Rules, the same as the walk-forward simulator:
  - the strategy's target at the latest CLOSED candle decides the position
  - fills happen at the open of the candle now forming (that is the "next
    candle's open" the research used), paying COST_PER_SIDE
  - the stop-loss acts like a resting exchange order: it is checked against
    every closed candle since the last run, so skipped GitHub runs don't
    make it miss. It fills at the stop price, or at the open if the candle
    gapped below it.
  - after a stop, no re-entry until the target has gone back to 0
  - a 20% drop from the experiment's peak halts it (same kill switch idea)

Signal entries/exits are never backdated: if runs were skipped, they happen
at the current price.
"""
import pandas as pd

from engine.research import COST_PER_SIDE

KILL_SWITCH = 0.20


def new_state(starting_cash=1000.0, start_price=None, started_at=None):
    return {"cash": starting_cash, "btc": 0.0, "in_position": False, "entry_price": 0.0,
            "stopped": False, "peak_equity": starting_cash, "halted": False,
            "last_candle_ts": None, "start_price": start_price, "started_at": started_at,
            "starting_cash": starting_cash, "trades": 0}


def step(state, closed, target, forming_open, stop_loss=None, cost=COST_PER_SIDE):
    """Advance one experiment. `closed` = closed candles, `target` = strategy
    target aligned with `closed`, `forming_open` = open of the current hour.
    Returns (state, events) where events is a list of dicts describing trades."""
    events = []
    last = pd.Timestamp(state["last_candle_ts"]) if state["last_candle_ts"] else None
    new_mask = closed["timestamp"] > last if last is not None else closed.index == closed.index[-1]
    new_idx = closed.index[new_mask]

    def sell(price, reason, when):
        proceeds = state["btc"] * price * (1 - cost)
        pnl = (proceeds / state["cost_basis"] - 1) * 100
        events.append({"action": "SELL", "reason": reason, "price": round(price, 2),
                       "pnl_pct": round(pnl, 2), "candle": str(when)})
        state.update(cash=proceeds, btc=0.0, in_position=False, entry_price=0.0)
        state["trades"] += 1

    # resting stop-loss over every new closed candle, in order
    for i in new_idx:
        row = closed.loc[i]
        if state["stopped"] and target.loc[i] == 0:
            state["stopped"] = False
        if state["in_position"] and stop_loss is not None:
            stop_price = state["entry_price"] * (1 - stop_loss)
            if row["low"] <= stop_price:
                sell(min(row["open"], stop_price), "stop_loss", row["timestamp"])
                state["stopped"] = True

    equity = state["cash"] + state["btc"] * forming_open
    state["peak_equity"] = max(state["peak_equity"], equity)
    if not state["halted"] and (equity - state["peak_equity"]) / state["peak_equity"] <= -KILL_SWITCH:
        state["halted"] = True
        events.append({"action": "HALT", "reason": "20% below peak equity"})

    want = int(target.iloc[-1]) if not state["stopped"] else 0
    if state["halted"]:
        want = 0
    if want == 1 and not state["in_position"]:
        state["cost_basis"] = state["cash"]
        state["btc"] = state["cash"] * (1 - cost) / forming_open
        state.update(cash=0.0, in_position=True, entry_price=forming_open)
        events.append({"action": "BUY", "reason": "signal", "price": round(forming_open, 2)})
    elif want == 0 and state["in_position"]:
        sell(forming_open, "halt" if state["halted"] else "signal", "now")

    state["last_candle_ts"] = str(closed["timestamp"].iloc[-1])
    return state, events, len(new_idx)
