"""
Step 12: live paper experiments.

Runs the research candidates listed in experiments/config.json side by side,
each with its own $1,000 paper portfolio, alongside (not instead of) the
main bot in 06_paper_trade.py. Same execution rules as the walk-forward
research (see engine/experiment.py). Runs in the same GitHub workflow.

One failing experiment doesn't stop the others; the script exits non-zero
at the end if any failed, and its run-log step shows the error.

Usage: python 12_experiments.py
"""
import csv
import json
import os
import sys
from datetime import datetime, timezone

import ccxt
import pandas as pd

from engine.data import validate_ohlcv
from engine.experiment import new_state, step
from engine.runlog import RunLogger
from engine.strategies import STRATEGIES

CONFIG_FILE = os.path.join("experiments", "config.json")
SYMBOL = "BTC/USD"


def fetch():
    """Kraken's last 720 hourly candles: the closed ones, plus the open of the hour now forming."""
    rows = ccxt.kraken().fetch_ohlcv(SYMBOL, timeframe="1h", limit=720)
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    closed = df[df["timestamp"] + pd.Timedelta(hours=1) <= now].reset_index(drop=True)
    forming = df[df["timestamp"] + pd.Timedelta(hours=1) > now]
    if forming.empty:
        raise RuntimeError("Kraken returned no candle for the current hour")
    closed, _ = validate_ohlcv(closed, source="Kraken live fetch")
    return closed, float(forming["open"].iloc[-1])


def paths(exp_id):
    base = os.path.join("experiments", exp_id)
    return base, os.path.join(base, "state.json"), os.path.join(base, "trades.csv")


EXPERIMENT_STATE_FIELDS = {
    "cash": (int, float), "btc": (int, float), "in_position": bool,
    "entry_price": (int, float), "stopped": bool, "peak_equity": (int, float),
    "halted": bool, "starting_cash": (int, float), "trades": int,
}


class CorruptStateError(Exception):
    """An experiment's state.json exists but isn't trustworthy. Never treated
    the same as a brand-new experiment -- that would quietly erase its real
    trade history back to $1,000 because of a read error."""


def validate_experiment_state(state):
    if not isinstance(state, dict):
        raise CorruptStateError(f"expected a JSON object, got {type(state).__name__}")
    for field, types in EXPERIMENT_STATE_FIELDS.items():
        if field not in state:
            raise CorruptStateError(f"missing required field '{field}'")
        if not isinstance(state[field], types) or isinstance(state[field], bool) != (types is bool):
            raise CorruptStateError(f"field '{field}' is {type(state[field]).__name__}, expected {types}")
    if state["cash"] < 0 or state["btc"] < 0:
        raise CorruptStateError("cash or btc holding is negative")
    if state["in_position"] and state["btc"] <= 0:
        raise CorruptStateError("in_position is true but btc holding is zero")
    return state


def load_experiment_state(state_path, forming_open):
    """Like paper_trade's load_state: missing file -> brand new experiment,
    file that exists but fails to parse or validate -> CorruptStateError,
    never silently treated as a fresh start."""
    if not os.path.exists(state_path):
        return new_state(start_price=forming_open, started_at=datetime.now(timezone.utc).isoformat())
    with open(state_path) as f:
        try:
            state = json.load(f)
        except json.JSONDecodeError as e:
            raise CorruptStateError(f"{state_path} is not valid JSON: {e}") from e
    return validate_experiment_state(state)


def main():
    with open(CONFIG_FILE) as f:
        experiments = json.load(f)["experiments"]

    closed, forming_open = fetch()
    latest_closed = str(closed["timestamp"].iloc[-1])

    log = RunLogger("experiments", [(e["id"], e["employee"], e["description"]) for e in experiments])
    states = {}
    corrupt = set()
    for exp in experiments:
        _, state_path, _ = paths(exp["id"])
        try:
            states[exp["id"]] = load_experiment_state(state_path, forming_open)
        except CorruptStateError as e:
            corrupt.add(exp["id"])
            rec = log._by_id[exp["id"]]
            rec["status"] = "error"
            rec["error"] = f"{type(e).__name__}: {e}"
            print(f"{exp['id']}: refusing to trade on corrupt state -- {e}")

    live = [e for e in experiments if e["id"] not in corrupt]
    if corrupt and not live:
        log.finish("error", f"All experiment states failed validation: {sorted(corrupt)}")
        log.write()
        return 1

    if live and all(states[e["id"]]["last_candle_ts"] == latest_closed for e in live):
        if not corrupt:
            print(f"No new hourly candle since {latest_closed}, nothing to do.")
            return 0  # nothing written, so no commit
        # at least one experiment is corrupt and needs reporting even though
        # the healthy ones have nothing new to do
        log.skip_remaining(f"No new candle since {latest_closed}; skipped experiments are unaffected")
        log.finish("error", f"{len(corrupt)} experiment(s) have corrupt state: {sorted(corrupt)}")
        log.write()
        return 1

    failures = len(corrupt)
    try:
        for exp in live:
            state = states[exp["id"]]
            try:
                with log.step(exp["id"]) as s:
                    strat = STRATEGIES[exp["strategy"]]
                    target = strat["fn"](closed, **exp["params"])
                    state, events, n_new = step(state, closed, target, forming_open, exp.get("stop_loss"))

                    base, state_path, trades_path = paths(exp["id"])
                    os.makedirs(base, exist_ok=True)
                    for ev in events:
                        new_file = not os.path.exists(trades_path)
                        with open(trades_path, "a", newline="") as f:
                            w = csv.writer(f)
                            if new_file:
                                w.writerow(["time", "action", "reason", "price", "pnl_pct", "candle"])
                            w.writerow([datetime.now(timezone.utc).isoformat(), ev["action"], ev["reason"],
                                        ev.get("price"), ev.get("pnl_pct"), ev.get("candle")])
                    with open(state_path, "w") as f:
                        json.dump(state, f, indent=2)

                    equity = state["cash"] + state["btc"] * forming_open
                    bh = (forming_open / state["start_price"] - 1) * 100 if state["start_price"] else None
                    s.output(
                        strategy=strat["label"], settings=exp["params"],
                        stop_loss=f"{exp['stop_loss'] * 100:.0f}%" if exp.get("stop_loss") else "none",
                        target_now="hold BTC" if target.iloc[-1] == 1 else "hold cash",
                        action=", ".join(f"{e['action']} ({e['reason']})" for e in events) or "no change",
                        price=round(forming_open, 2), equity=round(equity, 2),
                        return_since_start_pct=round((equity / state["starting_cash"] - 1) * 100, 2),
                        btc_since_start_pct=round(bh, 2) if bh is not None else None,
                        in_position=state["in_position"], completed_trades=state["trades"],
                        new_candles_checked=n_new, halted=state["halted"], started=state["started_at"],
                        research_result=exp["research_note"],
                    )
                    print(f"{exp['id']}: {s.record['outputs']['action']} | equity ${equity:.2f}")
            except Exception as e:
                failures += 1
                print(f"{exp['id']} failed: {e}")
        log.finish("done" if not failures else "error",
                   f"{len(experiments) - failures}/{len(experiments)} experiments updated at the {latest_closed} candle")
    finally:
        log.write()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
