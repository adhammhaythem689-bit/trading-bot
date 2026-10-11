from engine.config import StrategyConfig
from engine.features import prepare


def test_buy_signal_fires_on_clean_uptrend(flat_then_rising_then_falling):
    config = StrategyConfig(short_window=5, long_window=20)
    df = prepare(flat_then_rising_then_falling, config)

    buys = df[df["position_change"] == 1]
    sells = df[df["position_change"] == -1]

    assert len(buys) >= 1, "expected at least one buy signal during the clean ramp up"
    assert len(sells) >= 1, "expected at least one sell signal during the clean ramp down"
    # the first buy must come before the first sell (we go long before we exit)
    assert buys["timestamp"].iloc[0] < sells["timestamp"].iloc[0]


def test_no_signal_on_perfectly_flat_price():
    import pandas as pd
    flat = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=100, freq="h"),
        "open": [100.0] * 100, "high": [100.0] * 100, "low": [100.0] * 100,
        "close": [100.0] * 100, "volume": [50.0] * 100,
    })
    config = StrategyConfig(short_window=5, long_window=20)
    df = prepare(flat, config)
    assert (df["position_change"].fillna(0) == 0).all(), "flat price should never cross, so no signals"
