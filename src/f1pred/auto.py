"""Automatic race weekend job: decide what to do now. It never runs git.

The job is meant to be started every 20 minutes. Outside a race weekend it does nothing.
Inside one it makes the prediction once, after qualifying and before the race start, and
adds the result once, after the race. This file holds the decision (which race is live
and which step is due) and the runner for the steps. A step is one of a fixed list of
`python -m f1pred...` commands; nothing else can be run. All times are UTC.
"""
import fcntl
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from .config import DATA, ROOT

LOCK = DATA / "auto.lock"

# The only commands the job can run: step name -> (module, number of integer arguments, timeout in seconds).
STEPS = {
    "fetch": ("f1pred.fetch", 0, 900),
    "strategy": ("f1pred.lab.strategy", 0, 1800),
    "predict": ("f1pred.predict", 2, 600),
    "lab_report": ("f1pred.lab.report", 0, 120),
    "outcome": ("f1pred.outcome", 2, 300),
}


def command(step, *args):
    """The argument list for one allowed step. Arguments must be whole numbers (year, round)."""
    if step not in STEPS:
        raise ValueError(f"step {step!r} is not allowed")
    module, n_args, _ = STEPS[step]
    if len(args) != n_args or not all(type(a) is int and a >= 0 for a in args):
        raise ValueError(f"step {step!r} takes {n_args} whole-number arguments, got {args!r}")
    return [sys.executable, "-m", module, *(str(a) for a in args)]


def run_step(step, *args):
    """Run one allowed step from the project folder, without a shell. Returns (ok, last lines of its output).
    A step that runs past its timeout is stopped and counts as failed."""
    cmd = command(step, *args)
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=STEPS[step][2])
    except subprocess.TimeoutExpired:
        return False, f"{step} stopped after {STEPS[step][2]} s"
    tail = "\n".join((p.stdout + p.stderr).strip().splitlines()[-5:])
    return p.returncode == 0, tail


@contextmanager
def lock(path=LOCK):
    """Hold the job's lock file. Yields True if this run holds it, False if another run does.
    The system drops the lock when the process ends, so a crash cannot leave it stuck."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        try:
            fcntl.flock(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            yield False
            return
        yield True

QUALI_LENGTH = timedelta(hours=1)    # no point asking Jolpica for the grid before qualifying ends
GRID_GRACE = timedelta(hours=3)      # after qualifying starts; past this, ask the user for --grid
RACE_LENGTH = timedelta(hours=3)     # a red-flagged race can run this long; no result before then
OUTCOME_WINDOW = timedelta(days=3)   # keep looking for the result this long after the race start

IDLE, PREDICT, ASK_GRID, MISSED, OUTCOME = "idle", "predict", "ask_grid", "missed", "outcome"


def _utc(day, clock):
    return datetime.fromisoformat(f"{day}T{clock.rstrip('Z')}").replace(tzinfo=timezone.utc)


def race_times(race):
    """Year, round, name and the two start times of a Jolpica calendar entry, or None if the race has no start time.
    If the entry has no qualifying time, qualifying is taken as one day before the race."""
    if not race.get("time"):
        return None
    start = _utc(race["date"], race["time"])
    q = race.get("Qualifying") or {}
    quali = _utc(q["date"], q["time"]) if q.get("date") and q.get("time") else start - timedelta(days=1)
    return {"year": int(race["season"]), "round": int(race["round"]), "event": race["raceName"],
            "quali_utc": quali, "race_utc": start}


def find_race(calendar, now):
    """The race whose weekend window holds `now`: from the start of qualifying until
    OUTCOME_WINDOW after the race start. None between race weekends."""
    for entry in calendar:
        r = race_times(entry)
        if r and r["quali_utc"] <= now < r["race_utc"] + OUTCOME_WINDOW:
            return r
    return None


def decide(race, now, has_prediction, has_outcome, quali_ready, state):
    """The step due now for `race`.

    has_prediction: a pre-race prediction is saved. has_outcome: the result is saved.
    quali_ready: a function that asks Jolpica whether qualifying is published; called only when needed.
    state: this race's flags from the state file ("grid_asked", "missed"), so a notice is sent once.
    A prediction is never due once the race has started.
    """
    if now < race["race_utc"]:
        if has_prediction or now < race["quali_utc"] + QUALI_LENGTH:
            return IDLE
        if quali_ready():
            return PREDICT
        if now >= race["quali_utc"] + GRID_GRACE and not state.get("grid_asked"):
            return ASK_GRID
        return IDLE
    if not has_prediction:
        return IDLE if state.get("missed") else MISSED
    if has_outcome or now < race["race_utc"] + RACE_LENGTH:
        return IDLE
    return OUTCOME
