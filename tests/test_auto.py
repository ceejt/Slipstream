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
