"""Predict podium probabilities for one race and save them as JSON plus an HTML page.

Usage: python -m f1pred.predict 2024 16
       python -m f1pred.predict 2026 18 --grid ANT,RUS,VER,...
       python -m f1pred.predict 2026 18 --start-grid ANT,VER,RUS,...
If the race is already in data/raw/results.csv it is a backtest (the actual result
is stored next to the prediction). Otherwise the qualifying result is fetched from
Jolpica and used as the grid. If Jolpica does not have it yet, pass the grid
yourself with --grid (driver codes in qualifying order). Training always uses races
strictly before the target race.
--start-grid is the official starting order after penalties (pit-lane starters last).
Without it the starting grid is the qualifying order, so grid penalties are not reflected.
"""
import argparse
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
import shap

from . import jolpica
from .config import EVALUATION, PREDICTIONS, RESULTS_CSV
from .evaluate import Blend
from .fetch import _code, _seconds
from .features import FEATURES, build

MIN_TRAIN_RACES = 5


def predict_frame(df: pd.DataFrame, race_id: int, min_train_races: int = MIN_TRAIN_RACES) -> pd.DataFrame:
    """df is the output of features.build(). Returns the target race rows with p_podium and reasons."""
    train = df[(df["race_id"] < race_id) & df["position"].notna()]
    test = df[df["race_id"] == race_id].copy()
    if train["race_id"].nunique() < min_train_races:
        raise ValueError(f"need at least {min_train_races} earlier races, have {train['race_id'].nunique()}")
    if test.empty:
        raise ValueError(f"race {race_id} not found")

    med = train[FEATURES].median(numeric_only=True)
    Xtr, Xte = train[FEATURES].fillna(med), test[FEATURES].fillna(med)
    model = Blend().fit(Xtr, train["podium"])
    test["p_podium"] = model.predict_proba(Xte)[:, 1]
    # a second model for the chance of winning; exactly one driver wins, so the field is scaled to sum to 1.
    # Walk-forward Brier 0.030 against 0.047 for a constant guess
    win = Blend().fit(Xtr, (train["position"] == 1).astype(int))
    raw = win.predict_proba(Xte)[:, 1]
    test["p_win"] = raw / raw.sum()

    contrib = shap.TreeExplainer(model.xgb).shap_values(Xte)  # reasons explain the tree half of the blend
    reasons = []
    for i in range(len(test)):
        order = np.argsort(-np.abs(contrib[i]))[:3]
        reasons.append([{"feature": FEATURES[j], "value": None if pd.isna(Xte.iloc[i, j]) else round(float(Xte.iloc[i, j]), 3),
                         "shap": round(float(contrib[i][j]), 3)} for j in order])
    test["reasons"] = reasons
    return test.sort_values("p_podium", ascending=False)


def _start_positions(codes, start_grid):
    """Starting position per driver code from the official grid, or None to use qualifying."""
    if not start_grid:
        return None
    if len(set(start_grid)) != len(start_grid):
        raise ValueError("--start-grid lists a driver more than once")
    missing, extra = set(codes) - set(start_grid), set(start_grid) - set(codes)
    if missing or extra:
        raise ValueError(f"--start-grid must list the same drivers as qualifying; missing {sorted(missing)}, unknown {sorted(extra)}")
    return {c: i + 1 for i, c in enumerate(start_grid)}


def _upcoming_rows(year: int, rnd: int, results: pd.DataFrame, grid=None, start_grid=None) -> pd.DataFrame:
    """Rows for a race that has not been run: one per driver. Qualifying sets quali_pos;
    the starting grid is the qualifying order unless start_grid (official, with penalties) is given."""
    sched = jolpica.get(f"{year}/{rnd}", year)["RaceTable"]["Races"]
    if not sched:
        raise ValueError(f"{year} round {rnd} is not on the calendar")
    event, location = sched[0]["raceName"], sched[0]["Circuit"]["Location"]["locality"]

    if grid:
        last = results.sort_values(["year", "round"]).drop_duplicates("Abbreviation", keep="last")
        team_of = dict(zip(last["Abbreviation"], last["TeamName"]))
        unknown = [c for c in grid if c not in team_of]
        if unknown:
            raise ValueError(f"no team known for {unknown}; check the driver codes")
        quali = [{"code": c, "team": team_of[c], "pos": i + 1, "time": np.nan} for i, c in enumerate(grid)]
    else:
        races = jolpica.get(f"{year}/{rnd}/qualifying", year, limit=jolpica.PAGE)["RaceTable"]["Races"]
        if not races:
            raise ValueError(f"Qualifying for {year} round {rnd} is not on Jolpica yet. "
                             "Pass the grid yourself: --grid CODE1,CODE2,... (qualifying order)")
        quali = []
        for x in races[0]["QualifyingResults"]:
            times = [_seconds(x[k]) for k in ("Q3", "Q2", "Q1") if x.get(k)]
            quali.append({"code": _code(x["Driver"]), "team": x["Constructor"]["name"],
                          "pos": int(x["position"]), "time": times[0] if times else np.nan})

    start = _start_positions([q["code"] for q in quali], start_grid)
    return pd.DataFrame({
        "Abbreviation": [q["code"] for q in quali], "TeamName": [q["team"] for q in quali],
        "GridPosition": [start[q["code"]] if start else q["pos"] for q in quali], "Position": np.nan,
        "Status": "Unknown", "Points": 0.0,
        "quali_pos": [q["pos"] for q in quali], "quali_time_s": [q["time"] for q in quali],
        "year": year, "round": rnd, "event": event, "location": location})


def run(year: int, rnd: int, grid=None, start_grid=None) -> dict:
    results = pd.read_csv(RESULTS_CSV)
    race_id = year * 100 + rnd
    done = ((results["year"] == year) & (results["round"] == rnd)).any()
    if not done:
        results = pd.concat([results, _upcoming_rows(year, rnd, results, grid, start_grid)], ignore_index=True)

    df = build(results)
    out = predict_frame(df, race_id)
    first = out.iloc[0]
    payload = {
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "year": year, "round": rnd, "event": str(first["event"]), "location": str(first["location"]),
        "mode": "backtest" if done else "upcoming",
        "model": "blend",
        "official_grid": bool(start_grid) and not done,
        "trained_on_races": int(df[(df["race_id"] < race_id) & df["position"].notna()]["race_id"].nunique()),
        "evaluation": json.loads(EVALUATION.read_text()) if EVALUATION.exists() else None,
        "drivers": [{
            "driver": r["Abbreviation"], "team": r["TeamName"],
            "grid": None if pd.isna(r["grid"]) else int(r["grid"]),
            "p_podium": round(float(r["p_podium"]), 4),
            "p_win": round(float(r["p_win"]), 4),
            "actual_position": None if (not done or pd.isna(r["position"])) else int(r["position"]),
            "status": str(r["Status"]) if done else None,
            "reasons": r["reasons"]} for _, r in out.iterrows()],
    }
    PREDICTIONS.mkdir(parents=True, exist_ok=True)
    path = PREDICTIONS / f"{year}_R{rnd:02d}.json"
    path.write_text(json.dumps(payload, indent=2))
    from .report import write_report
    page = write_report(payload)
    print(f"saved {path}\nsaved {page}")
    for d in payload["drivers"][:3]:
        print(f"  {d['driver']:<4} {d['team']:<20} P(podium)={d['p_podium']:.3f}")
    return payload


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("year", type=int)
    ap.add_argument("round", type=int)
    ap.add_argument("--grid", help="driver codes in qualifying order, comma separated")
    ap.add_argument("--start-grid", help="driver codes in the official starting order (after penalties), comma separated")
    a = ap.parse_args()
    split = lambda v: v.upper().split(",") if v else None
    run(a.year, a.round, split(a.grid), split(a.start_grid))
