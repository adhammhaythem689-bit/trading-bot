"""
Step 1: pull real historical BTC/USDT price data from a public exchange API
(no account or API key needed for this, it's public market data) and plot it.

Binance caps each request at 1000 candles, so for a longer history we page
backwards in time, 1000 candles at a time, and stitch the results together.
"""
import ccxt
import pandas as pd
import matplotlib.pyplot as plt
import time

exchange = ccxt.binance()

symbol = "BTC/USDT"
timeframe = "1h"
total_candles = 17520  # ~2 years of hourly data, spans multiple market regimes

all_rows = []
since = exchange.milliseconds() - total_candles * 60 * 60 * 1000

while len(all_rows) < total_candles:
    batch = exchange.fetch_ohlcv(symbol, timeframe=timeframe, since=since, limit=1000)
    if not batch:
        break
    all_rows.extend(batch)
    since = batch[-1][0] + 60 * 60 * 1000  # move past the last candle fetched
    time.sleep(exchange.rateLimit / 1000)  # respect Binance's rate limit

df = pd.DataFrame(all_rows, columns=["timestamp", "open", "high", "low", "close", "volume"])
df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
df = df.drop_duplicates(subset="timestamp").sort_values("timestamp").reset_index(drop=True)

print(df.head())
print(df.tail())
print(f"\nTotal candles: {len(df)} (~{len(df)/24:.0f} days)")

df.to_csv("btc_usdt_1h.csv", index=False)
print("Saved to btc_usdt_1h.csv")

plt.figure(figsize=(12, 6))
plt.plot(df["timestamp"], df["close"])
plt.title(f"{symbol} close price ({timeframe})")
plt.xlabel("Time")
plt.ylabel("Price (USDT)")
plt.tight_layout()
plt.savefig("btc_usdt_1h.png")
print("Saved chart to btc_usdt_1h.png")
