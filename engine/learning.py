"""
The self-learning condition-analysis layer: given a set of completed trades
with their entry-time condition fingerprints, compute win rate per
combination, and refuse to trust combinations with too few samples.
"""
import pandas as pd
from engine.features import compute_bins, condition_combo


def label_trades_with_conditions(df, config):
    """Re-walk the signals to capture the condition-combo present at each
    trade's ENTRY (not exit -- using post-entry data would be lookahead)."""
    bins = compute_bins(df)
    in_position = False
    entry_combo = None
    labeled = []

    for _, row in df.iterrows():
        if row["position_change"] == 1 and not in_position:
            in_position = True
            entry_combo = condition_combo(row, bins)
            entry_price = row["close"]
        elif row["position_change"] == -1 and in_position:
            pnl_pct = (row["close"] - entry_price) / entry_price * 100
            labeled.append({"combo": entry_combo, "pnl_pct": pnl_pct, "win": pnl_pct > 0})
            in_position = False

    return pd.DataFrame(labeled), bins


def learn_filters(labeled_trades_df, min_samples):
    """Win rate per condition-combo, with a 'reliable' flag based on min_samples.

    Returns a plain dict suitable for JSON serialization:
        {combo_string: {n, win_rate, avg_pnl_pct, reliable}}
    """
    if labeled_trades_df.empty:
        return {}

    grouped = labeled_trades_df.groupby("combo").agg(
        n=("win", "count"), win_rate=("win", "mean"), avg_pnl_pct=("pnl_pct", "mean"),
    ).reset_index()
    grouped["win_rate"] = (grouped["win_rate"] * 100).round(1)
    grouped["avg_pnl_pct"] = grouped["avg_pnl_pct"].round(2)
    grouped["reliable"] = grouped["n"] >= min_samples

    return {
        r["combo"]: {"n": int(r["n"]), "win_rate": float(r["win_rate"]),
                      "avg_pnl_pct": float(r["avg_pnl_pct"]), "reliable": bool(r["reliable"])}
        for _, r in grouped.iterrows()
    }
