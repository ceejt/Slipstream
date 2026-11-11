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
