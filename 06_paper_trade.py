"""
Step 6: live paper trading -- built on the shared engine.

Runs against live price updates from Kraken's public API instead of a fixed
CSV. No account or API key needed, this only reads public market data and
tracks a simulated ("paper") balance locally in paper_state.json.

Critically, this now calls engine.backtest.step_decision(), the EXACT SAME
function the backtester uses, instead of a second hand-written copy of the
stop-loss/sizing/kill-switch logic. That duplication was a real risk (it
already caused one bug, a feature computed differently in two copies) and
is now structurally impossible: there is only one implementation.

Uses Kraken rather than Binance because Binance blocks requests from cloud/
datacenter IP ranges (including GitHub Actions runners, error 451
"restricted location"), while btc_usdt_1h.csv was fetched from Binance
earlier from a residential connection, which isn't blocked. Kraken's BTC/USD
price tracks Binance's BTC/USDT closely enough that this doesn't meaningfully
affect the strategy, but the live feed and the backtested history do come
from different (very similar) venues.

Usage:
    python 06_paper_trade.py            # run forever, check once per hour
    python 06_paper_trade.py --once      # check one time right now and exit (for testing)
"""
import ccxt
import pandas as pd
import json
import os
import sys
import time
from datetime import datetime, timezone
from importlib import import_module

from engine.config import DEFAULT_CONFIG
from engine.features import prepare, compute_bins
from engine.backtest import step_decision

_market_context_mod = import_module("09_market_context")
get_market_context = _market_context_mod.get_market_context

SYMBOL = "BTC/USD"
TIMEFRAME = "1h"
config = DEFAULT_CONFIG

STATE_FILE = "paper_state.json"
LOG_FILE = "paper_trade_log.csv"
CONTEXT_LOG_FILE = "market_context_log.csv"
LEARNED_FILTERS_FILE = "learned_filters.json"

exchange = ccxt.kraken()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "cash": config.starting_balance, "btc": 0.0, "in_position": False,
        "entry_price": 0.0, "peak_equity": config.starting_balance,
        "trading_halted": False, "last_candle_ts": None,
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def load_learned_filters():
    """Load the self-learning filter table, if 07_analyze_trades.py has produced one.

    Note: the bins used to bucket conditions were fitted on historical CSV
    data, not live data, so this is an approximation -- acceptable since the
    filter has zero reliable combinations right now anyway (see repo status).
    """
    if not os.path.exists(LEARNED_FILTERS_FILE):
        return None, None
    with open(LEARNED_FILTERS_FILE) as f:
        filters = json.load(f)
    try:
        from engine.data import load_ohlcv_csv
        hist_df, _ = load_ohlcv_csv("btc_usdt_1h.csv")
        hist_prepared = prepare(hist_df, config)
        bins = compute_bins(hist_prepared)
    except Exception:
        return None, None
    return filters, bins


def log_event(event):
    header_needed = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a") as f:
        if header_needed:
            f.write("timestamp,event,price,cash,btc,equity,note\n")
        f.write(",".join(str(x) for x in event) + "\n")


def fetch_candles():
    limit = config.long_window + 10
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def run_once(state, learned_filters, bins):
    raw = fetch_candles()
    df = prepare(raw, config)

    latest = df.iloc[-1]
    latest_ts = str(latest["timestamp"])

    if state["last_candle_ts"] == latest_ts:
        print(f"[{datetime.now(timezone.utc).isoformat()}] No new candle yet (last processed: {latest_ts}). Skipping.")
        return state

    try:
        context = get_market_context()
        news_label = context["news"]["label"]
        news_score = context["news"]["avg_compound"]
        fear_greed = context["fear_greed"]["value"]
        fear_greed_label = context["fear_greed"]["label"]
    except Exception as e:
        print(f"Warning: could not fetch market context: {e}")
        news_label, news_score, fear_greed, fear_greed_label = "unknown", 0.0, None, "unknown"

    header_needed = not os.path.exists(CONTEXT_LOG_FILE)
    with open(CONTEXT_LOG_FILE, "a") as f:
        if header_needed:
            f.write("timestamp,news_label,news_score,fear_greed,fear_greed_label\n")
        f.write(f"{latest_ts},{news_label},{news_score},{fear_greed},{fear_greed_label}\n")
    print(f"Market context: news={news_label} ({news_score:+.3f}), fear_greed={fear_greed} ({fear_greed_label})")

    state, note = step_decision(state, latest, config, learned_filters=learned_filters, bins=bins)
    price = latest["close"]
    equity_now = state["cash"] + state["btc"] * price
    print(f"[{latest_ts}] price={price:.2f} equity=${equity_now:.2f} "
          f"in_position={state['in_position']} halted={state['trading_halted']} | {note}")

    note_with_context = f"{note} | news={news_label} fear_greed={fear_greed}"
    log_event([latest_ts, "tick", price, state["cash"], state["btc"], equity_now, note_with_context])

    state["last_candle_ts"] = latest_ts
    save_state(state)
    return state


def seconds_until_next_hour():
    now = datetime.now(timezone.utc)
    return 3600 - (now.minute * 60 + now.second)


if __name__ == "__main__":
    run_forever = "--once" not in sys.argv
    state = load_state()
    learned_filters, bins = load_learned_filters()
    print(f"Starting paper trader. Current state: {state}")
    print(f"Learned filters loaded: {len(learned_filters) if learned_filters else 0} combinations")

    if not run_forever:
        run_once(state, learned_filters, bins)
    else:
        while True:
            state = run_once(state, learned_filters, bins)
            wait = seconds_until_next_hour() + 5  # small buffer past the hour
            print(f"Sleeping {wait}s until next candle check...\n")
            time.sleep(wait)
