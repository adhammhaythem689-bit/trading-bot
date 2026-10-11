"""
Step 6: live paper trading.

Runs the exact same MA-crossover + risk-management logic from step 5, but now
against live price updates from Kraken's public API instead of a fixed CSV.
No account or API key needed, this only reads public market data and tracks
a simulated ("paper") balance locally in paper_state.json.

Uses Kraken rather than Binance here specifically because Binance blocks
requests from cloud/datacenter IP ranges (including GitHub Actions runners,
error 451 "restricted location"), while our historical data in btc_usdt_1h.csv
was fetched from Binance earlier from a residential connection, which isn't
blocked. Kraken's BTC/USD price tracks Binance's BTC/USDT closely enough that
this doesn't meaningfully affect the strategy, but it's worth knowing the
live feed and the backtested history come from different (very similar)
venues.

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

_market_context_mod = import_module("09_market_context")
get_market_context = _market_context_mod.get_market_context

SYMBOL = "BTC/USD"
TIMEFRAME = "1h"
SHORT_WINDOW = 24
LONG_WINDOW = 72
STARTING_BALANCE = 1000.0
FEE_RATE = 0.001
RISK_PER_TRADE = 0.02
STOP_LOSS_PCT = 0.03
MAX_DRAWDOWN_KILL = 0.20

STATE_FILE = "paper_state.json"
LOG_FILE = "paper_trade_log.csv"
CONTEXT_LOG_FILE = "market_context_log.csv"

exchange = ccxt.kraken()


def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE) as f:
            return json.load(f)
    return {
        "cash": STARTING_BALANCE, "btc": 0.0, "in_position": False,
        "entry_price": 0.0, "peak_equity": STARTING_BALANCE,
        "trading_halted": False, "last_candle_ts": None,
    }


def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def log_event(event):
    header_needed = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a") as f:
        if header_needed:
            f.write("timestamp,event,price,cash,btc,equity,note\n")
        f.write(",".join(str(x) for x in event) + "\n")


def fetch_candles():
    limit = LONG_WINDOW + 10
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def run_once(state):
    df = fetch_candles()
    df["short_ma"] = df["close"].rolling(window=SHORT_WINDOW).mean()
    df["long_ma"] = df["close"].rolling(window=LONG_WINDOW).mean()
    df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)
    df["position_change"] = df["signal"].diff()
    df = df.dropna(subset=["short_ma", "long_ma"]).reset_index(drop=True)

    latest = df.iloc[-1]
    latest_ts = str(latest["timestamp"])

    if state["last_candle_ts"] == latest_ts:
        print(f"[{datetime.now(timezone.utc).isoformat()}] No new candle yet (last processed: {latest_ts}). Skipping.")
        return state

    price = latest["close"]

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

    cash, btc = state["cash"], state["btc"]
    in_position = state["in_position"]
    entry_price = state["entry_price"]
    peak_equity = state["peak_equity"]
    trading_halted = state["trading_halted"]

    equity_now = cash + btc * price
    peak_equity = max(peak_equity, equity_now)
    current_drawdown = (equity_now - peak_equity) / peak_equity

    if not trading_halted and current_drawdown <= -MAX_DRAWDOWN_KILL:
        trading_halted = True
        print(f"!!! KILL SWITCH TRIGGERED: drawdown {current_drawdown*100:.2f}% exceeds limit. Trading halted. !!!")
        log_event([latest_ts, "KILL_SWITCH", price, cash, btc, equity_now, "max drawdown exceeded"])

    note = "hold"

    if in_position and price <= entry_price * (1 - STOP_LOSS_PCT):
        cash += (btc * price) * (1 - FEE_RATE)
        pnl_pct = (price - entry_price) / entry_price * 100
        btc = 0.0
        in_position = False
        note = f"STOP-LOSS exit, pnl {pnl_pct:+.2f}%"
        print(note)

    elif not trading_halted and latest["position_change"] == 1 and not in_position:
        trade_capital = min(cash * RISK_PER_TRADE / STOP_LOSS_PCT, cash)
        btc = (trade_capital * (1 - FEE_RATE)) / price
        cash -= trade_capital
        entry_price = price
        in_position = True
        note = f"BUY at {price:.2f}"
        print(note)

    elif latest["position_change"] == -1 and in_position:
        cash += (btc * price) * (1 - FEE_RATE)
        pnl_pct = (price - entry_price) / entry_price * 100
        btc = 0.0
        in_position = False
        note = f"SELL at {price:.2f}, pnl {pnl_pct:+.2f}%"
        print(note)

    equity_now = cash + btc * price
    print(f"[{latest_ts}] price={price:.2f} equity=${equity_now:.2f} in_position={in_position} halted={trading_halted}")
    note_with_context = f"{note} | news={news_label} fear_greed={fear_greed}"
    log_event([latest_ts, "tick", price, cash, btc, equity_now, note_with_context])

    state.update({
        "cash": cash, "btc": btc, "in_position": in_position,
        "entry_price": entry_price, "peak_equity": peak_equity,
        "trading_halted": trading_halted, "last_candle_ts": latest_ts,
    })
    save_state(state)
    return state


def seconds_until_next_hour():
    now = datetime.now(timezone.utc)
    return 3600 - (now.minute * 60 + now.second)


if __name__ == "__main__":
    run_forever = "--once" not in sys.argv
    state = load_state()
    print(f"Starting paper trader. Current state: {state}")

    if not run_forever:
        run_once(state)
    else:
        while True:
            state = run_once(state)
            wait = seconds_until_next_hour() + 5  # small buffer past the hour
            print(f"Sleeping {wait}s until next candle check...\n")
            time.sleep(wait)
