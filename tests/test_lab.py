import numpy as np
import pandas as pd

from f1pred import report
from f1pred.lab import model
from f1pred.lab.sim import Setup, simulate


def _setup(**kw):
    base = dict(laps=40, grid=np.arange(1, 5), pace=np.array([0.0, 0.0, 0.0, 0.0]), pace_sd=0.0,
                comp_off={"SOFT": -0.1, "MEDIUM": 0.0, "HARD": 0.05}, deg={"SOFT": 0.06, "MEDIUM": 0.05, "HARD": 0.04},
                fuel=-0.05, pit_loss=22.0, pit_sd=0.0, lap_sd=0.1, p_dnf=np.zeros(4), margin=1.0,
                plans=[([20], ["MEDIUM", "HARD"])])
    base.update(kw)
    return Setup(**base)


def test_simulation_returns_a_full_classification():
    rank = simulate(_setup(), n=50, seed=1)
    assert rank.shape == (50, 4)
    assert all(sorted(r) == [1, 2, 3, 4] for r in rank)


def test_faster_car_wins_more_often_than_a_slower_one():
    rank = simulate(_setup(pace=np.array([0.0, 0.0, 0.0, -1.5]), grid=np.array([1, 2, 3, 4])), n=200, seed=2)
    assert (rank[:, 3] == 1).mean() > (rank[:, 0] == 1).mean()


def test_retired_cars_finish_last():
    s = _setup(dnf_laps=np.array([np.inf, 5, np.inf, np.inf]))
    rank = simulate(s, n=20, seed=3)
    assert (rank[:, 1] == 4).all()


def test_same_seed_gives_same_result():
    a, b = simulate(_setup(), n=20, seed=7), simulate(_setup(), n=20, seed=7)
    assert (a == b).all()


def test_fit_race_recovers_driver_and_tyre_effects():
    rng = np.random.default_rng(0)
    rows = []
    for i, d in enumerate("ABCDEFGHIJ"):
        pit = 10 + 2 * i  # drivers stop on different laps, as in a real race, so tyre age and lap number can be told apart
        for comp, start, end in [("SOFT", 2, pit), ("HARD", pit + 2, 40)]:
            for lap in range(start, end):
                age = lap - start
                t = 90 + i * 0.1 + (-0.2 if comp == "SOFT" else 0.0) + 0.05 * age - 0.04 * lap + rng.normal(0, 0.05)
                rows.append({"driver": d, "compound": comp, "age": age, "lap": lap, "seconds": t})
    f = model.fit_race(pd.DataFrame(rows))
    assert abs(f["driver_off"]["J"] - f["driver_off"]["A"] - 0.9) < 0.1
    assert abs(f["deg"]["HARD"] - 0.05) < 0.02


def test_navbar_links_both_sections_and_marks_the_current_one():
    top = report._top(current="lab", root="../")
    assert 'href="../index.html"' in top and 'href="../lab/index.html" aria-current=page' in top
    assert 'aria-current=page>Podium' not in top
    assert 'href="index.html" aria-current=page' in report._top()


def test_points_follow_finishing_position():
    from f1pred.lab.season import POINTS, _points
    assert list(_points(np.array([1, 2, 10, 11]), POINTS)) == [25, 18, 1, 0]


def test_table_splits_a_tied_title_and_orders_by_expected_points():
    from f1pred.lab.season import _table
    rows = _table(["A", "B"], {"A": 10.0, "B": 0.0}, np.array([[0.0, 10.0]] * 4))
    assert [r["name"] for r in rows][0] in ("A", "B")
    assert abs(sum(r["p_title"] for r in rows) - 1) < 1e-9 and rows[0]["p_title"] == 0.5


def test_simulation_accepts_a_grid_and_pace_per_simulation():
    s = _setup(grid=np.tile(np.arange(1, 5), (30, 1)), pace=np.zeros((30, 4)))
    assert simulate(s, n=30, seed=4).shape == (30, 4)


def test_candidate_plans_use_two_tyres_and_respect_the_minimum_stint():
    from f1pred.lab.strategy import MIN_STINT, candidates
    plans = candidates(60, 5)
    assert plans and all(len(set(c)) > 1 for _, c in plans)
    assert all(b - a >= MIN_STINT for laps, _ in plans for a, b in zip(laps, laps[1:]))


def test_forced_plan_is_followed_by_that_car_only():
    from f1pred.lab.strategy import evaluate
    s = _setup(plans=[([20], ["MEDIUM", "HARD"])])
    long_soft = evaluate(s, 0, ([38], ["SOFT", "HARD"]), 100, 1)
    assert 1 <= long_soft["position"] <= 4 and s.forced == {0: ([38], ["SOFT", "HARD"])}


def test_undercut_helps_and_overcut_does_not():
    from f1pred.lab.strategy import undercut_curve
    c = undercut_curve(_setup(laps=60), gap=1.0, shifts=(-3, 0, 3), n=300)
    assert c[-3] > 0.5 > c[3] and c[-3] > c[0]


def test_a_pitting_car_is_not_held_up_by_the_car_it_is_behind():
    # B is 1 s ahead and stops a lap before A; A stays out and should come out ahead of B, not stuck behind
    s = _setup(grid=np.array([1, 2]), pace=np.zeros(2), p_dnf=np.zeros(2), lap_sd=0.0, grid_step=1.0, laps=40,
               fixed=[([20], ["MEDIUM", "HARD"]), ([21], ["MEDIUM", "HARD"])])
    s.pit_loss = 22.0
    rank = simulate(s, n=20, seed=1)
    assert (rank[:, 1] != rank[:, 0]).all()


def _sample_forecast():
    path = {"mean": [10.0, 20.0], "low": [10.0, 15.0], "high": [10.0, 25.0]}
    row = lambda n, t: {"name": n, "team": t, "now": 10.0, "expected": 20.0, "low": 15.0, "high": 25.0, "p_title": 0.5, "path": path}
    return {"year": 2026, "after_round": 19, "races_left": 1, "simulations": 10, "remaining": [{"round": 20, "event": "Brazilian Grand Prix", "sprint": False}],
            "drivers": [row("AAA", "Mercedes"), row("BBB", "Mercedes")], "constructors": [row("Mercedes", "Mercedes")],
            "driver_title_clinched": False, "constructor_title_clinched": False}


def test_lab_chart_data_embeds_safely_and_marks_a_teammate_dashed():
    import json
    from f1pred.lab import charts
    data, css = charts.build(_sample_forecast(), None)
    d = json.loads(data.replace("<\\/", "</"))
    assert [r["dash"] for r in d["ch"]["drivers"]] == [False, True]
    assert d["ch"]["labels"] == ["Now", "Brazilian"] and ".c-AAA" in css and "prefers-color-scheme:light" in css
    assert "</script" not in data.lower()


def test_lab_page_works_with_and_without_the_forecasts():
    from f1pred.lab import report
    ev = {"races": 5, "races_fitted": 6, "wet_races_skipped": 1, "tuned_on": 2023, "simulations_per_race": 10,
          "fitted": {"compound_offset_s": {"SOFT": -0.1, "MEDIUM": 0.0, "HARD": 0.05}, "wear_s_per_lap": {"SOFT": 0.05, "MEDIUM": 0.05, "HARD": 0.04},
                     "pit_loss_s": 22.0, "fuel_and_track_s_per_lap": -0.05},
          "holdout": {k: {"races": 3, "top3_overlap": 0.6, "exact_podium": 0.2, "brier": 0.07, "logloss": 0.2}
                      for k in ("simulator", "blend", "grid logistic", "simulator + blend", "grid order")},
          "replay": {"races": 3, "spearman": 0.8, "mean_place_error": 2.0, "winner_right": 0.5},
          "replay_true_pace": {"races": 3, "spearman": 0.9, "mean_place_error": 1.0, "winner_right": 0.6},
          "brier_difference": {"simulator minus blend": {"diff": 0.01, "low": 0.0, "high": 0.02},
                               "simulator minus grid logistic": {"diff": 0.0, "low": -0.01, "high": 0.01}}}
    bare = report.render(ev)
    assert 'id="fan-root"' not in bare and 'id="checks"' in bare
    full = report.render(ev, _sample_forecast())
    assert 'id="fan-root"' in full and 'id="lab-data"' in full and 'aria-label="On this page"' in full
