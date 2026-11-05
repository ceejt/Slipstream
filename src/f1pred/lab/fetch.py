"""Download laps, stints, pit stops and safety car events for every race in data/raw/races.csv.

Usage: python -m f1pred.lab.fetch
Writes data/raw/lab/{laps,stints,pits,events}.csv. Rows carry year and round, so they join
to results.csv. Races OpenF1 does not have are skipped and listed.
"""
import pandas as pd

from ..config import RACES_CSV, RAW
from . import openf1

LAB = RAW / "lab"


def _sessions(year):
    return [s for s in openf1.get("sessions", year=year, session_name="Race") if not s.get("is_cancelled")]


def _race_key(races):
    """Map (year, round) to an OpenF1 session_key by matching the race date."""
    out = {}
    for year in sorted(races["year"].unique()):
        by_date = {s["date_start"][:10]: s["session_key"] for s in _sessions(int(year))}
        for r in races[races["year"] == year].itertuples():
            if r.date in by_date:
                out[(int(r.year), int(r.round))] = by_date[r.date]
    return out


def run():
    races = pd.read_csv(RACES_CSV)
    races = races[races["year"] >= 2023]
    keys = _race_key(races)
    missing = [(int(r.year), int(r.round)) for r in races.itertuples() if (int(r.year), int(r.round)) not in keys]
    laps, stints, pits, events = [], [], [], []
    for n, ((year, rnd), sk) in enumerate(sorted(keys.items()), 1):
        print(f"{year} R{rnd:02d} session {sk} ({n}/{len(keys)})", flush=True)
        code = {d["driver_number"]: d["name_acronym"] for d in openf1.get("drivers", session_key=sk)}
        tag = {"year": year, "round": rnd}
        for x in openf1.get("laps", session_key=sk):
            laps.append({**tag, "driver": code.get(x["driver_number"]), "lap": x["lap_number"],
                         "seconds": x["lap_duration"], "pit_out": bool(x["is_pit_out_lap"])})
        for x in openf1.get("stints", session_key=sk):
            stints.append({**tag, "driver": code.get(x["driver_number"]), "stint": x["stint_number"],
                           "lap_start": x["lap_start"], "lap_end": x["lap_end"],
                           "compound": x["compound"], "tyre_age_start": x["tyre_age_at_start"]})
        for x in openf1.get("pit", session_key=sk):
            pits.append({**tag, "driver": code.get(x["driver_number"]), "lap": x["lap_number"],
                         "lane_s": x["lane_duration"] if x.get("lane_duration") is not None else x.get("pit_duration")})
        for x in openf1.get("race_control", session_key=sk):
            msg = (x.get("message") or "").upper()
            kind = ("safety_car" if "SAFETY CAR" in msg and "VIRTUAL" not in msg else
                    "vsc" if "VIRTUAL SAFETY CAR" in msg else
                    "red_flag" if x.get("flag") == "RED" else None)
            if kind:
                events.append({**tag, "lap": x["lap_number"], "kind": kind, "message": x.get("message")})
    LAB.mkdir(parents=True, exist_ok=True)
    for name, rows in (("laps", laps), ("stints", stints), ("pits", pits), ("events", events)):
        pd.DataFrame(rows).to_csv(LAB / f"{name}.csv", index=False)
        print(f"{name}: {len(rows)} rows")
    if missing:
        print("not found on OpenF1:", missing)


if __name__ == "__main__":
    run()
