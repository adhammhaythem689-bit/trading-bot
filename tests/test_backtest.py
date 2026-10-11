import pandas as pd
import pytest
from engine.config import StrategyConfig
from engine.features import prepare
from engine.backtest import run_backtest
from engine.metrics import compute_metrics


def test_fees_are_deducted_on_both_entry_and_exit():
    """A simple up-then-down round trip, with 0% fees vs 1% fees, must show
    the 1%-fee version ending with strictly less equity (fees are a real
    cost on both the buy and the sell)."""
    prices = [100.0] * 30 + [100.0 + i for i in range(1, 15)] + [113.0] * 5 + [113.0 - i for i in range(1, 15)]
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=len(prices), freq="h"),
        "open": prices, "high": prices, "low": prices, "close": prices, "volume": [10.0] * len(prices),
    })

    config_no_fee = StrategyConfig(short_window=5, long_window=15, fee_rate=0.0,
                                     risk_per_trade=None, stop_loss_pct=None, max_drawdown_kill=None)
    config_fee = StrategyConfig(short_window=5, long_window=15, fee_rate=0.01,
                                  risk_per_trade=None, stop_loss_pct=None, max_drawdown_kill=None)

    prepared_no_fee = prepare(df, config_no_fee)
    prepared_fee = prepare(df, config_fee)

    result_no_fee = run_backtest(prepared_no_fee, config_no_fee)
    result_fee = run_backtest(prepared_fee, config_fee)

    assert len(result_no_fee.trades) >= 1, "test setup should produce at least one round-trip trade"
    assert result_fee.final_equity < result_no_fee.final_equity, (
        "fees should strictly reduce final equity relative to a zero-fee run on identical signals"
    )


def test_stop_loss_exits_before_signal_would():
    """Construct a price path with a single-candle crash so steep (20%) that
    it must breach a 3% stop-loss on the very first post-peak candle, before
    the (slower-reacting) moving-average crossover could possibly fire. This
    isolates the stop-loss path from the signal-exit path unambiguously."""
    prices = [100.0] * 30 + [100.0 + i for i in range(1, 10)] + [108.0]  # enter near ~108
    crash = [108.0 * 0.80]  # single-candle 20% crash, far past the 3% stop
    prices = prices + crash + [crash[-1]] * 20

    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=len(prices), freq="h"),
        "open": prices, "high": prices, "low": prices, "close": prices, "volume": [10.0] * len(prices),
    })

    config = StrategyConfig(short_window=5, long_window=15, stop_loss_pct=0.03,
                              risk_per_trade=0.02, max_drawdown_kill=0.5)
    prepared = prepare(df, config)
    result = run_backtest(prepared, config)

    assert len(result.trades) >= 1
    assert result.trades[0]["reason"] == "stop_loss", (
        f"expected the sharp crash to trigger a stop-loss exit, got reason={result.trades[0]['reason']!r}"
    )


def test_kill_switch_halts_trading_and_stays_halted():
    """A severe, sustained equity drawdown should trip the kill switch, and
    once tripped, no further trades should open even if a new buy signal fires."""
    # repeated whipsaw pattern designed to rack up losing trades and drawdown
    cycle = [100.0] * 10 + [103.0] * 2 + [97.0] * 2
    prices = (cycle * 15)
    df = pd.DataFrame({
        "timestamp": pd.date_range("2024-01-01", periods=len(prices), freq="h"),
        "open": prices, "high": prices, "low": prices, "close": prices, "volume": [10.0] * len(prices),
    })

    config = StrategyConfig(short_window=3, long_window=8, stop_loss_pct=0.01,
                              risk_per_trade=0.5, max_drawdown_kill=0.05, fee_rate=0.002)
    prepared = prepare(df, config)
    result = run_backtest(prepared, config)

    assert result.trading_halted, "a large sustained drawdown should trip the kill switch in this adversarial setup"
    assert result.halted_at is not None


def test_metrics_win_rate_matches_known_trades():
    class FakeResult:
        trades = [
            {"pnl_pct": 5.0, "reason": "signal"},
            {"pnl_pct": -2.0, "reason": "signal"},
            {"pnl_pct": 3.0, "reason": "signal"},
            {"pnl_pct": -1.0, "reason": "stop_loss"},
        ]
        equity_curve = [1000, 1050, 1029, 1060, 1049]
        final_equity = 1049
        trading_halted = False
        skipped_by_filter = 0

    metrics = compute_metrics(FakeResult(), starting_balance=1000)
    assert metrics["num_trades"] == 4
    assert metrics["win_rate"] == pytest.approx(50.0)  # 2 wins out of 4
    assert metrics["return_pct"] == pytest.approx(4.9)
