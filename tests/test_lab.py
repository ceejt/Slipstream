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
