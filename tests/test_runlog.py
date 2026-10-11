import json
import numpy as np
import pandas as pd
import pytest
from engine.runlog import RunLogger, jsonable

STEPS = [("a", "emp_a", "first"), ("b", "emp_b", "second"), ("c", "emp_c", "third")]


def read_latest(tmp_path, run_type="test"):
    with open(tmp_path / f"latest_{run_type}.json") as f:
        return json.load(f)


def test_successful_run_records_every_step(tmp_path):
    log = RunLogger("test", STEPS, run_dir=str(tmp_path))
    for sid in ["a", "b", "c"]:
        with log.step(sid) as s:
            s.output(value=1)
    log.finish("done", "all good")
    log.write()

    run = read_latest(tmp_path)
    assert run["status"] == "done"
    assert [s["status"] for s in run["steps"]] == ["done", "done", "done"]
    assert all(s["started_at"] and s["finished_at"] for s in run["steps"])


def test_error_marks_the_failing_step_and_leaves_later_steps_not_reached(tmp_path):
    log = RunLogger("test", STEPS, run_dir=str(tmp_path))
    with pytest.raises(RuntimeError):
        try:
            with log.step("a"):
                pass
            with log.step("b"):
                raise RuntimeError("exchange down")
            with log.step("c"):
                pass
        finally:
            log.write()

    run = read_latest(tmp_path)
    statuses = {s["step"]: s["status"] for s in run["steps"]}
    assert statuses == {"a": "done", "b": "error", "c": "not_reached"}
    assert "exchange down" in run["steps"][1]["error"]
    assert run["status"] == "error"


def test_skip_remaining_marks_unrun_steps_skipped_with_reason(tmp_path):
    log = RunLogger("test", STEPS, run_dir=str(tmp_path))
    with log.step("a"):
        pass
    log.skip_remaining("no new candle")
    log.finish("skipped", "no new candle")
    log.write()

    run = read_latest(tmp_path)
    assert [s["status"] for s in run["steps"]] == ["done", "skipped", "skipped"]
    assert run["steps"][2]["outputs"]["reason"] == "no new candle"


def test_run_that_never_finishes_is_marked_incomplete(tmp_path):
    log = RunLogger("test", STEPS, run_dir=str(tmp_path))
    with log.step("a"):
        pass
    log.write()
    assert read_latest(tmp_path)["status"] == "incomplete"


def test_history_is_capped(tmp_path, monkeypatch):
    monkeypatch.setattr("engine.runlog.HISTORY_LIMIT", 3)
    for _ in range(5):
        log = RunLogger("test", STEPS, run_dir=str(tmp_path))
        log.finish("done")
        log.write()
    lines = (tmp_path / "test_history.jsonl").read_text().strip().splitlines()
    assert len(lines) == 3


def test_jsonable_handles_numpy_pandas_and_nan():
    out = jsonable({"f": np.float64(1.5), "i": np.int64(3), "nan": float("nan"),
                    "ts": pd.Timestamp("2026-01-01 10:00"), "b": np.bool_(True)})
    assert out == {"f": 1.5, "i": 3, "nan": None, "ts": "2026-01-01 10:00:00", "b": True}
    json.dumps(out)
