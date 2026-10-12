"""
Keeps btc_usdt_1h.csv growing so the daily research works on new data.

Source: Binance's public market-data mirror (data-api.binance.vision), the
same exchange and pair (BTC/USDT) the stored history came from. The main
Binance API refuses GitHub Actions' servers (HTTP 451), and filling a Binance
history with Kraken prices would silently mix two venues, so if the mirror
is unreachable nothing is written and the caller reports it.

Only CLOSED candles are stored. The last stored candle is always re-fetched
and replaced, because it may have been saved while still forming (the
original download happened 37 minutes into its last hour).
"""
import time
import pandas as pd
import requests

from engine.data import validate_ohlcv

BINANCE_DATA_API = "https://data-api.binance.vision/api/v3/klines"
HOUR_MS = 60 * 60 * 1000
COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


def fetch_binance_closed_candles(start_ms, now_ms=None, symbol="BTCUSDT", get=requests.get):
    """All 1h candles opening at or after start_ms that have fully closed by now_ms."""
    now_ms = now_ms if now_ms is not None else int(time.time() * 1000)
    rows, cursor = [], start_ms
    while True:
        resp = get(BINANCE_DATA_API, params={"symbol": symbol, "interval": "1h",
                                             "startTime": cursor, "limit": 1000}, timeout=20)
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        for k in batch:
            open_ms, close_ms = k[0], k[6]
            if close_ms >= now_ms:
                continue  # candle still forming
            rows.append([open_ms, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])])
        if len(batch) < 1000:
            break
        cursor = batch[-1][0] + HOUR_MS

    df = pd.DataFrame(rows, columns=COLUMNS)
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    return df


def extend_history(path, fetch=fetch_binance_closed_candles, now_ms=None):
    """Append newly closed candles to the CSV at `path`. Returns a summary dict."""
    existing = pd.read_csv(path, parse_dates=["timestamp"])
    last_stored = existing["timestamp"].max()
    # naive timestamps in this file are UTC
    start_ms = int(last_stored.tz_localize("UTC").timestamp() * 1000)

    fresh = fetch(start_ms, now_ms)
    if fresh.empty:
        return {"appended": 0, "replaced": 0, "rows": len(existing),
                "last_candle": last_stored, "warnings": []}

    overlap = existing["timestamp"].isin(fresh["timestamp"])
    replaced = int(overlap.sum())
    combined = pd.concat([existing[~overlap], fresh], ignore_index=True)
    combined, warnings = validate_ohlcv(combined, source=path)
    combined[COLUMNS].to_csv(path, index=False)

    return {
        "appended": len(fresh) - replaced,
        "replaced": replaced,
        "rows": len(combined),
        "last_candle": combined["timestamp"].iloc[-1],
        "warnings": [f"{w.kind}: {w.detail}" for w in warnings],
    }
