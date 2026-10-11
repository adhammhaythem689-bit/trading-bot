"""
Indicator and condition-feature computation, the single place this logic
lives now instead of five near-identical copies.

Every feature here is computed using ONLY data available up to and including
the current row (rolling windows, pct_change against the past), never future
rows. This is what "no lookahead bias" means concretely, and is covered by
tests/test_no_lookahead.py.
"""
import pandas as pd


def add_signal_columns(df, config):
    """Add the MA-crossover signal columns. Mutates a copy, returns it."""
    df = df.copy()
    df["short_ma"] = df["close"].rolling(window=config.short_window).mean()
    df["long_ma"] = df["close"].rolling(window=config.long_window).mean()
    df["signal"] = (df["short_ma"] > df["long_ma"]).astype(int)
    df["position_change"] = df["signal"].diff()
    return df


def add_condition_features(df):
    """Add the market-condition features used by the self-learning filter.

    All of these are backward-looking (rolling/diff/pct_change), so they are
    valid to use as a filter on trades that start at the current row.
    """
    df = df.copy()
    df["returns"] = df["close"].pct_change()
    df["volatility"] = df["returns"].rolling(window=24).std() * 100
    df["momentum_pct"] = df["short_ma"].pct_change(6).abs() * 100
    df["hour"] = df["timestamp"].dt.hour
    df["trend_strength"] = df["close"].pct_change(24).abs() * 100
    df["volume_ratio"] = df["volume"] / df["volume"].rolling(window=24).mean()
    return df


def prepare(df, config):
    """Full feature pipeline: signals + condition features, with warmup rows dropped."""
    df = add_signal_columns(df, config)
    df = add_condition_features(df)
    required = ["short_ma", "long_ma", "volatility", "momentum_pct", "trend_strength", "volume_ratio"]
    return df.dropna(subset=required).reset_index(drop=True)


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


def compute_bins(df):
    """Compute quantile bin edges from a dataframe (fit on TRAINING data only)."""
    return {
        "volatility": df["volatility"].quantile([0, 1/3, 2/3, 1]).values,
        "momentum": df["momentum_pct"].quantile([0, 0.5, 1]).values,
        "trend": df["trend_strength"].quantile([0, 0.5, 1]).values,
        "volume": df["volume_ratio"].quantile([0, 0.5, 1]).values,
    }


def condition_combo(row, bins):
    """The "pattern fingerprint" string for a single row, given fitted bins."""
    return (
        "volatility=" + bucket(row["volatility"], bins["volatility"], ["low", "medium", "high"]) + "|"
        + "momentum=" + bucket(row["momentum_pct"], bins["momentum"], ["weak", "strong"]) + "|"
        + "hour=" + hour_bucket(row["hour"]) + "|"
        + "trend=" + bucket(row["trend_strength"], bins["trend"], ["weak", "strong"]) + "|"
        + "volume=" + bucket(row["volume_ratio"], bins["volume"], ["low", "high"])
    )
