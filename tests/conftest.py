import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
import pytest


def make_price_series(prices, start="2024-01-01", freq="h"):
    """Build a minimal OHLCV dataframe from a list of close prices.

    open == high == low == close for simplicity, volume is constant; tests
    that need volume variation build their own dataframe directly.
    """
    n = len(prices)
    timestamps = pd.date_range(start=start, periods=n, freq=freq)
    return pd.DataFrame({
        "timestamp": timestamps,
        "open": prices, "high": prices, "low": prices, "close": prices,
        "volume": [100.0] * n,
    })


@pytest.fixture
def flat_then_rising_then_falling():
    """A price path with an unambiguous crossover: flat, then a clean ramp up
    (short MA crosses above long MA), then a clean ramp down (crosses back
    below). Long enough that both moving-average windows are populated well
    before the ramps start.
    """
    flat = [100.0] * 100
    rising = [100.0 + i * 2 for i in range(1, 80)]
    falling = [list(rising)[-1] - i * 2 for i in range(1, 80)]
    return make_price_series(flat + rising + falling)
