"""12_experiments.main(): each experiment trades only when ITS timeframe has a new
candle, and one broken price feed can't stop the others."""
import importlib
import json

import pandas as pd
import pytest

from engine.experiment import new_state

runner = importlib.import_module("12_experiments")

HOURLY_LAST = "2026-01-01 09:00:00"
DAILY_LAST = "2025-12-10 00:00:00"


def flat_candles(start, periods, freq):
    return pd.DataFrame({"timestamp": pd.date_range(start, periods=periods, freq=freq),
                         "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1.0})


def fake_fetch(symbol, timeframe):
    if timeframe == "1h":
        return flat_candles("2026-01-01 00:00", 10, "h"), 100.0
    return flat_candles("2025-12-01", 10, "D"), 100.0


EXPERIMENTS = [
    {"id": "hourly_x", "employee": "hx", "description": "hourly", "strategy": "price_above_sma",
     "params": {"window": 3}, "stop_loss": 0.03, "research_note": "n"},
    {"id": "daily_x", "employee": "dx", "description": "daily", "strategy": "price_above_sma",
     "params": {"window": 3}, "stop_loss": 0.10, "symbol": "ETH/USD", "timeframe": "1d",
     "kill_switch": None, "research_note": "n"},
]


@pytest.fixture
def workdir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "experiments").mkdir()
    (tmp_path / "experiments" / "config.json").write_text(json.dumps({"experiments": EXPERIMENTS}))
    monkeypatch.setattr(runner, "fetch", fake_fetch)
    return tmp_path


def write_state(workdir, exp_id, last_candle_ts):
    state = new_state(start_price=100.0, started_at="2026-01-01T00:00:00+00:00")
    state["last_candle_ts"] = last_candle_ts
    folder = workdir / "experiments" / exp_id
    folder.mkdir(exist_ok=True)
    (folder / "state.json").write_text(json.dumps(state))
    return folder / "state.json"


def read_steps(workdir):
    run = json.loads((workdir / "runlog" / "latest_experiments.json").read_text())
    return {s["step"]: s for s in run["steps"]}


def test_only_the_experiment_with_a_new_candle_trades(workdir):
    write_state(workdir, "hourly_x", "2026-01-01 08:00:00")   # a new hourly candle has closed
    daily_path = write_state(workdir, "daily_x", DAILY_LAST)  # no new daily candle yet
    before = daily_path.read_text()

    assert runner.main() == 0

    assert daily_path.read_text() == before, "a daily experiment with nothing new must not rewrite its state"
    hourly_state = json.loads((workdir / "experiments" / "hourly_x" / "state.json").read_text())
    assert hourly_state["last_candle_ts"] == HOURLY_LAST
    steps = read_steps(workdir)
    assert steps["hourly_x"]["status"] == "done" and steps["daily_x"]["status"] == "done"
    assert "no new 1d candle" in steps["daily_x"]["outputs"]["action"]
    assert steps["daily_x"]["outputs"]["asset"] == "ETH/USD"
    assert steps["daily_x"]["outputs"]["btc_since_start_pct"] is None   # the BTC field is only for BTC experiments


def test_nothing_new_anywhere_writes_nothing(workdir):
    write_state(workdir, "hourly_x", HOURLY_LAST)
    write_state(workdir, "daily_x", DAILY_LAST)
    assert runner.main() == 0
    assert not (workdir / "runlog").exists()


def test_a_broken_feed_fails_only_its_own_experiments(workdir, monkeypatch):
    write_state(workdir, "hourly_x", "2026-01-01 08:00:00")

    def fetch_without_daily(symbol, timeframe):
        if timeframe == "1d":
            raise RuntimeError("Kraken is down")
        return fake_fetch(symbol, timeframe)

    monkeypatch.setattr(runner, "fetch", fetch_without_daily)
    assert runner.main() == 1
    steps = read_steps(workdir)
    assert steps["hourly_x"]["status"] == "done"
    assert steps["daily_x"]["status"] == "error" and "Kraken is down" in steps["daily_x"]["error"]
    assert not (workdir / "experiments" / "daily_x" / "state.json").exists(), "no fake fresh account on a failed feed"


def test_a_brand_new_daily_experiment_starts_a_fresh_account(workdir):
    write_state(workdir, "hourly_x", HOURLY_LAST)
    assert runner.main() == 0   # the daily one has no state yet, so it is due
    state = json.loads((workdir / "experiments" / "daily_x" / "state.json").read_text())
    assert state["cash"] == 1000.0 and state["last_candle_ts"] == DAILY_LAST and state["start_price"] == 100.0
