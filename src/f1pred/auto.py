"""Automatic race weekend job: decide what to do now. It never runs git.

The job is meant to be started every 20 minutes. Outside a race weekend it does nothing.
Inside one it makes the prediction once, after qualifying and before the race start, and
adds the result once, after the race. This file holds the decision (which race is live
and which step is due), the runner for the steps and the run itself. A step is one of a
fixed list of `python -m f1pred...` commands; nothing else can be run. What has been done
for each race is kept in data/auto_state.json. All times are UTC.

The job tells the user what happened with a macOS banner and writes the details, with the
commit commands to run by hand, to data/auto_status.txt. It commits and pushes nothing.

Usage: python -m f1pred.auto
"""
import fcntl
import json
import subprocess
import sys
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

from . import jolpica
from .config import DATA, NEXT_RACE, OUTCOMES, PREDICTIONS, ROOT

LOCK = DATA / "auto.lock"
STATE = DATA / "auto_state.json"
STATUS = DATA / "auto_status.txt"
MAX_FAILURES = 3   # failed runs of the prediction or of the result, per race, before the job stops trying
MIN_DRIVERS = 10   # fewer rows than this means Jolpica does not have the full session yet

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


def load_state(path=STATE):
    """What the job has done so far, per race. Empty if the file is missing or unreadable."""
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def save_state(state, path=STATE):
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(path)


def _now():
    return datetime.now(timezone.utc)


def calendar(year):
    return jolpica.get(str(year), year, limit=jolpica.PAGE)["RaceTable"]["Races"]


def _published(year, rnd, kind, rows_key):
    races = jolpica.get(f"{year}/{rnd}/{kind}", year, limit=jolpica.PAGE)["RaceTable"]["Races"]
    return bool(races) and len(races[0].get(rows_key, [])) >= MIN_DRIVERS


def quali_published(year, rnd):
    return _published(year, rnd, "qualifying", "QualifyingResults")


def results_published(year, rnd):
    return _published(year, rnd, "results", "Results")


def has_prediction(year, rnd):
    """A prediction made before the race is saved. A backtest of the same race does not count."""
    try:
        return json.loads((PREDICTIONS / f"{year}_R{rnd:02d}.json").read_text())["mode"] == "upcoming"
    except (OSError, ValueError, KeyError):
        return False


def has_outcome(year, rnd):
    return (OUTCOMES / f"{year}_R{rnd:02d}.json").exists()


def _strategy_is_for(year, rnd):
    """The pit strategy step plans the race named in data/next_race.json. True if that is this race."""
    try:
        nxt = json.loads(NEXT_RACE.read_text())
        return (nxt["year"], nxt["round"]) == (year, rnd)
    except (OSError, ValueError, KeyError, TypeError):
        return False


def prediction_pass(race):
    """Fetch, plan the pit stops, predict, rebuild the Race lab page. Returns (ok, notes).

    The pit plans run before the prediction because saving a prediction moves data/next_race.json
    on to the following race. The pit plans and the lab page are extras: if one fails the pass
    still counts, with a note. The prediction is not started once the race has begun.
    """
    year, rnd = race["year"], race["round"]
    ok, out = run_step("fetch")
    if not ok:
        return False, [f"fetch failed: {out}"]
    notes = []
    if not _strategy_is_for(year, rnd):
        notes.append("pit plans skipped: data/next_race.json names another race")
    elif _now() + timedelta(seconds=STEPS["strategy"][2]) >= race["race_utc"]:
        notes.append("pit plans skipped: too close to the race start")
    else:
        ok, out = run_step("strategy")
        if not ok:
            notes.append(f"pit plans not updated: {out}")
    if _now() >= race["race_utc"]:
        return False, notes + ["the race started before the prediction could run"]
    ok, out = run_step("predict", year, rnd)
    if not ok or not has_prediction(year, rnd):
        return False, notes + [f"predict failed: {out}"]
    ok, out = run_step("lab_report")
    if not ok:
        notes.append(f"Race lab page not rebuilt: {out}")
    return True, notes


def outcome_pass(race):
    """Fetch, then add the result beside the saved prediction. Returns (ok, notes)."""
    year, rnd = race["year"], race["round"]
    for step, args in (("fetch", ()), ("outcome", (year, rnd))):
        ok, out = run_step(step, *args)
        if not ok:
            return False, [f"{step} failed: {out}"]
    if not has_outcome(year, rnd):
        return False, [f"outcome saved no result: {out}"]
    return True, []


def tick(now, cal, state):
    """One run of the job. Changes `state` in place and returns what happened, or None if nothing did.

    The return value is a dict with "kind" (ask_grid, missed, predicted, scored, failed, gave_up),
    "race" and "notes". After MAX_FAILURES failed runs of a pass the job stops trying it for that race.
    """
    race = find_race(cal, now)
    if race is None:
        return None
    year, rnd = race["year"], race["round"]
    s = state.setdefault(f"{year}_R{rnd:02d}", {})
    action = decide(race, now, has_prediction(year, rnd), has_outcome(year, rnd),
                    lambda: quali_published(year, rnd), s)
    if action == IDLE:
        return None
    if action in (ASK_GRID, MISSED):
        s["grid_asked" if action == ASK_GRID else "missed"] = True
        return {"kind": action, "race": race, "notes": []}
    failures = f"{action}_failures"
    if s.get(failures, 0) >= MAX_FAILURES:
        return None
    if action == OUTCOME and not results_published(year, rnd):
        return None
    ok, notes = prediction_pass(race) if action == PREDICT else outcome_pass(race)
    if ok:
        s[f"{action}_utc"] = now.isoformat(timespec="seconds")
        return {"kind": "predicted" if action == PREDICT else "scored", "race": race, "notes": notes}
    s[failures] = s.get(failures, 0) + 1
    return {"kind": "gave_up" if s[failures] >= MAX_FAILURES else "failed", "step": action,
            "race": race, "notes": notes}


def _when(t):
    return f"{t:%a %d %b %H:%M} UTC ({t.astimezone():%a %H:%M} local time)"


def report(event, now):
    """The banner line and the full status text for what `tick` returned."""
    race, kind = event["race"], event["kind"]
    year, rnd = race["year"], race["round"]
    gp, tag, start = race["event"].replace("Grand Prix", "GP"), f"{year}_R{rnd:02d}", _when(race["race_utc"])
    page = f"reports/{tag}.html reports/index.html data/next_race.json"
    if kind == "predicted":
        banner = f"{gp}: prediction saved. Commit and push before the race start. Penalties? Use --start-grid."
        body = [
            f"The pre-race prediction is saved. The race starts {start}.",
            "",
            "If the official starting grid differs from qualifying (penalties), run this again before the start:",
            f"  python -m f1pred.predict {year} {rnd} --start-grid CODE,CODE,...   (official starting order)",
            "",
            "Then commit and push before the race start, so the commit time proves the prediction came first:",
            f"  git add data/predictions/{tag}.json {page}",
            f'  git commit -m "Add the pre-race prediction for the {gp}"',
            "  git add data/strategy.json reports/lab/index.html",
            f'  git commit -m "Update the Race lab pit plans for the {gp} with the qualifying grid"',
            "  git push",
            "The second commit has nothing to add if the pit plans were skipped (see the notes).",
        ]
    elif kind == "scored":
        banner = f"{gp}: result added to the prediction. Commit and push when ready."
        body = [
            "The result is saved beside the prediction and the page is rebuilt.",
            "",
            f"  git add data/outcomes/{tag}.json {page}",
            f'  git commit -m "Add the result of the {gp}"',
            "  git push",
            "",
            "Still by hand after a race: evaluate, lab.fetch, lab.season, lab.strategy, lab.report.",
        ]
    elif kind == ASK_GRID:
        banner = f"{gp}: qualifying is not on Jolpica yet. Run predict with --grid before the race start."
        body = [
            f"Qualifying is still not published. The race starts {start}.",
            "To be sure of a pre-race prediction, type the qualifying order yourself before the start:",
            f"  python -m f1pred.predict {year} {rnd} --grid CODE,CODE,...   (qualifying order)",
            "Add --start-grid CODE,CODE,... if the official starting grid differs (penalties).",
            "The job still predicts by itself if Jolpica publishes qualifying before the start.",
        ]
    elif kind == MISSED:
        banner = f"{gp}: the race started with no prediction. None will be made."
        body = [
            f"The race started {start} and no pre-race prediction was saved, so the job makes none.",
            "It can only be added as a labelled backtest, once the result is in:",
            "  python -m f1pred.fetch",
            f"  python -m f1pred.predict {year} {rnd}",
        ]
    else:
        what = "prediction" if event["step"] == PREDICT else "result"
        by_hand = (f"python -m f1pred.predict {year} {rnd}   (add --grid CODE,CODE,... if qualifying is not on Jolpica)"
                   if event["step"] == PREDICT else f"python -m f1pred.outcome {year} {rnd}")
        if kind == "gave_up":
            banner = f"{gp}: the {what} run failed {MAX_FAILURES} times. The job has stopped trying. Run it by hand."
            body = [f"The {what} run failed {MAX_FAILURES} times and the job will not try again for this race."]
        else:
            banner = f"{gp}: the {what} run failed. The job will try again on its next run."
            body = [f"The {what} run failed. The job tries again on its next run, up to {MAX_FAILURES} times in all."]
        body += ["To run it by hand:", "  python -m f1pred.fetch", f"  {by_hand}"]
        if event["step"] == PREDICT:
            body.append(f"A prediction only counts as pre-race before the start, {start}.")
    notes = ["", "Notes:"] + [f"- {n}" for n in event["notes"]] if event["notes"] else []
    head = ["Slipstream automatic job", f"Written {_when(now)}", f"{race['event']}, {year} round {rnd}", ""]
    return banner, "\n".join(head + body + notes) + "\n"


def notify(text, title="Slipstream"):
    """Show a macOS banner. Returns False if it could not be shown; never raises.
    The text is passed as an argument, so nothing in it is read as script."""
    script = ["-e", "on run argv", "-e", "display notification (item 1 of argv) with title (item 2 of argv)",
              "-e", "end run"]
    try:
        return subprocess.run(["osascript", *script, text, title], capture_output=True, timeout=15).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def main():
    with lock() as held:
        if not held:
            print("another run holds the lock; nothing done")
            return
        now, state = _now(), load_state()
        try:
            event = tick(now, calendar(now.year), state)
        except Exception as e:  # a network error here is not a failed step; the next run tries again
            print(f"run stopped: {e}")
            return
        finally:
            save_state(state)
        if event is None:
            print("nothing to do")
            return
        banner, status = report(event, now)
        STATUS.write_text(status)
        shown = notify(banner)
        print(banner if shown else f"{banner} (banner not shown; see {STATUS.name})")


if __name__ == "__main__":
    main()
