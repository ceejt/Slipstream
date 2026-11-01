"""Leak-free feature building.

Rule: a feature for race N may only use information known before race N starts.
Rolling stats are computed on earlier races only (shift before aggregating).
There are no weather features yet. Add them from a forecast, not from observed
race-day weather, so training and prediction see the same kind of input.
"""
import numpy as np
import pandas as pd

from .config import CIRCUITS_CSV, FORM_WINDOW, RESULTS_CSV

FEATURES = [
    "grid", "quali_pos", "quali_gap_s", "grid_penalty",
    "driver_form_pos", "driver_dnf_rate", "team_form_pts", "team_dnf_rate",
    "circuit_dnf_rate", "circuit_pos_gain",
    "altitude_m", "is_street",
]


def _prior_rolling(df, group, col, window=None):
    """Mean of `col` over earlier races only (current race excluded)."""
    def f(s):
        s = s.shift(1)
        return s.rolling(window, min_periods=1).mean() if window else s.expanding().mean()
    return df.groupby(group)[col].transform(f)


def build(results=None, races=None, circuits=None) -> pd.DataFrame:
    # races is unused until forecast features exist; kept so callers stay stable
    results = pd.read_csv(RESULTS_CSV) if results is None else results.copy()
    circuits = pd.read_csv(CIRCUITS_CSV) if circuits is None else circuits.copy()

    df = results.merge(circuits[["location", "altitude_m", "is_street"]], on="location", how="left")
    df = df.sort_values(["year", "round"]).reset_index(drop=True)
    df["race_id"] = df["year"] * 100 + df["round"]

    df["position"] = pd.to_numeric(df["Position"], errors="coerce")
    df["grid"] = pd.to_numeric(df["GridPosition"], errors="coerce").replace(0, 20)  # 0 = pit lane
    # places lost between qualifying and the start: positive means a penalty or a car sent to the pit lane
    df["grid_penalty"] = df["grid"] - df["quali_pos"]
    df["podium"] = (df["position"] <= 3).astype(int)
    df["dnf"] = (~df["Status"].astype(str).str.contains("Finished|Lap", regex=True)).astype(int)
    df["pos_gain"] = df["grid"] - df["position"]
    df["points"] = pd.to_numeric(df["Points"], errors="coerce").fillna(0)

    pole = df.groupby("race_id")["quali_time_s"].transform("min")
    df["quali_gap_s"] = df["quali_time_s"] - pole

    # per-driver and per-team history, strictly before the current race
    df["driver_form_pos"] = _prior_rolling(df, "Abbreviation", "position", FORM_WINDOW)
    df["driver_dnf_rate"] = _prior_rolling(df, "Abbreviation", "dnf")
    team_race = df.groupby(["TeamName", "race_id"], as_index=False).agg(
        pts=("points", "sum"), dnf=("dnf", "mean"))
    team_race["team_form_pts"] = _prior_rolling(team_race, "TeamName", "pts", FORM_WINDOW)
    team_race["team_dnf_rate"] = _prior_rolling(team_race, "TeamName", "dnf")
    df = df.merge(team_race[["TeamName", "race_id", "team_form_pts", "team_dnf_rate"]],
                  on=["TeamName", "race_id"], how="left")

    # per-circuit history, strictly before the current race
    circ_race = df.groupby(["location", "race_id"], as_index=False).agg(
        circuit_dnf_rate_raw=("dnf", "mean"),
        circuit_pos_gain_raw=("pos_gain", lambda s: s.abs().mean()))
    circ_race = circ_race.sort_values("race_id")
    for raw, out in [("circuit_dnf_rate_raw", "circuit_dnf_rate"),
                     ("circuit_pos_gain_raw", "circuit_pos_gain")]:
        circ_race[out] = _prior_rolling(circ_race, "location", raw)
    df = df.merge(circ_race[["location", "race_id", "circuit_dnf_rate", "circuit_pos_gain"]],
                  on=["location", "race_id"], how="left")
    return df
