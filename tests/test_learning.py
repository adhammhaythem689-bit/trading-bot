import pandas as pd
from engine.learning import learn_filters


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
