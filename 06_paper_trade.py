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
import csv
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
from engine.data import validate_ohlcv
from engine.runlog import RunLogger

_market_context_mod = import_module("09_market_context")
get_news_sentiment = _market_context_mod.get_news_sentiment
get_fear_greed = _market_context_mod.get_fear_greed

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


def append_csv(path, header, row):
    """Append one row with proper quoting, notes like "SELL at 83000, pnl +1%" contain commas."""
    header_needed = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        writer = csv.writer(f)
        if header_needed:
            writer.writerow(header)
        writer.writerow(row)


def fetch_candles():
    limit = config.long_window + 11
    ohlcv = exchange.fetch_ohlcv(SYMBOL, timeframe=TIMEFRAME, limit=limit)
    df = pd.DataFrame(ohlcv, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    # Kraken includes the candle that's still forming. Its "close" is just the
    # latest price, so decide only on fully closed candles, like the backtests do.
    now = pd.Timestamp.now(tz="UTC").tz_localize(None)
    return df[df["timestamp"] + pd.Timedelta(hours=1) <= now].reset_index(drop=True)


HOURLY_STEPS = [
    ("fetch_prices", "price_fetcher", "Pull the latest hourly BTC/USD candles from Kraken"),
    ("check_data", "data_checker", "Check the candles for gaps, duplicates and bad prices"),
    ("compute_indicators", "indicator_analyst", "Compute the 24h and 72h moving averages"),
    ("check_signal", "signal_watcher", "Check whether the averages crossed this hour"),
    ("check_risk", "risk_officer", "Check drawdown against the kill switch and the stop-loss"),
    ("read_news", "news_reader", "Read crypto headlines and score their sentiment"),
    ("read_mood", "mood_analyst", "Read the Crypto Fear & Greed index"),
    ("decide_trade", "trader", "Decide buy / sell / hold and update the paper portfolio"),
    ("save_state", "record_keeper", "Save the portfolio and logs for GitHub to commit"),
]


def run_once(state, learned_filters, bins):
    log = RunLogger("hourly", HOURLY_STEPS)
    try:
        state = _run_steps(log, state, learned_filters, bins)
    finally:
        log.write()
    return state


def _run_steps(log, state, learned_filters, bins):
    with log.step("fetch_prices") as s:
        raw = fetch_candles()
        s.output(source=f"Kraken {SYMBOL}", closed_candles=len(raw),
                 latest_closed_candle=raw["timestamp"].iloc[-1], latest_close=raw["close"].iloc[-1],
                 note="The hour still in progress is left out until it closes")

    with log.step("check_data") as s:
        raw, warnings = validate_ohlcv(raw, source="Kraken live fetch")
        s.output(rows_checked=len(raw), warnings=[f"{w.kind}: {w.detail}" for w in warnings],
                 verdict="clean" if not warnings else "warnings found")

    with log.step("compute_indicators") as s:
        df = prepare(raw, config)
        latest = df.iloc[-1]
        latest_ts = str(latest["timestamp"])
        gap_pct = (latest["short_ma"] - latest["long_ma"]) / latest["long_ma"] * 100
        s.output(candle=latest_ts, close=latest["close"],
                 short_ma=round(latest["short_ma"], 2), long_ma=round(latest["long_ma"], 2),
                 gap_pct=round(gap_pct, 3),
                 windows=f"{config.short_window}h / {config.long_window}h")

    if state["last_candle_ts"] == latest_ts:
        reason = f"No new hourly candle since the last run ({latest_ts}), nothing to decide"
        print(f"[{datetime.now(timezone.utc).isoformat()}] {reason}. Skipping.")
        log.skip_remaining(reason)
        log.finish("skipped", reason)
        return state

    with log.step("check_signal") as s:
        change = latest["position_change"]
        crossover = "bullish (24h crossed above 72h)" if change == 1 else \
                    "bearish (24h crossed below 72h)" if change == -1 else "none"
        trend_up = latest["signal"] == 1
        if change == 1:
            meaning = "Buy signal: entering a position unless risk rules block it"
        elif change == -1:
            meaning = "Sell signal: exiting the position if one is open"
        elif trend_up and not state["in_position"]:
            meaning = "Trend is up, but the bot only buys in the hour the cross happens, so it waits"
        elif trend_up:
            meaning = "Trend still up, holding the open position"
        else:
            meaning = "Trend is down, staying out of the market"
        s.output(crossover=crossover, trend="24h above 72h" if trend_up else "24h below 72h",
                 what_it_means=meaning)

    with log.step("check_risk") as s:
        price = latest["close"]
        equity = state["cash"] + state["btc"] * price
        peak = max(state["peak_equity"], equity)
        drawdown_pct = (equity - peak) / peak * 100
        risk = {"equity": round(equity, 2), "peak_equity": round(peak, 2),
                "drawdown_pct": round(drawdown_pct, 2),
                "kill_switch_at_pct": -config.max_drawdown_kill * 100,
                "trading_halted": state["trading_halted"]}
        if state["in_position"]:
            stop_price = state["entry_price"] * (1 - config.stop_loss_pct)
            risk.update(entry_price=round(state["entry_price"], 2), stop_loss_price=round(stop_price, 2),
                        distance_to_stop_pct=round((price - stop_price) / price * 100, 2))
        else:
            risk["position"] = "flat, no stop-loss to watch"
        s.output(**risk)

    with log.step("read_news") as s:
        news = get_news_sentiment()
        s.output(headlines=news["headline_count"], sentiment=news["label"],
                 score=news["avg_compound"], sample=news["sample"][:3],
                 feeds_failed=news.get("feeds_failed", []),
                 used_for_decisions="no, logged for future research only")

    with log.step("read_mood") as s:
        mood = get_fear_greed()
        s.output(value=mood["value"], label=mood["label"],
                 used_for_decisions="no, logged for future research only")

    with log.step("decide_trade") as s:
        before = {"cash": state["cash"], "btc": state["btc"]}
        state, note = step_decision(state, latest, config, learned_filters=learned_filters, bins=bins)
        equity_now = state["cash"] + state["btc"] * price
        s.output(decision=note, price=price, cash_before=round(before["cash"], 2),
                 cash_after=round(state["cash"], 2), btc_after=round(state["btc"], 8),
                 equity=round(equity_now, 2), in_position=state["in_position"])
        print(f"[{latest_ts}] price={price:.2f} equity=${equity_now:.2f} "
              f"in_position={state['in_position']} halted={state['trading_halted']} | {note}")

    with log.step("save_state") as s:
        append_csv(CONTEXT_LOG_FILE, ["timestamp", "news_label", "news_score", "fear_greed", "fear_greed_label"],
                   [latest_ts, news["label"], news["avg_compound"], mood["value"], mood["label"]])
        note_with_context = f"{note} | news={news['label']} fear_greed={mood['value']}"
        append_csv(LOG_FILE, ["timestamp", "event", "price", "cash", "btc", "equity", "note"],
                   [latest_ts, "tick", price, state["cash"], state["btc"], equity_now, note_with_context])
        state["last_candle_ts"] = latest_ts
        save_state(state)
        s.output(files=[STATE_FILE, LOG_FILE, CONTEXT_LOG_FILE],
                 pushed_by="GitHub Actions, right after this run")

    log.finish("done", note)
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
