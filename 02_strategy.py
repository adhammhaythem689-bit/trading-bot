"""
Step 2: moving-average crossover strategy.

Idea: compute a short-term average price and a long-term average price.
When the short average crosses ABOVE the long average, that's a "buy" signal
(price is picking up momentum). When it crosses BELOW, that's a "sell" signal.

This script just computes the signals and shows them, it does not place any
trades yet, that comes in the backtester step.
"""
import pandas as pd
import matplotlib.pyplot as plt

SHORT_WINDOW = 12   # 12 hours
LONG_WINDOW = 48     # 48 hours

df = pd.read_csv("btc_usdt_1h.csv", parse_dates=["timestamp"])

df["short_ma"] = df["close"].rolling(window=SHORT_WINDOW).mean()
df["long_ma"] = df["close"].rolling(window=LONG_WINDOW).mean()

# signal: 1 means "short MA is above long MA" (bullish), 0 means bearish
df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)

# a trade happens when the signal changes from the previous row
df["position_change"] = df["signal"].diff()
# position_change == 1 -> just crossed up (buy), -1 -> just crossed down (sell)

buys = df[df["position_change"] == 1]
sells = df[df["position_change"] == -1]

print(f"Number of buy signals: {len(buys)}")
print(f"Number of sell signals: {len(sells)}")
print("\nFirst few signal changes:")
print(df[df["position_change"].notna() & (df["position_change"] != 0)]
      [["timestamp", "close", "short_ma", "long_ma", "position_change"]].head(10))

df.to_csv("btc_usdt_1h_with_signals.csv", index=False)

plt.figure(figsize=(14, 7))
plt.plot(df["timestamp"], df["close"], label="Close price", alpha=0.6)
plt.plot(df["timestamp"], df["short_ma"], label=f"{SHORT_WINDOW}h MA", linewidth=1.5)
plt.plot(df["timestamp"], df["long_ma"], label=f"{LONG_WINDOW}h MA", linewidth=1.5)
plt.scatter(buys["timestamp"], buys["close"], marker="^", color="green", s=100, label="Buy signal", zorder=5)
plt.scatter(sells["timestamp"], sells["close"], marker="v", color="red", s=100, label="Sell signal", zorder=5)
plt.title("BTC/USDT with moving-average crossover signals")
plt.xlabel("Time")
plt.ylabel("Price (USDT)")
plt.legend()
plt.tight_layout()
plt.savefig("btc_usdt_signals.png")
print("\nSaved chart to btc_usdt_signals.png")
