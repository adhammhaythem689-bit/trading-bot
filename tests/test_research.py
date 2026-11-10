import numpy as np
import pandas as pd
import pytest
from engine.research import simulate, metrics, buy_and_hold, walk_forward
from engine.strategies import STRATEGIES, sma_cross, donchian_breakout, rsi_reversion


def candles(opens, closes=None, lows=None):
    n = len(opens)
    closes = closes or opens
    lows = lows or [min(o, c) for o, c in zip(opens, closes)]
    return pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=n, freq="h"),
        "open": opens, "high": [max(o, c) for o, c in zip(opens, closes)], "low": lows,
        "close": closes, "volume": 1.0,
    })


def test_signal_is_filled_at_the_next_open_not_the_signal_close():
    df = candles([100, 100, 110, 120])
    target = pd.Series([1, 1, 1, 1], dtype=float)  # wants in from the first close
    res = simulate(df, target, cost=0.0)
    # can't trade on candle 0's own close; first fill is candle 1's open (100)
    assert res["equity"][0] == 1000
    assert res["equity"][-1] == pytest.approx(1000 * 120 / 100)


def test_costs_are_paid_on_entry_and_exit():
    df = candles([100, 100, 100, 100])
    target = pd.Series([1, 1, 0, 0], dtype=float)
    res = simulate(df, target, cost=0.01)
    assert len(res["trades"]) == 1
    assert res["equity"][-1] == pytest.approx(1000 * 0.99 * 0.99)


def test_stop_loss_fills_at_the_stop_or_the_gap_open():
    # entry at 100, stop 3% = 97; candle 2 opens at 90 (gap below the stop) -> fill at 90, not 97
    df = candles([100, 100, 90, 90], closes=[100, 100, 90, 90], lows=[100, 100, 89, 89])
    res = simulate(df, pd.Series([1, 1, 1, 1], dtype=float), cost=0.0, stop_loss=0.03)
    assert res["trades"][0]["reason"] == "stop_loss"
    assert res["trades"][0]["exit_price"] == 90


def test_no_reentry_after_a_stop_until_the_signal_resets():
    df = candles([100, 100, 96, 96, 96, 96], lows=[100, 100, 95, 96, 96, 96])
    target = pd.Series([1, 1, 1, 1, 1, 1], dtype=float)
    res = simulate(df, target, cost=0.0, stop_loss=0.03)
    assert len(res["trades"]) == 1 and res["open_trade"] is None


def test_short_profits_when_price_falls_and_loses_when_it_rises():
    target = pd.Series([-1, -1, -1, -1], dtype=float)
    down = simulate(candles([100, 100, 90, 80]), target, cost=0.0, short_cost_per_hour=0.0)
    up = simulate(candles([100, 100, 110, 120]), target, cost=0.0, short_cost_per_hour=0.0)
    assert down["equity"][-1] == pytest.approx(1200)   # 10 units shorted at 100, price 80
    assert up["equity"][-1] == pytest.approx(800)      # price 120


def test_short_stop_loss_fills_at_the_stop_or_the_gap_open():
    # short entered at 100, stop 3% = 103; candle 2 gaps up to open at 110 -> fill at 110
    df = candles([100, 100, 110, 110])
    res = simulate(df, pd.Series([-1] * 4, dtype=float), cost=0.0, stop_loss=0.03, short_cost_per_hour=0.0)
    trade = res["trades"][0]
    assert trade["side"] == "short" and trade["reason"] == "stop_loss" and trade["exit_price"] == 110
    assert trade["pnl_pct"] == pytest.approx(-10.0)


def test_no_short_reentry_after_a_stop_until_the_signal_resets():
    df = candles([100, 100, 110, 110, 110, 110])
    res = simulate(df, pd.Series([-1] * 6, dtype=float), cost=0.0, stop_loss=0.03, short_cost_per_hour=0.0)
    assert len(res["trades"]) == 1 and res["open_trade"] is None


def test_flipping_from_long_to_short_trades_both_legs_at_the_same_open():
    df = candles([100, 100, 100, 110, 110])
    target = pd.Series([1, 1, -1, -1, -1], dtype=float)  # decided at close, filled next open
    res = simulate(df, target, cost=0.0, short_cost_per_hour=0.0)
    assert res["trades"][0]["side"] == "long" and res["trades"][0]["exit_price"] == 110
    assert res["open_trade"]["side"] == "short" and res["open_trade"]["entry_price"] == 110
    assert res["equity"][-1] == pytest.approx(1100)


def test_holding_a_short_costs_money_every_hour():
    df = candles([100] * 5)
    res = simulate(df, pd.Series([-1] * 5, dtype=float), cost=0.0, short_cost_per_hour=0.001)
    assert res["equity"][-1] == pytest.approx(1000 - 4)  # 4 hours held, 1 unit-value each hour


def test_strategies_do_not_look_ahead():
    """Changing the future must not change any earlier target."""
    rng = np.random.default_rng(0)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 1000)))
    df = candles(list(close))
    for name, strat in STRATEGIES.items():
        params = strat["grid"][0]
        full = strat["fn"](df, **params)
        cut = strat["fn"](df.iloc[:700].reset_index(drop=True), **params)
        assert (full.iloc[:700].to_numpy() == cut.to_numpy()).all(), name


def test_walk_forward_never_reports_the_training_window():
    rng = np.random.default_rng(1)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.01, 600)))
    df = candles(list(close))
    wf = walk_forward(df, STRATEGIES["sma_cross"], train_hours=300, test_hours=100)
    assert len(wf["folds"]) == 3
    assert len(wf["equity"]) == 300  # only the 3 test windows
    assert wf["folds"][0]["test_period"].startswith(str(df["timestamp"].iloc[300]))


def test_metrics_drawdown_and_win_rate():
    m = metrics([1100, 990, 1210], [{"pnl_pct": 10}, {"pnl_pct": -5}])
    assert m["return_pct"] == pytest.approx(21.0)
    assert m["max_drawdown_pct"] == pytest.approx(-10.0)
    assert m["win_rate"] == 50.0
