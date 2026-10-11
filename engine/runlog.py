"""
Step-by-step run log, the data source for the research city's employees.

Each scheduled run (hourly paper trade, daily re-learn) declares the steps
it plans to take and which employee owns each one. As steps execute, their
real start/end times, status, and outputs are recorded. Steps the run never
reached keep the status "not_reached", so the city can't show work that
didn't happen.

Files written (committed back to GitHub by the workflows):
    runlog/latest_<run_type>.json      the most recent run, every step
    runlog/<run_type>_history.jsonl    one summary line per run, last 200
"""
import json
import math
import os
from contextlib import contextmanager
from datetime import datetime, timezone

RUNLOG_DIR = "runlog"
HISTORY_LIMIT = 200


def _now():
    return datetime.now(timezone.utc).isoformat()


def jsonable(value):
    """Convert numpy/pandas scalars, timestamps, and NaN into plain JSON values."""
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if hasattr(value, "item"):  # numpy scalar
        value = value.item()
    if isinstance(value, float):
        return None if math.isnan(value) or math.isinf(value) else value
    if isinstance(value, int):
        return value
    return str(value)


class _Step:
    def __init__(self, record):
        self.record = record

    def output(self, **values):
        self.record["outputs"].update(jsonable(values))


class RunLogger:
    def __init__(self, run_type, planned_steps, run_dir=RUNLOG_DIR):
        """planned_steps: list of (step_id, employee_id, description) tuples."""
        self.run_type = run_type
        self.run_dir = run_dir
        self.run = {
            "run_type": run_type,
            "run_id": f"{run_type}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
            "started_at": _now(),
            "finished_at": None,
            "status": "running",
            "summary": None,
            "trigger": os.environ.get("GITHUB_EVENT_NAME", "local"),
            "steps": [
                {"step": sid, "employee": emp, "description": desc, "status": "not_reached",
                 "started_at": None, "finished_at": None, "duration_ms": None,
                 "outputs": {}, "error": None}
                for sid, emp, desc in planned_steps
            ],
        }
        self._by_id = {s["step"]: s for s in self.run["steps"]}

    @contextmanager
    def step(self, step_id):
        record = self._by_id[step_id]
        record["status"] = "running"
        record["started_at"] = _now()
        start = datetime.now(timezone.utc)
        try:
            yield _Step(record)
            record["status"] = "done"
        except Exception as e:
            record["status"] = "error"
            record["error"] = f"{type(e).__name__}: {e}"
            self.run["status"] = "error"
            self.run["summary"] = f"Failed at step '{step_id}': {record['error']}"
            raise
        finally:
            record["finished_at"] = _now()
            record["duration_ms"] = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

    def skip_remaining(self, reason):
        for record in self.run["steps"]:
            if record["status"] == "not_reached":
                record["status"] = "skipped"
                record["error"] = None
                record["outputs"] = {"reason": reason}

    def finish(self, status="done", summary=None):
        if self.run["status"] != "error":
            self.run["status"] = status
            self.run["summary"] = summary

    def write(self):
        self.run["finished_at"] = _now()
        if self.run["status"] == "running":
            # the process stopped without finish() or an error being recorded
            self.run["status"] = "incomplete"
        os.makedirs(self.run_dir, exist_ok=True)
        latest_path = os.path.join(self.run_dir, f"latest_{self.run_type}.json")
        with open(latest_path, "w") as f:
            json.dump(self.run, f, indent=2)

        history_path = os.path.join(self.run_dir, f"{self.run_type}_history.jsonl")
        lines = []
        if os.path.exists(history_path):
            with open(history_path) as f:
                lines = [line for line in f.read().splitlines() if line.strip()]
        summary_line = {
            "run_id": self.run["run_id"], "started_at": self.run["started_at"],
            "finished_at": self.run["finished_at"], "status": self.run["status"],
            "summary": self.run["summary"],
        }
        lines.append(json.dumps(summary_line))
        with open(history_path, "w") as f:
            f.write("\n".join(lines[-HISTORY_LIMIT:]) + "\n")
        return latest_path
