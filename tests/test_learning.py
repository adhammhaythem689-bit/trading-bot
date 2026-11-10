import pandas as pd
from engine.config import DEFAULT_CONFIG
from engine.learning import learn_filters, label_trades_with_conditions


def test_labels_use_the_same_stop_loss_and_fees_as_the_bot():
    # buy at 100, price falls to 90 (past the 3% stop) before the sell signal at 120
    closes = [100, 90, 120]
    df = pd.DataFrame({
        "timestamp": pd.date_range("2026-01-01", periods=3, freq="h"),
        "close": closes,
        "position_change": [1, 0, -1],
        "volatility": [1.0, 2.0, 3.0],
    })
    labeled, _ = label_trades_with_conditions(df, DEFAULT_CONFIG)

    fee = DEFAULT_CONFIG.fee_rate
    expected = ((1 - fee) * 90 / 100 * (1 - fee) - 1) * 100
    assert len(labeled) == 1, "the stop-loss exit ends the trade, the later sell signal is not a second trade"
    assert abs(labeled["pnl_pct"].iloc[0] - expected) < 1e-9
    assert not labeled["win"].iloc[0]


def test_min_samples_marks_small_groups_unreliable():
    labeled = pd.DataFrame([
        {"combo": "A", "pnl_pct": 1.0, "win": True},
        {"combo": "A", "pnl_pct": 1.0, "win": True},
        {"combo": "A", "pnl_pct": -1.0, "win": False},
        {"combo": "B", "pnl_pct": 1.0, "win": True},
    ])
    filters = learn_filters(labeled, min_samples=3)

    assert filters["A"]["n"] == 3
    assert filters["A"]["reliable"] is True
    assert filters["B"]["n"] == 1
    assert filters["B"]["reliable"] is False, "a single-trade group must never be marked reliable"


def test_win_rate_calculated_correctly():
    labeled = pd.DataFrame([
        {"combo": "X", "pnl_pct": 1.0, "win": True},
        {"combo": "X", "pnl_pct": 1.0, "win": True},
        {"combo": "X", "pnl_pct": 1.0, "win": True},
        {"combo": "X", "pnl_pct": -1.0, "win": False},
    ])
    filters = learn_filters(labeled, min_samples=1)
    assert filters["X"]["win_rate"] == 75.0


def test_empty_trades_returns_empty_dict():
    assert learn_filters(pd.DataFrame(), min_samples=5) == {}
