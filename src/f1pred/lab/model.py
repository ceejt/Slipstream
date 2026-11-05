"""Fit what the simulator needs from lap data, using earlier races only.

Per race: each driver's pace, the offset and wear rate of each tyre compound, the fuel and track
evolution slope, and the time lost in the pits. Across races: a forecast of each driver's pace from
recent form and the qualifying gap. Everything is in seconds per lap.
"""
import numpy as np
import pandas as pd

from ..config import RAW, RESULTS_CSV

LAB = RAW / "lab"
DRY = ["SOFT", "MEDIUM", "HARD"]
FORM = 5  # races of history behind a driver or team pace
NEUTRAL = 1.07  # a lap is neutralised when the field median is this much slower than the race median


def load():
    return {n: pd.read_csv(LAB / f"{n}.csv") for n in ("laps", "stints", "pits", "events")}


def prepare(laps, stints):
    """One row per lap with compound, tyre age and the flags that decide which laps are clean."""
    laps = laps.dropna(subset=["driver"]).copy()
    key = ["year", "round", "driver"]
    m = laps.merge(stints.dropna(subset=["driver"]), on=key, how="left")
    m = m[(m["lap"] >= m["lap_start"]) & (m["lap"] <= m["lap_end"])]
    m = m.drop_duplicates(key + ["lap"])
    m["age"] = m["tyre_age_start"].fillna(0) + (m["lap"] - m["lap_start"])
    rk = ["year", "round"]
    field = m.groupby(rk + ["lap"])["seconds"].transform("median")
    ref = m.groupby(rk)["seconds"].transform("median")
    m["neutral"] = field > NEUTRAL * ref
    prev = m.groupby(key)["neutral"].shift(1).astype("boolean").fillna(False)  # the restart lap after a neutralised one
    m["neutral"] = m["neutral"] | prev.astype(bool)
    # a lap before a pit-out lap is an in-lap
    m["pit_in"] = m.groupby(key)["pit_out"].shift(-1).astype("boolean").fillna(False).astype(bool)
    return m


def wet_races(m):
    share = m.assign(w=m["compound"].isin(["INTERMEDIATE", "WET"])).groupby(["year", "round"])["w"].mean()
    return set(share[share > 0.2].index)


def clean(m):
    c = m[(m["compound"].isin(DRY)) & ~m["neutral"] & ~m["pit_out"] & ~m["pit_in"] & (m["lap"] > 1) & m["seconds"].notna()]
    med = c.groupby(["year", "round", "driver"])["seconds"].transform("median")
    return c[c["seconds"] < 1.07 * med]


def fit_race(c):
    """Regress lap time on driver, compound, tyre age per compound and lap number for one race."""
    drivers = sorted(d for d, n in c["driver"].value_counts().items() if n >= 10)
    c = c[c["driver"].isin(drivers)]
    if len(drivers) < 8:
        return None
    cols = {f"d_{d}": (c["driver"] == d).astype(float) for d in drivers}
    comps = [k for k in DRY if (c["compound"] == k).sum() >= 60]
    base = "MEDIUM" if "MEDIUM" in comps else max(comps, key=lambda k: (c["compound"] == k).sum())  # the compound left out, so offsets are against it
    for k in comps:
        if k != base:
            cols[f"c_{k}"] = (c["compound"] == k).astype(float)
        cols[f"a_{k}"] = (c["compound"] == k) * c["age"]
    cols["lap"] = c["lap"].astype(float)
    X = pd.DataFrame(cols)
    y = c["seconds"].values
    keep = np.ones(len(y), dtype=bool)
    for _ in range(2):  # fit, drop laps more than 3 sd off (traffic, mistakes, slow zones), fit again
        beta, *_ = np.linalg.lstsq(X.values[keep], y[keep], rcond=None)
        resid = y - X.values @ beta
        keep = np.abs(resid) < 3 * resid[keep].std()
    b = dict(zip(X.columns, beta))
    resid = resid[keep]
    off = np.array([b[f"d_{d}"] for d in drivers])
    if abs(b["lap"]) > 0.3 or off.std() > 3:  # the lap data did not fit a race (red flags, timing gaps): skip it
        return None
    return {"driver_off": dict(zip(drivers, off - off.mean())), "base": float(off.mean()),
            "comp_off": {k: b.get(f"c_{k}", 0.0 if k == base else np.nan) if base == "MEDIUM" else np.nan for k in comps},
            "deg": {k: b[f"a_{k}"] for k in comps}, "fuel": b["lap"], "sigma": float(resid.std())}


def pit_losses(m):
    """Seconds lost per stop under green: in-lap plus out-lap minus two ordinary laps."""
    out = []
    for (y, r, d), g in m.sort_values("lap").groupby(["year", "round", "driver"]):
        t = g.set_index("lap")["seconds"]
        neutral = g.set_index("lap")["neutral"]
        ok = g[g["compound"].isin(DRY + ["INTERMEDIATE", "WET"]) & ~g["neutral"] & (g["lap"] > 1) & ~g["pit_out"] & ~g["pit_in"]]
        for lap in g.loc[g["pit_out"], "lap"]:
            if lap - 1 not in t.index or neutral.get(lap, True) or neutral.get(lap - 1, True):
                continue
            near = ok[(ok["lap"] - lap).abs().between(2, 6)]["seconds"]
            if len(near) >= 3 and pd.notna(t[lap]) and pd.notna(t[lap - 1]):
                out.append({"year": y, "round": r, "driver": d, "loss": t[lap] + t[lap - 1] - 2 * near.median()})
    return pd.DataFrame(out)


def race_fits(m):
    """{(year, round): fit} on dry clean laps, skipping wet races."""
    wet = wet_races(m)
    c = clean(m)
    fits = {}
    for (y, r), g in c.groupby(["year", "round"]):
        if (y, r) in wet:
            continue
        f = fit_race(g)
        if f:
            fits[(int(y), int(r))] = f
    return fits, wet


def pace_table(fits):
    """One row per driver and race: the race pace (off), plus form from earlier races and the qualifying gap."""
    res = pd.read_csv(RESULTS_CSV)
    rows = []
    for (y, r), f in sorted(fits.items()):
        g = res[(res["year"] == y) & (res["round"] == r)].set_index("Abbreviation")
        for d, o in f["driver_off"].items():
            if d in g.index:
                gap = g.loc[d, "quali_time_s"] - g["quali_time_s"].min()
                rows.append({"year": y, "round": r, "driver": d, "team": g.loc[d, "TeamName"], "off": o,
                             "quali_gap": gap, "race_id": y * 100 + r})
    t = pd.DataFrame(rows).sort_values(["race_id", "driver"]).reset_index(drop=True)
    t["team_off"] = t.groupby(["team", "race_id"])["off"].transform("mean")
    t["rel"] = t["off"] - t["team_off"]
    tr = t.groupby(["team", "race_id"], as_index=False)["off"].mean().sort_values("race_id")
    tr["team_form"] = tr.groupby("team")["off"].transform(lambda s: s.shift(1).rolling(FORM, min_periods=1).mean())
    t = t.merge(tr[["team", "race_id", "team_form"]], on=["team", "race_id"], how="left")
    t["drv_form"] = t.groupby("driver")["rel"].transform(lambda s: s.shift(1).rolling(FORM, min_periods=1).mean())
    return t


PACE_X = ["team_form", "drv_form", "quali_gap"]


def pace_model(t, race_id, cols=PACE_X):
    """Ridge fit on races before race_id: pace = a*team_form + b*drv_form + c*quali_gap. Returns (coef, residual sd).
    cols can leave out the qualifying gap, for races whose qualifying has not happened."""
    tr = t[t["race_id"] < race_id].copy()
    tr[PACE_X] = tr[PACE_X].fillna(0)
    tr["quali_gap"] = tr["quali_gap"].clip(upper=3)
    X, y = tr[cols].values, tr["off"].values
    coef = np.linalg.solve(X.T @ X + 5 * np.eye(len(cols)), X.T @ y)
    return coef, float((y - X @ coef).std())


def pooled(fits, before, losses, circuit_of, circuit):
    """Compound offsets, wear rates, fuel slope and pit loss from races before `before`."""
    use = [f for k, f in fits.items() if k < before]
    med = lambda vals: float(np.nanmedian(vals)) if len(vals) else np.nan
    comp_off = {k: (0.0 if k == "MEDIUM" else med([f["comp_off"].get(k, np.nan) for f in use])) for k in DRY}
    deg = {k: max(med([f["deg"].get(k, np.nan) for f in use]), 0.0) for k in DRY}
    L = losses[(losses["year"] * 100 + losses["round"]) < before[0] * 100 + before[1]]
    L = L[L["loss"].between(8, 60)]
    here = L[[circuit_of.get((y, r)) == circuit for y, r in zip(L["year"], L["round"])]]
    pit = float(here["loss"].median()) if len(here) >= 8 else float(L["loss"].median())
    return {"comp_off": comp_off, "deg": deg, "fuel": med([f["fuel"] for f in use]), "pit_loss": pit,
            "pit_sd": float(L["loss"].std()), "sigma": med([f["sigma"] for f in use])}
