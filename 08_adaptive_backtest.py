"""
Step 8: adaptive backtest -- the bot "learns from its mistakes" in the only
honest sense possible: it consults the win-rate table from step 7 before
taking a trade, and skips trades whose condition-combination has a reliable
(enough samples) history of losing more often than winning.

It does NOT skip based on unreliable combos (too few samples) -- those are
treated as "unknown, trade normally" rather than guessed at.

To check this isn't just overfitting to the exact same data it learned from,
we train the filter on the first 75% of history and validate on the last 25%
it never saw, same discipline as step 4.
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
MAX_DRAWDOWN_KILL = 0.20
MIN_SAMPLES = 30  # raised from 5: a 5-trade "win rate" proved untrustworthy on unseen data
WIN_RATE_SKIP_THRESHOLD = 50.0  # skip trades in combos with a reliable win rate below this

df_full = pd.read_csv("btc_usdt_1h.csv", parse_dates=["timestamp"])
split_idx = int(len(df_full) * 0.75)
train_df = df_full.iloc[:split_idx].reset_index(drop=True)
test_df = df_full.iloc[split_idx:].reset_index(drop=True)


def add_features(df):
    df = df.copy()
    df["short_ma"] = df["close"].rolling(window=SHORT_WINDOW).mean()
    df["long_ma"] = df["close"].rolling(window=LONG_WINDOW).mean()
    df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)
    df["position_change"] = df["signal"].diff()
    df["returns"] = df["close"].pct_change()
    df["volatility"] = df["returns"].rolling(window=24).std() * 100
    df["momentum_pct"] = df["short_ma"].pct_change(6).abs() * 100
    df["hour"] = df["timestamp"].dt.hour
    df["trend_strength"] = df["close"].pct_change(24).abs() * 100
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=24).mean()
    return df.dropna(subset=["short_ma", "long_ma", "volatility", "momentum_pct",
                              "trend_strength", "volume_ratio"]).reset_index(drop=True)


def hour_bucket(h):
    if h < 6: return "night"
    if h < 12: return "morning"
    if h < 18: return "afternoon"
    return "evening"


def bucket(value, edges, labels):
    for i in range(len(edges) - 1):
        if edges[i] <= value <= edges[i + 1]:
            return labels[i]
    return labels[-1]


def learn_filters(df):
    vol_bins = df["volatility"].quantile([0, 1/3, 2/3, 1]).values
    momentum_bins = df["momentum_pct"].quantile([0, 0.5, 1]).values
    trend_bins = df["trend_strength"].quantile([0, 0.5, 1]).values
    volume_bins = df["volume_ratio"].quantile([0, 0.5, 1]).values

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
            trades.append({**entry_conditions, "pnl_pct": pnl_pct, "win": pnl_pct > 0})
            btc = 0.0
            in_position = False

    bins = {"vol": vol_bins, "momentum": momentum_bins, "trend": trend_bins, "volume": volume_bins}
    trades_df = pd.DataFrame(trades)
    if trades_df.empty:
        return {}, bins

    trades_df["combo"] = ("volatility=" + trades_df["volatility"] + "|"
                           + "momentum=" + trades_df["momentum"] + "|"
                           + "hour=" + trades_df["hour"] + "|"
                           + "trend=" + trades_df["trend"] + "|"
                           + "volume=" + trades_df["volume"])
    grouped = trades_df.groupby("combo").agg(n=("win", "count"), win_rate=("win", "mean")).reset_index()
    grouped["win_rate"] *= 100
    lookup = {r["combo"]: {"n": int(r["n"]), "win_rate": float(r["win_rate"])}
              for _, r in grouped.iterrows()}
    return lookup, bins


def run_backtest(df, bins, learned_filters=None):
    cash, btc, in_position = STARTING_BALANCE, 0.0, False
    entry_price = 0.0
    trading_halted = False
    peak_equity = STARTING_BALANCE
    trades = []
    equity_curve = []
    skipped_count = 0

    for _, row in df.iterrows():
        price = row["close"]
        equity_now = cash + btc * price
        peak_equity = max(peak_equity, equity_now)
        if not trading_halted and (equity_now - peak_equity) / peak_equity <= -MAX_DRAWDOWN_KILL:
            trading_halted = True

        if in_position and price <= entry_price * (1 - STOP_LOSS_PCT):
            cash += (btc * price) * (1 - FEE_RATE)
            trades.append({"pnl_pct": (price - entry_price) / entry_price * 100, "reason": "stop_loss"})
            btc = 0.0
            in_position = False

        elif not trading_halted and row["position_change"] == 1 and not in_position:
            take_trade = True
            if learned_filters is not None:
                combo = ("volatility=" + bucket(row["volatility"], bins["vol"], ["low", "medium", "high"])
                          + "|momentum=" + bucket(row["momentum_pct"], bins["momentum"], ["weak", "strong"])
                          + "|hour=" + hour_bucket(row["hour"])
                          + "|trend=" + bucket(row["trend_strength"], bins["trend"], ["weak", "strong"])
                          + "|volume=" + bucket(row["volume_ratio"], bins["volume"], ["low", "high"]))
                info = learned_filters.get(combo)
                if info and info["n"] >= MIN_SAMPLES and info["win_rate"] < WIN_RATE_SKIP_THRESHOLD:
                    take_trade = False
                    skipped_count += 1

            if take_trade:
                trade_capital = min(cash * RISK_PER_TRADE / STOP_LOSS_PCT, cash)
                btc = (trade_capital * (1 - FEE_RATE)) / price
                cash -= trade_capital
                entry_price = price
                in_position = True

        elif row["position_change"] == -1 and in_position:
            cash += (btc * price) * (1 - FEE_RATE)
            trades.append({"pnl_pct": (price - entry_price) / entry_price * 100, "reason": "signal"})
            btc = 0.0
            in_position = False

        equity_curve.append(cash + btc * price)

    final_equity = equity_curve[-1] if equity_curve else STARTING_BALANCE
    trades_df = pd.DataFrame(trades)
    win_rate = (trades_df["pnl_pct"] > 0).mean() * 100 if len(trades_df) else 0
    eq = pd.Series(equity_curve)
    max_dd = ((eq - eq.cummax()) / eq.cummax() * 100).min() if len(eq) else 0

    return {
        "final_equity": final_equity,
        "return_pct": (final_equity - STARTING_BALANCE) / STARTING_BALANCE * 100,
        "num_trades": len(trades_df), "win_rate": win_rate, "max_drawdown": max_dd,
        "skipped_by_filter": skipped_count,
    }


train_feat = add_features(train_df)
test_feat = add_features(test_df)

learned_filters, bins = learn_filters(train_feat)
print(f"Learned {len(learned_filters)} condition combinations from training data.")
print(f"Of those, {sum(1 for v in learned_filters.values() if v['n'] >= MIN_SAMPLES)} are reliable (n>={MIN_SAMPLES}).")

baseline = run_backtest(test_feat, bins, learned_filters=None)
adaptive = run_backtest(test_feat, bins, learned_filters=learned_filters)

test_start, test_end = test_feat["close"].iloc[0], test_feat["close"].iloc[-1]
buy_hold_return = (test_end / test_start - 1) * 100

print("\n" + "=" * 70)
print("RESULTS ON UNSEEN TEST DATA (last 25%, filter never trained on this)")
print("=" * 70)
print(f"{'':20s} {'Baseline (no filter)':>22s} {'Adaptive (with filter)':>24s}")
print(f"{'Return':20s} {baseline['return_pct']:>21.2f}% {adaptive['return_pct']:>23.2f}%")
print(f"{'Num trades':20s} {baseline['num_trades']:>22d} {adaptive['num_trades']:>24d}")
print(f"{'Win rate':20s} {baseline['win_rate']:>21.1f}% {adaptive['win_rate']:>23.1f}%")
print(f"{'Max drawdown':20s} {baseline['max_drawdown']:>21.2f}% {adaptive['max_drawdown']:>23.2f}%")
print(f"{'Trades skipped':20s} {'--':>22s} {adaptive['skipped_by_filter']:>24d}")
print(f"\nBuy & hold on this test period: {buy_hold_return:+.2f}%")

print("\n--- VERDICT ---")
if adaptive["return_pct"] > baseline["return_pct"]:
    print(f"The learned filter IMPROVED returns by {adaptive['return_pct'] - baseline['return_pct']:.2f} points on unseen data.")
else:
    print(f"The learned filter did NOT improve returns on unseen data "
          f"({adaptive['return_pct']:.2f}% vs {baseline['return_pct']:.2f}%).")
print("With this little data, treat this as a single noisy test, not proof either way.")
