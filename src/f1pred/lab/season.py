"""Championship forecast: simulate every remaining race of the season many times and add up the points.

For each remaining round the simulator runs with pace forecast from earlier races (no qualifying yet, so
qualifying is simulated from the same pace), typical strategies, random retirements and safety cars.
Each simulated season also gets its own shift in driver pace, shared by all its races, so a car that turns
out quick stays quick. Sprint weekends run a short second race with the sprint points.
Usage: python -m f1pred.lab.season            forecast the current season
       python -m f1pred.lab.season --backtest compare with what happened in 2023 to 2025
"""
import json
import sys
from datetime import datetime, timezone

import numpy as np
import pandas as pd

from .. import jolpica
from ..config import DATA
from .sim import Setup, simulate
from .validate import Context, add_random_events, base_setup, pace_for  # noqa: F401

CHAMPIONSHIP = DATA / "championship.json"
POINTS = np.array([25, 18, 15, 12, 10, 8, 6, 4, 2, 1])
SPRINT_POINTS = np.array([8, 7, 6, 5, 4, 3, 2, 1])
SPRINT_SHARE = 0.33  # a sprint is about a third of a race distance
SHARED = 0.7         # share of the pace uncertainty that lasts the whole season (the rest changes race to race)
DEFAULT_LAPS = 57


def _points(rank, table):
    return np.where(rank <= len(table), table[np.minimum(rank, len(table)) - 1], 0)


def standings(year, after_round):
    """Official points after a round, from Jolpica: ({driver code: points}, {team: points})."""
    d = jolpica.get(f"{year}/{after_round}/driverStandings", year)["StandingsTable"]["StandingsLists"]
    c = jolpica.get(f"{year}/{after_round}/constructorStandings", year)["StandingsTable"]["StandingsLists"]
    drivers = {x["Driver"].get("code") or x["Driver"]["familyName"][:3].upper(): float(x["points"]) for x in d[0]["DriverStandings"]} if d else {}
    teams = {x["Constructor"]["name"]: float(x["points"]) for x in c[0]["ConstructorStandings"]} if c else {}
    return drivers, teams


def calendar(year):
    return [{"round": int(r["round"]), "event": r["raceName"], "location": r["Circuit"]["Location"]["locality"],
             "sprint": "Sprint" in r, "date": r["date"]} for r in jolpica.get(str(year), year)["RaceTable"]["Races"]]


def _lineup(ctx, year, after_round):
    """The cars as they raced in the last completed round: one row per driver."""
    rows = ctx.df[(ctx.df["year"] == year) & (ctx.df["round"] == after_round)].reset_index(drop=True)
    hist = ctx.df[ctx.df["race_id"] <= year * 100 + after_round]
    drv = hist.groupby("Abbreviation")["dnf"].mean()
    team = hist.groupby(["TeamName", "race_id"])["dnf"].mean().groupby("TeamName").mean()
    rows = rows.assign(grid=np.nan, quali_time_s=np.nan, quali_gap_s=np.nan,
                       driver_dnf_rate=rows["Abbreviation"].map(drv), team_dnf_rate=rows["TeamName"].map(team))
    return rows[["Abbreviation", "TeamName", "grid", "quali_time_s", "quali_gap_s", "driver_dnf_rate", "team_dnf_rate"]]


def _laps(ctx, location):
    seen = [(k, v) for k, v in ctx.laps_in_race.items() if ctx.circuit.get(k) == location]
    return max(seen)[1] if seen else DEFAULT_LAPS


def season_points(ctx, year, after_round, n=2000, seed=0, margin=2.0, sd_scale=0.75):
    """Points scored over the remaining rounds in every simulated season: (codes, teams, total n x cars, remaining races, per race R x n x cars)."""
    lineup = _lineup(ctx, year, after_round)
    codes, teams = list(lineup["Abbreviation"]), list(lineup["TeamName"])
    rng = np.random.default_rng(seed)
    D = len(codes)
    total = np.zeros((n, D))
    by_race = []
    rest = [c for c in calendar(year) if c["round"] > after_round]
    shared = None
    for k, race in enumerate(rest):
        L = _laps(ctx, race["location"])
        s, sd = base_setup(ctx, year, race["round"], lineup, L, race["location"], margin, sd_scale, 0.5, use_quali=False)
        add_random_events(ctx, year, race["round"], lineup, L, race["location"], s)
        if shared is None:
            shared = rng.normal(0, sd * sd_scale * SHARED, (n, D))
        base = s.pace[None, :] + shared
        within = sd * sd_scale * np.sqrt(1 - SHARED ** 2)
        grid = np.argsort(np.argsort(base + rng.normal(0, within, (n, D)), axis=1), axis=1) + 1  # simulated qualifying
        s.pace, s.pace_sd, s.grid = base, within, grid
        got = _points(simulate(s, n=n, seed=seed + k), POINTS)
        if race["sprint"]:
            sp = Setup(**{**s.__dict__, "laps": max(int(L * SPRINT_SHARE), 5), "plans": [([], ["MEDIUM"])], "p_sc": 0.0,
                          "p_dnf": s.p_dnf * 0.3, "fixed": None})
            got = got + _points(simulate(sp, n=n, seed=seed + 100 + k), SPRINT_POINTS)
        by_race.append(got)
        total += got
    return codes, teams, total, rest, np.stack(by_race) if by_race else np.zeros((0, n, D))


def _table(names, now, gained, groups=None):
    """Rows with current points, expected final points, a 5-95% range and the chance of finishing first."""
    final = np.array([now.get(nm, 0.0) for nm in names])[None, :] + gained
    lead = final.max(1, keepdims=True)
    winners = (final == lead).astype(float)
    winners /= winners.sum(1, keepdims=True)  # a tie splits the title
    rows = [{"name": nm, "now": now.get(nm, 0.0), "expected": float(final[:, i].mean()),
             "low": float(np.percentile(final[:, i], 5)), "high": float(np.percentile(final[:, i], 95)),
             "p_title": float(winners[:, i].mean()), "p_top3": float((final[:, i] >= np.sort(final, 1)[:, -min(3, final.shape[1])]).mean())}
            for i, nm in enumerate(names)]
    return sorted(rows, key=lambda r: -r["expected"])


def _add_paths(rows, names, now, per_race):
    """Points after each remaining race: the average and a 5 to 95% band, starting from the points now."""
    start = np.array([now.get(nm, 0.0) for nm in names])
    cum = np.cumsum(per_race, axis=0) + start[None, None, :]
    cut = lambda a: np.concatenate([start[None, :], a])
    mean, low, high = cut(cum.mean(1)), cut(np.percentile(cum, 5, axis=1)), cut(np.percentile(cum, 95, axis=1))
    for r in rows:
        i = names.index(r["name"])
        r["path"] = {"mean": [round(float(x), 1) for x in mean[:, i]], "low": [round(float(x), 1) for x in low[:, i]],
                     "high": [round(float(x), 1) for x in high[:, i]]}


def forecast(ctx, year, after_round, n=2000, seed=0):
    codes, teams, pts, rest, per_race = season_points(ctx, year, after_round, n, seed)
    now_d, now_t = standings(year, after_round)
    team_list = sorted(set(teams))
    by_team = np.stack([pts[:, [i for i, t in enumerate(teams) if t == tm]].sum(1) for tm in team_list], 1)
    drivers = _table(codes, now_d, pts)
    constructors = _table(team_list, now_t, by_team)
    team_of = dict(zip(codes, teams))
    for r in drivers:
        r["team"] = team_of[r["name"]]
    by_team_race = np.stack([per_race[:, :, [i for i, t in enumerate(teams) if t == tm]].sum(2) for tm in team_list], 2)
    _add_paths(drivers, codes, now_d, per_race)
    _add_paths(constructors, team_list, now_t, by_team_race)
    left = sum(25 + (8 if c["sprint"] else 0) for c in rest)
    left_t = sum(43 + (15 if c["sprint"] else 0) for c in rest)
    def clinched(rows, room):
        a = sorted(rows, key=lambda r: -r["now"])
        return bool(len(a) > 1 and a[0]["now"] - a[1]["now"] > room)
    return {"year": year, "after_round": after_round, "races_left": len(rest), "simulations": n,
            "remaining": [{"round": c["round"], "event": c["event"], "sprint": c["sprint"]} for c in rest],
            "drivers": drivers, "constructors": constructors,
            "driver_title_clinched": clinched(drivers, left), "constructor_title_clinched": clinched(constructors, left_t)}


def _score(rows, actual):
    """Chance given to the real champion and the mean error of expected points against the real final points."""
    champ = max(actual, key=actual.get)
    p = next((r["p_title"] for r in rows if r["name"] == champ), 0.0)
    err = np.mean([abs(r["expected"] - actual[r["name"]]) for r in rows if r["name"] in actual])
    return champ, p, float(err)


def backtest(ctx, years=(2023, 2024, 2025), n=400):
    out = []
    for y in years:
        cal = calendar(y)
        final_d, final_t = standings(y, len(cal))
        for k in (8, 12, 16, 20):
            if k >= len(cal) - 1 or (y, k) not in ctx.fits:
                continue
            f = forecast(ctx, y, k, n=n)
            now_d, now_t = standings(y, k)
            cd, pd_, ed = _score(f["drivers"], final_d)
            ct, pt, et = _score(f["constructors"], final_t)
            # baseline: keep scoring at the average rate so far
            base_d = np.mean([abs(v + v / k * (len(cal) - k) - final_d.get(nm, 0)) for nm, v in now_d.items() if nm in final_d])
            leader_d = max(now_d, key=now_d.get)
            leader_t = max(now_t, key=now_t.get)
            row = {"year": y, "after_round": k, "driver_champion": cd, "p_driver_champion": pd_, "driver_points_error": ed,
                   "extrapolation_error": float(base_d), "leader_is_champion": leader_d == cd,
                   "constructor_champion": ct, "p_constructor_champion": pt, "leader_team_is_champion": leader_t == ct}
            out.append(row)
            print(row, flush=True)
    return out


if __name__ == "__main__":
    ctx = Context()
    if "--backtest" in sys.argv:
        rows = backtest(ctx)
        (DATA / "championship_backtest.json").write_text(json.dumps(rows, indent=2))
    else:
        year = max(ctx.df["year"])
        after = int(ctx.df[ctx.df["year"] == year]["round"].max())
        out = forecast(ctx, year, after)
        out["created_utc"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        CHAMPIONSHIP.write_text(json.dumps(out, indent=2))
        for r in out["drivers"][:6]:
            print(f'{r["name"]:4s} now {r["now"]:5.0f}  expected {r["expected"]:6.1f}  ({r["low"]:.0f}-{r["high"]:.0f})  title {r["p_title"]*100:5.1f}%')
        for r in out["constructors"][:4]:
            print(f'{r["name"]:18s} now {r["now"]:5.0f}  expected {r["expected"]:6.1f}  title {r["p_title"]*100:5.1f}%')
        print("clinched:", out["driver_title_clinched"], out["constructor_title_clinched"])
