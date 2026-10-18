import pandas as pd
from engine.live import new_candles_since, effective_signal


def frame(changes, start="2026-10-13 20:00"):
    ts = pd.date_range(start, periods=len(changes), freq="h")
    return pd.DataFrame({"timestamp": ts, "position_change": changes, "close": 100.0})


def test_cross_inside_a_gap_is_not_lost():
    # The real Oct 13 case: buy cross at 23:00, GitHub skipped the runs, next run saw 00:00 first.
    df = frame([0, 0, 0, 1, 0, 0])  # 20:00 .. 01:00, cross at 23:00
    new, covers = new_candles_since(df, "2026-10-13 21:00:00")
    change, cross_ts, missed = effective_signal(new)
    assert covers
    assert change == 1
    assert cross_ts == pd.Timestamp("2026-10-13 23:00")
    assert missed == 3  # 22:00, 23:00, 00:00 were never looked at on time


def test_latest_cross_in_the_gap_wins():
    df = frame([0, 1, 0, -1, 0])  # bought and sold again inside the gap
    new, _ = new_candles_since(df, "2026-10-13 20:00:00")
    change, cross_ts, _ = effective_signal(new)
    assert change == -1
    assert cross_ts == pd.Timestamp("2026-10-13 23:00")


def test_no_cross_means_no_action():
    df = frame([0, 0, 0])
    new, _ = new_candles_since(df, "2026-10-13 20:00:00")
    assert effective_signal(new) == (0, None, 1)


def test_nothing_new_returns_empty():
    df = frame([0, 0, 0])
    new, _ = new_candles_since(df, "2026-10-13 22:00:00")
    assert new.empty


def test_first_run_ever_only_looks_at_the_latest_candle():
    df = frame([0, 1, 0])
    new, covers = new_candles_since(df, None)
    assert len(new) == 1 and covers


def test_gap_longer_than_the_fetched_data_is_flagged():
    df = frame([0, 0, 0], start="2026-10-14 10:00")
    _, covers = new_candles_since(df, "2026-10-13 21:00:00")
    assert not covers
