"""
The self-learning condition-analysis layer: given a set of completed trades
with their entry-time condition fingerprints, compute win rate per
combination, and refuse to trust combinations with too few samples.
"""
from dataclasses import replace
import pandas as pd
from engine.backtest import run_backtest
from engine.features import compute_bins, condition_combo


def label_trades_with_conditions(df, config):
    """Tag each trade with the condition-combo present at its ENTRY (not exit,
    using post-entry data would be lookahead).

    Trades come from run_backtest itself, so they get the same stop-loss and
    fees the live bot pays. The kill switch is turned off here only so one
    bad stretch doesn't hide the rest of history from the learner.
    """
    bins = compute_bins(df)
    result = run_backtest(df, replace(config, max_drawdown_kill=None))
    rows_by_time = df.set_index("timestamp")
    labeled = [
        {"combo": condition_combo(rows_by_time.loc[t["entry_time"]], bins),
         "pnl_pct": t["net_pnl_pct"], "win": t["net_pnl_pct"] > 0}
        for t in result.trades
    ]
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
