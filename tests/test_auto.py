from datetime import datetime, timedelta, timezone

from f1pred import auto

QUALI = datetime(2026, 11, 21, 4, 0, tzinfo=timezone.utc)
RACE = datetime(2026, 11, 22, 4, 0, tzinfo=timezone.utc)
VEGAS = {"season": "2026", "round": "21", "raceName": "Las Vegas Grand Prix",
         "date": "2026-11-22", "time": "04:00:00Z",
         "Qualifying": {"date": "2026-11-21", "time": "04:00:00Z"}}
R = auto.race_times(VEGAS)


def _never():
    raise AssertionError("Jolpica must not be asked here")


def _decide(now, has_prediction=False, has_outcome=False, quali_ready=_never, state=None):
    return auto.decide(R, now, has_prediction, has_outcome, quali_ready, state or {})


def test_race_times_reads_both_start_times_in_utc():
    assert R == {"year": 2026, "round": 21, "event": "Las Vegas Grand Prix", "quali_utc": QUALI, "race_utc": RACE}


def test_race_times_falls_back_when_times_are_missing():
    no_quali = {k: v for k, v in VEGAS.items() if k != "Qualifying"}
    assert auto.race_times(no_quali)["quali_utc"] == RACE - timedelta(days=1)
    assert auto.race_times({k: v for k, v in VEGAS.items() if k != "time"}) is None


def test_find_race_only_inside_the_weekend_window():
    cal = [VEGAS]
    assert auto.find_race(cal, QUALI - timedelta(minutes=1)) is None
    assert auto.find_race(cal, QUALI)["round"] == 21
    assert auto.find_race(cal, RACE + auto.OUTCOME_WINDOW - timedelta(minutes=1))["round"] == 21
    assert auto.find_race(cal, RACE + auto.OUTCOME_WINDOW) is None


def test_idle_while_qualifying_is_running_without_asking_jolpica():
    assert _decide(QUALI + timedelta(minutes=30)) == auto.IDLE


def test_predict_once_qualifying_is_published():
    now = QUALI + timedelta(hours=2)
    assert _decide(now, quali_ready=lambda: True) == auto.PREDICT
    assert _decide(now, quali_ready=lambda: False) == auto.IDLE
    assert _decide(now, has_prediction=True) == auto.IDLE


def test_late_qualifying_asks_for_the_grid_once_and_still_predicts_later():
    now = QUALI + auto.GRID_GRACE
    assert _decide(now, quali_ready=lambda: False) == auto.ASK_GRID
    assert _decide(now, quali_ready=lambda: False, state={"grid_asked": True}) == auto.IDLE
    assert _decide(now, quali_ready=lambda: True, state={"grid_asked": True}) == auto.PREDICT


def test_never_predicts_after_the_race_start():
    assert _decide(RACE) == auto.MISSED
    assert _decide(RACE + timedelta(hours=5)) == auto.MISSED
    assert _decide(RACE, state={"missed": True}) == auto.IDLE


def test_outcome_is_due_after_the_race_and_only_once():
    assert _decide(RACE + timedelta(hours=1), has_prediction=True) == auto.IDLE
    assert _decide(RACE + auto.RACE_LENGTH, has_prediction=True) == auto.OUTCOME
    assert _decide(RACE + auto.RACE_LENGTH, has_prediction=True, has_outcome=True) == auto.IDLE


def test_allowlist_only_runs_f1pred_modules_with_whole_number_arguments():
    for step, (module, n_args, timeout) in auto.STEPS.items():
        cmd = auto.command(step, *[2026, 21][:n_args])
        assert cmd[:3] == [auto.sys.executable, "-m", module] and module.startswith("f1pred.")
        assert all(a.isdigit() for a in cmd[3:]) and timeout > 0
        assert "git" not in " ".join(cmd[1:])


def test_command_refuses_anything_off_the_list():
    for bad in (("git",), ("push",), ("predict",), ("predict", 2026), ("predict", 2026, "21"),
                ("predict", 2026, "--grid"), ("predict", 2026, -1), ("predict", 2026, True), ("fetch", 2026)):
        try:
            auto.command(*bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} was accepted")


def test_run_step_reports_failure_and_timeout(monkeypatch):
    monkeypatch.setitem(auto.STEPS, "fetch", ("f1pred.no_such_module", 0, 60))
    ok, tail = auto.run_step("fetch")
    assert not ok and "no_such_module" in tail

    def slow(*a, **k):
        raise auto.subprocess.TimeoutExpired(a[0], k["timeout"])
    monkeypatch.setattr(auto.subprocess, "run", slow)
    assert auto.run_step("fetch") == (False, "fetch stopped after 60 s")


def test_lock_lets_one_run_in_at_a_time(tmp_path):
    path = tmp_path / "auto.lock"
    with auto.lock(path) as first:
        with auto.lock(path) as second:
            assert first and not second
    with auto.lock(path) as again:
        assert again


class World:
    """Stands in for Jolpica, the saved files and the step runner."""

    def __init__(self, monkeypatch, fail=(), quali=True, results=True, prediction=False, strategy_race=21):
        self.ran, self.fail, self.prediction, self.outcome, self.clock = [], set(fail), prediction, False, None
        monkeypatch.setattr(auto, "run_step", self.run_step)
        monkeypatch.setattr(auto, "quali_published", lambda y, r: quali)
        monkeypatch.setattr(auto, "results_published", lambda y, r: results)
        monkeypatch.setattr(auto, "has_prediction", lambda y, r: self.prediction)
        monkeypatch.setattr(auto, "has_outcome", lambda y, r: self.outcome)
        monkeypatch.setattr(auto, "_strategy_is_for", lambda y, r: r == strategy_race)
        monkeypatch.setattr(auto, "_now", lambda: self.clock)

    def run_step(self, step, *args):
        self.ran.append((step, *args))
        if step in self.fail:
            return False, "boom"
        if step == "predict":
            self.prediction = True
        if step == "outcome":
            self.outcome = True
        return True, ""

    def tick(self, now, state):
        self.clock = self.clock or now
        return auto.tick(now, [VEGAS], state)


AFTER_QUALI = QUALI + timedelta(hours=2)


def test_tick_does_nothing_outside_a_race_weekend(monkeypatch):
    w, state = World(monkeypatch), {}
    assert w.tick(QUALI - timedelta(days=2), state) is None and state == {} and w.ran == []


def test_tick_predicts_with_the_pit_plans_first(monkeypatch):
    w, state = World(monkeypatch), {}
    event = w.tick(AFTER_QUALI, state)
    assert w.ran == [("fetch",), ("strategy",), ("predict", 2026, 21), ("lab_report",)]
    assert event["kind"] == "predicted" and event["notes"] == []
    assert state["2026_R21"]["predict_utc"] == "2026-11-21T06:00:00+00:00"
    assert w.tick(AFTER_QUALI + timedelta(minutes=20), state) is None and len(w.ran) == 4


def test_failed_extras_do_not_block_the_prediction(monkeypatch):
    w = World(monkeypatch, fail={"strategy", "lab_report"})
    event = w.tick(AFTER_QUALI, {})
    assert event["kind"] == "predicted" and len(event["notes"]) == 2 and ("predict", 2026, 21) in w.ran
    w = World(monkeypatch, strategy_race=22)
    assert "skipped" in w.tick(AFTER_QUALI, {})["notes"][0] and ("strategy",) not in w.ran


def test_no_prediction_if_the_race_starts_during_the_pass(monkeypatch):
    w = World(monkeypatch)
    w.clock = RACE - timedelta(minutes=10)
    assert "too close" in w.tick(RACE - timedelta(minutes=10), {})["notes"][0] and ("strategy",) not in w.ran
    w = World(monkeypatch)
    w.clock = RACE
    event = w.tick(RACE - timedelta(minutes=1), {})
    assert event["kind"] == "failed" and not any(step[0] == "predict" for step in w.ran)


def test_job_stops_trying_after_three_failed_runs(monkeypatch):
    w, state = World(monkeypatch, fail={"predict"}), {}
    kinds = [w.tick(AFTER_QUALI + timedelta(minutes=20 * i), state)["kind"] for i in range(3)]
    assert kinds == ["failed", "failed", "gave_up"] and state["2026_R21"]["predict_failures"] == 3
    ran = len(w.ran)
    assert w.tick(AFTER_QUALI + timedelta(hours=2), state) is None and len(w.ran) == ran


def test_notices_are_recorded_so_they_fire_once(monkeypatch):
    w, state = World(monkeypatch, quali=False), {}
    assert w.tick(QUALI + auto.GRID_GRACE, state)["kind"] == "ask_grid"
    assert w.tick(QUALI + auto.GRID_GRACE + timedelta(minutes=20), state) is None
    assert w.tick(RACE, state)["kind"] == "missed" and w.tick(RACE + timedelta(minutes=20), state) is None
    assert w.ran == []


def test_result_is_added_once_jolpica_has_it(monkeypatch):
    late = RACE + auto.RACE_LENGTH
    w = World(monkeypatch, results=False, prediction=True)
    assert w.tick(late, {}) is None and w.ran == []
    w, state = World(monkeypatch, prediction=True), {}
    assert w.tick(late, state)["kind"] == "scored" and w.ran == [("fetch",), ("outcome", 2026, 21)]
    assert w.tick(late + timedelta(minutes=20), state) is None and len(w.ran) == 2


def test_state_file_round_trip_and_unreadable_file(tmp_path):
    path = tmp_path / "auto_state.json"
    assert auto.load_state(path) == {}
    auto.save_state({"2026_R21": {"missed": True}}, path)
    assert auto.load_state(path) == {"2026_R21": {"missed": True}}
    path.write_text("{not json")
    assert auto.load_state(path) == {}
