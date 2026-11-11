"""
Step 12: live paper experiments.

Runs the research candidates listed in experiments/config.json side by side,
each with its own $1,000 paper portfolio, alongside (not instead of) the
main bot in 06_paper_trade.py. Same execution rules as the walk-forward
research (see engine/experiment.py). Runs in the same GitHub workflow.

An experiment may set "symbol" (default BTC/USD), "timeframe" ("1h" default,
or "1d") and "kill_switch" (default 0.20, null for none). It only trades when
its own timeframe has a new closed candle, so a daily experiment acts once a
day even though this script runs every 15 minutes.

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
from engine.experiment import KILL_SWITCH, new_state, step
from engine.runlog import RunLogger
from engine.strategies import STRATEGIES

CONFIG_FILE = os.path.join("experiments", "config.json")
TIMEFRAMES = {"1h": pd.Timedelta(hours=1), "1d": pd.Timedelta(days=1)}
DEFAULT_SYMBOL, DEFAULT_TIMEFRAME = "BTC/USD", "1h"


def feed_key(exp):
    """Which candles an experiment trades on, as (symbol, timeframe)."""
    return exp.get("symbol", DEFAULT_SYMBOL), exp.get("timeframe", DEFAULT_TIMEFRAME)


def fetch(symbol=DEFAULT_SYMBOL, timeframe=DEFAULT_TIMEFRAME):
    """Kraken's last 720 candles: the closed ones, plus the open of the candle now forming."""
    length = TIMEFRAMES[timeframe]
    rows = ccxt.kraken().fetch_ohlcv(symbol, timeframe=timeframe, limit=720)
    df = pd.DataFrame(rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    closed = df[df["timestamp"] + length <= now].reset_index(drop=True)
    forming = df[df["timestamp"] + length > now]
    if forming.empty:
        raise RuntimeError(f"Kraken returned no {timeframe} candle for the current period")
    closed, _ = validate_ohlcv(closed, timeframe_hours=length.total_seconds() / 3600,
                               source=f"Kraken live fetch {symbol} {timeframe}")
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

    log = RunLogger("experiments", [(e["id"], e["employee"], e["description"]) for e in experiments])

    def mark_failed(exp_id, message):
        rec = log._by_id[exp_id]
        rec["status"] = "error"
        rec["error"] = message

    # one fetch per (symbol, timeframe), shared by every experiment on that feed
    feeds, feed_errors = {}, {}
    for key in dict.fromkeys(feed_key(e) for e in experiments):
        try:
            feeds[key] = fetch(*key)
        except Exception as e:
            feed_errors[key] = e
            print(f"{key[0]} {key[1]}: couldn't fetch candles -- {e}")

    states = {}
    failed = set()
    for exp in experiments:
        key = feed_key(exp)
        if key in feed_errors:
            failed.add(exp["id"])
            mark_failed(exp["id"], f"No prices: {type(feed_errors[key]).__name__}: {feed_errors[key]}")
            continue
        _, forming_open = feeds[key]
        _, state_path, _ = paths(exp["id"])
        try:
            states[exp["id"]] = load_experiment_state(state_path, forming_open)
        except CorruptStateError as e:
            failed.add(exp["id"])
            mark_failed(exp["id"], f"{type(e).__name__}: {e}")
            print(f"{exp['id']}: refusing to trade on corrupt state -- {e}")

    live = [e for e in experiments if e["id"] not in failed]
    if failed and not live:
        log.finish("error", f"Every experiment failed before trading (no prices or bad state): {sorted(failed)}")
        log.write()
        return 1

    def latest_closed(exp):
        closed, _ = feeds[feed_key(exp)]
        return str(closed["timestamp"].iloc[-1])

    def is_due(exp):
        return states[exp["id"]]["last_candle_ts"] != latest_closed(exp)

    if live and not any(is_due(e) for e in live):
        if not failed:
            print("No new candle for any experiment, nothing to do.")
            return 0  # nothing written, so no commit
        # something failed and needs reporting even though the healthy ones have nothing new to do
        log.skip_remaining("No new candle yet; the healthy experiments are unaffected")
        log.finish("error", f"{len(failed)} experiment(s) failed: {sorted(failed)}")
        log.write()
        return 1

    failures = len(failed)
    updated = 0
    try:
        for exp in live:
            state = states[exp["id"]]
            closed, forming_open = feeds[feed_key(exp)]
            symbol, timeframe = feed_key(exp)
            due = is_due(exp)
            try:
                with log.step(exp["id"]) as s:
                    strat = STRATEGIES[exp["strategy"]]
                    target = strat["fn"](closed, **exp["params"])
                    events, n_new = [], 0
                    if due:
                        state, events, n_new = step(state, closed, target, forming_open, exp.get("stop_loss"),
                                                    kill_switch=exp.get("kill_switch", KILL_SWITCH))
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

                    coin = symbol.split("/")[0]
                    equity = state["cash"] + state["btc"] * forming_open
                    hold = (forming_open / state["start_price"] - 1) * 100 if state["start_price"] else None
                    action = ", ".join(f"{e['action']} ({e['reason']})" for e in events) or \
                        ("no change" if due else f"no new {timeframe} candle yet, nothing to do")
                    s.output(
                        strategy=strat["label"], settings=exp["params"], asset=symbol, timeframe=timeframe,
                        stop_loss=f"{exp['stop_loss'] * 100:.0f}%" if exp.get("stop_loss") else "none",
                        target_now=f"hold {coin}" if target.iloc[-1] == 1 else "hold cash",
                        action=action,
                        price=round(forming_open, 2), equity=round(equity, 2),
                        return_since_start_pct=round((equity / state["starting_cash"] - 1) * 100, 2),
                        hold_since_start_pct=round(hold, 2) if hold is not None else None,
                        btc_since_start_pct=round(hold, 2) if hold is not None and symbol == "BTC/USD" else None,
                        in_position=state["in_position"], completed_trades=state["trades"],
                        new_candles_checked=n_new, halted=state["halted"], started=state["started_at"],
                        research_result=exp["research_note"],
                    )
                    print(f"{exp['id']}: {action} | equity ${equity:.2f}")
                updated += due
            except Exception as e:
                failures += 1
                print(f"{exp['id']} failed: {e}")
        log.finish("done" if not failures else "error",
                   f"{updated}/{len(experiments)} experiments traded on a new candle"
                   + (f", {failures} failed" if failures else ""))
    finally:
        log.write()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
