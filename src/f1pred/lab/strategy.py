"""Pit strategy optimiser.

For one driver in one race, the simulator plays the race many times with that driver on each candidate plan
(number of stops, tyre order, stop laps) while the rest of the field follows typical strategies. Plans are ranked
by expected points. Every plan is run on the same random draws, so the comparison between plans is paired.
It also measures the undercut and overcut: how often a car that stops a few laps earlier or later than the
car in front finishes ahead of it.
Usage: python -m f1pred.lab.strategy [CODE ...]     best plans for the next race (default: the three fastest cars)
       python -m f1pred.lab.strategy --check        does the simulator's view of strategy match real results?
"""
import itertools
import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from ..config import DATA, NEXT_RACE, RESULTS_CSV
from .season import POINTS, Context, _laps, _lineup, _points, calendar
from .sim import Setup, simulate
from .validate import add_random_events, base_setup, one_race, races

STRATEGY = DATA / "strategy.json"
COMPS = ["SOFT", "MEDIUM", "HARD"]
MIN_STINT = 8


def candidates(L, step):
    """One- and two-stop plans using at least two different tyres, stop laps on a grid of `step` laps."""
    out = []
    for seq in itertools.product(COMPS, repeat=2):
        if len(set(seq)) > 1:
            out += [([a], list(seq)) for a in range(int(0.2 * L), int(0.8 * L) + 1, step)]
    for seq in itertools.product(COMPS, repeat=3):
        if len(set(seq)) > 1:
            for a in range(int(0.15 * L), int(0.55 * L) + 1, step):
                out += [([a, b], list(seq)) for b in range(a + MIN_STINT, int(0.9 * L) + 1, step)]
    return out


def describe(plan):
    laps, comps = plan
    return {"stops": len(laps), "laps": [int(x) for x in laps], "tyres": comps}


def evaluate(s, car, plan, n, seed):
    """Expected points, expected position, podium and win chance for `car` on `plan` (None: a typical plan)."""
    s.forced = None if plan is None else {car: plan}
    r = simulate(s, n=n, seed=seed)[:, car]
    return {"points": float(_points(r, POINTS).mean()), "position": float(r.mean()),
            "podium": float((r <= 3).mean()), "win": float((r == 1).mean())}


def optimise(s, car, L, n_screen=300, n_final=1500, seed=0, step=5, keep=6):
    """Screen every candidate cheaply, then re-run the best and their neighbours on fresh random draws."""
    cands = candidates(L, step)
    screen = sorted(((evaluate(s, car, p, n_screen, seed)["points"], i) for i, p in enumerate(cands)), reverse=True)
    top = [cands[i] for _, i in screen[:keep]]
    seen, pool = set(), []
    for laps, comps in top:  # neighbours: move each stop by up to two laps
        for delta in itertools.product((-2, -1, 0, 1, 2), repeat=len(laps)):
            new = [x + d for x, d in zip(laps, delta)]
            ok = all(b - a >= MIN_STINT for a, b in zip([0] + new, new)) and new[-1] < L - MIN_STINT
            key = (tuple(new), tuple(comps))
            if ok and key not in seen:
                seen.add(key)
                pool.append((new, comps))
    scored = [(evaluate(s, car, p, n_final, seed + 1), p) for p in pool]
    scored.sort(key=lambda x: -x[0]["points"])
    base = evaluate(s, car, None, n_final, seed + 1)
    return base, [{**describe(p), **m} for m, p in scored[:5]]


def undercut_curve(setup, gap, shifts=range(-4, 5), n=1500, seed=0):
    """Chance that car A, level on pace and `gap` seconds behind car B, finishes ahead when A stops `k` laps earlier
    (negative k: an undercut) or later (positive k: an overcut) than B."""
    L = setup.laps
    mid = int(L * 0.45)
    out = {}
    for k in shifts:
        s = Setup(laps=L, grid=np.array([1, 2]), pace=np.zeros(2), pace_sd=0.0, comp_off=setup.comp_off, deg=setup.deg,
                  fuel=setup.fuel, pit_loss=setup.pit_loss, pit_sd=setup.pit_sd, lap_sd=setup.lap_sd, p_dnf=np.zeros(2),
                  margin=setup.margin, grid_step=gap,
                  fixed=[([mid], ["MEDIUM", "HARD"]), ([mid + k], ["MEDIUM", "HARD"])])
        out[k] = float((simulate(s, n=n, seed=seed)[:, 1] == 1).mean())
    return out


def _next(ctx):
    nxt = json.loads(NEXT_RACE.read_text())
    year, rnd = nxt["year"], nxt["round"]
    race = next(c for c in calendar(year) if c["round"] == rnd)
    return year, rnd, race


def race_rows(ctx, year, rnd):
    """The field for a race that has not been run: the official qualifying order if Jolpica has it, else None for the grid."""
    after = int(ctx.df[ctx.df["year"] == year]["round"].max())
    rows = _lineup(ctx, year, after)
    try:
        from ..predict import _upcoming_rows
        q = _upcoming_rows(year, rnd, pd.read_csv(RESULTS_CSV)).set_index("Abbreviation")
        rows = rows[rows["Abbreviation"].isin(q.index)].copy()
        rows["grid"] = rows["Abbreviation"].map(q["GridPosition"]).astype(float)
        rows["quali_time_s"] = rows["Abbreviation"].map(q["quali_time_s"])
        rows["quali_gap_s"] = rows["quali_time_s"] - rows["quali_time_s"].min()
        return rows.reset_index(drop=True), True
    except Exception:
        return rows, False


def run(codes=None, n_final=1500):
    ctx = Context()
    year, rnd, race = _next(ctx)
    rows, has_grid = race_rows(ctx, year, rnd)
    L = _laps(ctx, race["location"])
    s, sd = base_setup(ctx, year, rnd, rows, L, race["location"], 2.0, 0.75, 0.5, use_quali=has_grid)
    add_random_events(ctx, year, rnd, rows, L, race["location"], s)
    if not has_grid:
        rng = np.random.default_rng(0)
        N = max(n_final, 300)  # one row of pace and grid per simulation
        base = s.pace[None, :] + rng.normal(0, sd * 0.75 * 0.7, (N, len(rows)))
        s.pace, s.pace_sd = base, sd * 0.75 * 0.7
        s.grid = np.argsort(np.argsort(base + rng.normal(0, sd * 0.75 * 0.7, base.shape), axis=1), axis=1) + 1
    order = np.argsort(s.pace if s.pace.ndim == 1 else s.pace.mean(0))
    chosen = [list(rows["Abbreviation"]).index(c) for c in codes] if codes else list(order[:3])
    drivers = []
    for car in chosen:
        base_m, best = optimise(s, car, L, n_final=n_final)
        grid = None if not has_grid else int(rows["grid"].iloc[car])
        drivers.append({"driver": rows["Abbreviation"].iloc[car], "team": rows["TeamName"].iloc[car], "grid": grid,
                        "typical": base_m, "best": best})
        print(drivers[-1]["driver"], "typical", round(base_m["points"], 2), "best", best[0], flush=True)
    s.forced, s.grid, s.pace = None, np.arange(1, len(rows) + 1), np.zeros(len(rows))
    out = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"), "year": year, "round": rnd,
           "event": race["event"], "laps": L, "grid_known": has_grid, "simulations": n_final,
           "pit_loss_s": round(float(s.pit_loss), 1), "drivers": drivers,
           "undercut": {str(g): {str(k): v for k, v in undercut_curve(s, g).items()} for g in (1.0, 2.0)}}
    STRATEGY.write_text(json.dumps(out, indent=2))
    return out


def check(n=200, per_race=8):
    """Does the simulator's ranking of strategies carry information about real results?

    For each driver who started in the top 10 and finished, compare the simulated finishing position on his real
    plan with that on a typical plan. If the simulator understands strategy, drivers whose real plan looked better
    should have finished further ahead of the simulated typical-plan finish."""
    ctx = Context()
    rows_out = []
    for y, r in races(ctx):
        rows, rank_typ = one_race(ctx, y, r, "forecast", n=n, seed=5)
        L = ctx.laps_in_race[(y, r)]
        loc = ctx.circuit[(y, r)]
        s, _ = base_setup(ctx, y, r, rows, L, loc, 2.0, 0.75, 0.5)
        add_random_events(ctx, y, r, rows, L, loc, s)
        cand = rows[(rows["grid"] <= 10) & (rows["dnf"] == 0) & rows["position"].notna()].head(per_race)
        for i in cand.index:
            g = ctx.stints[(ctx.stints["year"] == y) & (ctx.stints["round"] == r) & (ctx.stints["driver"] == rows.loc[i, "Abbreviation"])].sort_values("stint")
            if len(g) < 2 or len(g) > 4 or not set(g["compound"]) <= set(COMPS):
                continue
            plan = ([int(e) for e in g["lap_end"].iloc[:-1]], list(g["compound"]))
            typ = evaluate(s, i, None, n, 5)
            act = evaluate(s, i, plan, n, 5)
            rows_out.append({"year": y, "round": r, "driver": rows.loc[i, "Abbreviation"], "value": typ["position"] - act["position"],
                             "surplus": typ["position"] - rows.loc[i, "position"]})
        print(y, r, len(rows_out), flush=True)
    d = pd.DataFrame(rows_out)
    return d


def summarise_check(d, reps=2000, seed=0):
    x = d["value"] - d.groupby(["year", "round"])["value"].transform("mean")  # compare drivers within a race
    y = d["surplus"] - d.groupby(["year", "round"])["surplus"].transform("mean")
    slope = lambda a, b: float((a * b).sum() / (a * a).sum())
    keys = d.groupby(["year", "round"]).ngroups
    groups = [g.index.values for _, g in d.groupby(["year", "round"])]
    rng = np.random.default_rng(seed)
    boots = []
    for _ in range(reps):
        idx = np.concatenate([groups[j] for j in rng.integers(0, len(groups), len(groups))])
        boots.append(slope(x.loc[idx], y.loc[idx]))
    return {"drivers": int(len(d)), "races": int(keys), "slope": slope(x, y), "low": float(np.percentile(boots, 2.5)),
            "high": float(np.percentile(boots, 97.5)), "correlation": float(np.corrcoef(x, y)[0, 1]),
            "value_sd_places": float(x.std())}


if __name__ == "__main__":
    if "--check" in sys.argv:
        d = check()
        d.to_csv(DATA / "strategy_check.csv", index=False)
        res = summarise_check(d)
        (DATA / "strategy_check.json").write_text(json.dumps(res, indent=2))
        print(res)
    else:
        run([a for a in sys.argv[1:] if not a.startswith("-")] or None)
