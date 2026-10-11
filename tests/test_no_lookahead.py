"""
The single most important property of a backtest: no feature or signal at
row i may depend on any data from row i+1 onward. This test verifies it
directly, by checking that recomputing features on a TRUNCATED dataframe
(everything after row i deleted) gives the identical value at row i as the
full dataframe. If any feature used future data, truncating the future
would change the earlier value, and this test would fail.
"""
import pandas as pd
import pytest
from engine.config import DEFAULT_CONFIG
from engine.features import prepare


def test_features_identical_when_future_is_truncated(flat_then_rising_then_falling):
    df = flat_then_rising_then_falling
    full = prepare(df, DEFAULT_CONFIG)

    # pick a row comfortably in the middle, truncate everything after it in
    # the RAW data, then recompute features on just that truncated slice
    check_timestamp = full["timestamp"].iloc[100]
    raw_truncated = df[df["timestamp"] <= check_timestamp].reset_index(drop=True)
    truncated = prepare(raw_truncated, DEFAULT_CONFIG)

    full_row = full[full["timestamp"] == check_timestamp].iloc[0]
    truncated_row = truncated[truncated["timestamp"] == check_timestamp].iloc[0]

    for col in ["short_ma", "long_ma", "signal", "volatility", "momentum_pct", "trend_strength", "volume_ratio"]:
        assert full_row[col] == pytest.approx(truncated_row[col], nan_ok=True), (
            f"{col} differs when future data is truncated -- this means it used lookahead data"
        )
