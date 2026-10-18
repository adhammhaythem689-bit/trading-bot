import pandas as pd
import pytest
from engine.experiment import new_state, step


def closed(opens, lows=None, start="2026-01-01 00:00"):
    n = len(opens)
    lows = lows or opens
    return pd.DataFrame({"timestamp": pd.date_range(start, periods=n, freq="h"),
                         "open": opens, "high": opens, "low": lows, "close": opens, "volume": 1.0})


def test_entry_fills_at_the_forming_candle_open_with_costs():
    df = closed([100, 100, 100])
    state, events, _ = step(new_state(), df, pd.Series([0, 0, 1.0]), forming_open=101.0, cost=0.01)
    assert events == [{"action": "BUY", "reason": "signal", "price": 101.0}]
    assert state["btc"] == pytest.approx(1000 * 0.99 / 101)
    assert state["cash"] == 0


def test_stop_loss_fires_on_a_candle_from_a_skipped_run():
    df = closed([100, 100, 100])
    state, _, _ = step(new_state(), df, pd.Series([1.0, 1, 1]), forming_open=100.0, cost=0.0)
    state["last_candle_ts"] = "2026-01-01 02:00:00"
    # three hours pass with no run; at 04:00 the low touched 96 (stop at 97)
    later = closed([100, 100, 100, 99, 98, 99], lows=[100, 100, 100, 99, 96, 99])
    state, events, n_new = step(state, later, pd.Series([1.0] * 6), forming_open=99.0, stop_loss=0.03, cost=0.0)
    assert n_new == 3
    assert events[0]["action"] == "SELL" and events[0]["reason"] == "stop_loss"
    assert events[0]["price"] == 97.0
    assert events[0]["candle"].startswith("2026-01-01 04:00")
    assert not state["in_position"]  # and no instant re-buy while still "stopped"
    assert state["stopped"]


def test_gap_below_the_stop_fills_at_the_open():
    df = closed([100])
    state, _, _ = step(new_state(), df, pd.Series([1.0]), forming_open=100.0, cost=0.0)
    later = closed([100, 90], lows=[100, 89])
    state, events, _ = step(state, later, pd.Series([1.0, 1.0]), forming_open=90.0, stop_loss=0.03, cost=0.0)
    assert events[0]["price"] == 90.0


def test_reentry_only_after_the_target_resets():
    df = closed([100])
    state, _, _ = step(new_state(), df, pd.Series([1.0]), forming_open=100.0, cost=0.0)
    state, _, _ = step(state, closed([100, 96], lows=[100, 95]), pd.Series([1.0, 1.0]), 96.0, stop_loss=0.03, cost=0.0)
    assert state["stopped"]
    # target drops to 0, then back to 1: now it may buy again
    state, ev, _ = step(state, closed([100, 96, 96], lows=[100, 95, 96]), pd.Series([1.0, 1, 0]), 96.0, stop_loss=0.03, cost=0.0)
    assert not state["stopped"] and ev == []
    state, ev, _ = step(state, closed([100, 96, 96, 97]), pd.Series([1.0, 1, 0, 1]), 97.0, stop_loss=0.03, cost=0.0)
    assert ev[0]["action"] == "BUY"


def test_kill_switch_halts_and_exits():
    df = closed([100])
    state, _, _ = step(new_state(), df, pd.Series([1.0]), forming_open=100.0, cost=0.0)
    state, events, _ = step(state, closed([100, 79]), pd.Series([1.0, 1.0]), 79.0, cost=0.0)
    assert state["halted"] and not state["in_position"]
    assert [e["action"] for e in events] == ["HALT", "SELL"]


def test_sell_pnl_includes_both_costs():
    df = closed([100])
    state, _, _ = step(new_state(), df, pd.Series([1.0]), forming_open=100.0, cost=0.01)
    state, events, _ = step(state, closed([100, 100]), pd.Series([1.0, 0.0]), 100.0, cost=0.01)
    assert events[0]["pnl_pct"] == pytest.approx((0.99 * 0.99 - 1) * 100, abs=0.01)
