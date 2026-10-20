"""Corrupt or malformed account state must never be treated as a fresh
$1,000 account, and must fail loudly instead of silently. Covers both the
main bot's paper_state.json and each experiment's state.json.
"""
import importlib
import json

import pytest

paper_trade = importlib.import_module("06_paper_trade")
experiments = importlib.import_module("12_experiments")


GOOD_PAPER_STATE = {
    "cash": 333.33, "btc": 0.008, "in_position": True, "entry_price": 82681.2,
    "peak_equity": 1003.4, "trading_halted": False, "last_candle_ts": "2026-10-20 14:00:00",
}

GOOD_EXPERIMENT_STATE = {
    "cash": 1000.0, "btc": 0.0, "in_position": False, "entry_price": 0.0,
    "stopped": False, "peak_equity": 1000.0, "halted": False,
    "last_candle_ts": None, "start_price": 100.0, "started_at": "2026-10-18T00:00:00+00:00",
    "starting_cash": 1000.0, "trades": 0,
}


def test_valid_paper_state_passes():
    assert paper_trade.validate_state(dict(GOOD_PAPER_STATE))["cash"] == 333.33


def test_missing_field_is_rejected():
    bad = dict(GOOD_PAPER_STATE)
    del bad["cash"]
    with pytest.raises(paper_trade.CorruptStateError, match="cash"):
        paper_trade.validate_state(bad)


def test_wrong_type_is_rejected():
    bad = dict(GOOD_PAPER_STATE, cash="lots")
    with pytest.raises(paper_trade.CorruptStateError, match="cash"):
        paper_trade.validate_state(bad)


def test_negative_cash_is_rejected():
    bad = dict(GOOD_PAPER_STATE, cash=-5.0)
    with pytest.raises(paper_trade.CorruptStateError, match="negative"):
        paper_trade.validate_state(bad)


def test_in_position_with_zero_btc_is_inconsistent():
    bad = dict(GOOD_PAPER_STATE, btc=0.0)
    with pytest.raises(paper_trade.CorruptStateError, match="btc"):
        paper_trade.validate_state(bad)


def test_non_dict_is_rejected():
    with pytest.raises(paper_trade.CorruptStateError):
        paper_trade.validate_state(["not", "a", "dict"])


def test_malformed_json_file_raises_not_resets(tmp_path, monkeypatch):
    bad_file = tmp_path / "paper_state.json"
    bad_file.write_text("{not valid json")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paper_trade, "STATE_FILE", "paper_state.json")
    with pytest.raises(paper_trade.CorruptStateError):
        paper_trade.load_state()


def test_missing_file_starts_a_genuinely_new_account(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(paper_trade, "STATE_FILE", "paper_state.json")
    state = paper_trade.load_state()
    assert state["cash"] == paper_trade.config.starting_balance
    assert state["last_candle_ts"] is None


def test_valid_experiment_state_passes():
    assert experiments.validate_experiment_state(dict(GOOD_EXPERIMENT_STATE))["trades"] == 0


def test_experiment_missing_field_is_rejected():
    bad = dict(GOOD_EXPERIMENT_STATE)
    del bad["halted"]
    with pytest.raises(experiments.CorruptStateError, match="halted"):
        experiments.validate_experiment_state(bad)


def test_experiment_malformed_json_raises_not_resets(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text("{corrupt")
    with pytest.raises(experiments.CorruptStateError):
        experiments.load_experiment_state(str(state_path), forming_open=100.0)


def test_experiment_missing_file_starts_fresh(tmp_path):
    state_path = tmp_path / "state.json"
    state = experiments.load_experiment_state(str(state_path), forming_open=100.0)
    assert state["cash"] == 1000.0
    assert state["start_price"] == 100.0


def test_valid_experiment_state_on_disk_is_loaded_unchanged(tmp_path):
    state_path = tmp_path / "state.json"
    state_path.write_text(json.dumps(GOOD_EXPERIMENT_STATE))
    loaded = experiments.load_experiment_state(str(state_path), forming_open=999.0)
    assert loaded["starting_cash"] == 1000.0
    assert loaded["started_at"] == GOOD_EXPERIMENT_STATE["started_at"]
