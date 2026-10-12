import pandas as pd
import pytest
from engine.history import extend_history, fetch_binance_closed_candles, COLUMNS

HOUR = pd.Timedelta(hours=1)


def write_history(path, start, n, close=100.0):
    ts = pd.date_range(start, periods=n, freq="h")
    pd.DataFrame({"timestamp": ts, "open": close, "high": close, "low": close,
                  "close": close, "volume": 1.0})[COLUMNS].to_csv(path, index=False)


def fake_fetch_from(frame):
    def fetch(start_ms, now_ms=None):
        start = pd.to_datetime(start_ms, unit="ms")
        return frame[frame["timestamp"] >= start].reset_index(drop=True)
    return fetch


def test_appends_new_candles_and_replaces_the_possibly_partial_last_one(tmp_path):
    path = tmp_path / "h.csv"
    write_history(path, "2026-01-01 00:00", 5, close=100.0)  # last stored: 04:00
    fresh = pd.DataFrame({"timestamp": pd.date_range("2026-01-01 04:00", periods=4, freq="h")})
    for c in ["open", "high", "low", "volume"]:
        fresh[c] = 1.0
    fresh["close"] = [111.0, 112.0, 113.0, 114.0]  # 04:00 final close differs from the stored partial one

    result = extend_history(str(path), fetch=fake_fetch_from(fresh))
    out = pd.read_csv(path, parse_dates=["timestamp"])

    assert result["appended"] == 3
    assert result["replaced"] == 1
    assert len(out) == 8
    assert out["timestamp"].is_monotonic_increasing and out["timestamp"].is_unique
    assert out.loc[out["timestamp"] == pd.Timestamp("2026-01-01 04:00"), "close"].item() == 111.0


def test_nothing_new_leaves_the_file_unchanged(tmp_path):
    path = tmp_path / "h.csv"
    write_history(path, "2026-01-01 00:00", 5)
    before = path.read_text()
    empty = pd.DataFrame(columns=COLUMNS)
    result = extend_history(str(path), fetch=lambda s, n=None: empty)
    assert result["appended"] == 0
    assert path.read_text() == before


def test_network_failure_raises_and_does_not_touch_the_file(tmp_path):
    import requests
    path = tmp_path / "h.csv"
    write_history(path, "2026-01-01 00:00", 5)
    before = path.read_text()

    def broken(start_ms, now_ms=None):
        raise requests.ConnectionError("blocked")

    with pytest.raises(requests.ConnectionError):
        extend_history(str(path), fetch=broken)
    assert path.read_text() == before


class FakeResponse:
    def __init__(self, data):
        self.data = data

    def raise_for_status(self):
        pass

    def json(self):
        return self.data


def test_fetch_skips_the_candle_that_is_still_forming():
    open_ms = int(pd.Timestamp("2026-01-01 10:00", tz="UTC").timestamp() * 1000)
    hour = 3_600_000
    klines = [
        [open_ms, "1", "2", "0.5", "1.5", "10", open_ms + hour - 1],
        [open_ms + hour, "1", "2", "0.5", "1.6", "10", open_ms + 2 * hour - 1],  # still forming
    ]
    now_ms = open_ms + hour + 20 * 60_000  # 11:20
    df = fetch_binance_closed_candles(open_ms, now_ms=now_ms, get=lambda *a, **k: FakeResponse(klines))
    assert len(df) == 1
    assert df["timestamp"].iloc[0] == pd.Timestamp("2026-01-01 10:00")
    assert df["close"].iloc[0] == 1.5
