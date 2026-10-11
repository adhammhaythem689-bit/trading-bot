"""
Step 7: self-analysis layer.

Re-runs the strategy, but this time records the MARKET CONDITIONS present at
the moment of every trade entry (not just the trade's result). Then groups
trades by those conditions and computes a real win rate per combination,
with a minimum sample size so we don't trust a "100% win rate" that's really
just one lucky trade.

Conditions tracked per entry:
  - volatility_bucket: low / medium / high (based on recent price swings)
  - momentum_bucket: weak/strong, how fast the short-term average was already
    rising in the 6 hours BEFORE the crossover (available at entry, unlike the
    gap between the two averages, which is always ~0 at the exact moment of a
    crossover by definition, so it carries no information at entry)
  - hour_bucket: time of day (0-6 / 6-12 / 12-18 / 18-24 UTC)
  - trend_bucket: weak/strong, based on how much price moved over the prior 24h
  - volume_bucket: low/high, current volume vs its recent 24h average

Output: learned_filters.json, a lookup table of
    "volatility=X|ma_gap=Y|hour=Z|trend=T|volume=V" -> {n, win_rate, avg_pnl_pct}
that the next script (08) will consult before taking a trade.

IMPORTANT TRADEOFF: adding more dimensions makes each "pattern" more specific
(closer to what people mean by "this looks like X"), but it also multiplies
the number of possible combinations, which means EACH ONE gets fewer historical
examples. More precise patterns need much more history to become trustworthy.
That tension is the whole reason MIN_SAMPLES exists, and why the honest result
below may be "not enough data yet" for most or all combinations.
"""
import pandas as pd
import numpy as np
import json

SHORT_WINDOW = 24
LONG_WINDOW = 72
STARTING_BALANCE = 1000.0
FEE_RATE = 0.001
RISK_PER_TRADE = 0.02
STOP_LOSS_PCT = 0.03
MIN_SAMPLES = 30  # raised from 5: a 5-trade "win rate" proved untrustworthy on unseen data

df = pd.read_csv("btc_usdt_1h.csv", parse_dates=["timestamp"])
df["short_ma"] = df["close"].rolling(window=SHORT_WINDOW).mean()
df["long_ma"] = df["close"].rolling(window=LONG_WINDOW).mean()
df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)
df["position_change"] = df["signal"].diff()

# conditions available at every point in time (computed BEFORE any trade decision,
# using only data available up to that candle, no lookahead)
df["returns"] = df["close"].pct_change()
df["volatility"] = df["returns"].rolling(window=24).std() * 100  # 24h rolling volatility, in %
df["momentum_pct"] = df["short_ma"].pct_change(6).abs() * 100  # short MA's own rate of change, last 6h
df["hour"] = df["timestamp"].dt.hour
df["trend_strength"] = df["close"].pct_change(24).abs() * 100  # how much price moved in the last 24h
df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=24).mean()

df = df.dropna(subset=["short_ma", "long_ma", "volatility", "momentum_pct", "trend_strength", "volume_ratio"]).reset_index(drop=True)

vol_bins = df["volatility"].quantile([0, 1/3, 2/3, 1]).values
momentum_bins = df["momentum_pct"].quantile([0, 0.5, 1]).values
trend_bins = df["trend_strength"].quantile([0, 0.5, 1]).values
volume_bins = df["volume_ratio"].quantile([0, 0.5, 1]).values


def bucket(value, edges, labels):
    for i in range(len(edges) - 1):
        if edges[i] <= value <= edges[i + 1]:
            return labels[i]
    return labels[-1]


def hour_bucket(h):
    if h < 6: return "night"
    if h < 12: return "morning"
    if h < 18: return "afternoon"
    return "evening"


cash, btc, in_position = STARTING_BALANCE, 0.0, False
entry_price, entry_conditions = 0.0, None
trades = []

for _, row in df.iterrows():
    price = row["close"]

    if row["position_change"] == 1 and not in_position:
        btc = (cash * (1 - FEE_RATE)) / price
        entry_price = price
        cash = 0.0
        in_position = True
        entry_conditions = {
            "volatility": bucket(row["volatility"], vol_bins, ["low", "medium", "high"]),
            "momentum": bucket(row["momentum_pct"], momentum_bins, ["weak", "strong"]),
            "hour": hour_bucket(row["hour"]),
            "trend": bucket(row["trend_strength"], trend_bins, ["weak", "strong"]),
            "volume": bucket(row["volume_ratio"], volume_bins, ["low", "high"]),
        }

    elif row["position_change"] == -1 and in_position:
        cash = (btc * price) * (1 - FEE_RATE)
        pnl_pct = (price - entry_price) / entry_price * 100
        trades.append({
            **entry_conditions,
            "entry_time": None, "pnl_pct": pnl_pct, "win": pnl_pct > 0,
        })
        btc = 0.0
        in_position = False

trades_df = pd.DataFrame(trades)
print(f"Total trades analyzed: {len(trades_df)}")

# group by the full combination of conditions
trades_df["combo"] = (
    "volatility=" + trades_df["volatility"] + "|"
    + "momentum=" + trades_df["momentum"] + "|"
    + "hour=" + trades_df["hour"] + "|"
    + "trend=" + trades_df["trend"] + "|"
    + "volume=" + trades_df["volume"]
)

grouped = trades_df.groupby("combo").agg(
    n=("win", "count"),
    win_rate=("win", "mean"),
    avg_pnl_pct=("pnl_pct", "mean"),
).reset_index()
grouped["win_rate"] = (grouped["win_rate"] * 100).round(1)
grouped["avg_pnl_pct"] = grouped["avg_pnl_pct"].round(2)
grouped["reliable"] = grouped["n"] >= MIN_SAMPLES
grouped = grouped.sort_values("win_rate", ascending=False)

print("\n" + "=" * 70)
print(f"WIN RATE BY CONDITION COMBINATION  (reliable = at least {MIN_SAMPLES} trades)")
print("=" * 70)
print(grouped.to_string(index=False))

reliable = grouped[grouped["reliable"]]
print(f"\n{len(reliable)} of {len(grouped)} combinations have enough trades to trust.")
if len(reliable):
    print(f"Best reliable combo:  {reliable.iloc[0]['combo']}  ({reliable.iloc[0]['win_rate']}% win rate, n={reliable.iloc[0]['n']})")
    worst = reliable.sort_values('win_rate').iloc[0]
    print(f"Worst reliable combo: {worst['combo']}  ({worst['win_rate']}% win rate, n={worst['n']})")
else:
    print("None of the combinations have enough samples yet to be trustworthy.")
    print("This is an honest result, not a bug: 45 trades split across many buckets")
    print("leaves most buckets with only 1-3 examples. More data (more paper trading")
    print("time, or more history) is needed before this filter can be trusted.")

# save the lookup table for the next script to use as a filter
lookup = {}
for _, r in grouped.iterrows():
    lookup[r["combo"]] = {"n": int(r["n"]), "win_rate": float(r["win_rate"]),
                           "avg_pnl_pct": float(r["avg_pnl_pct"]), "reliable": bool(r["reliable"])}

with open("learned_filters.json", "w") as f:
    json.dump(lookup, f, indent=2)
print("\nSaved lookup table to learned_filters.json")

trades_df.to_csv("trades_with_conditions.csv", index=False)
print("Saved full trade+conditions log to trades_with_conditions.csv")
