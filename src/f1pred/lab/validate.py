"""Walk-forward check of the simulator against real races.

For each race, everything the simulator uses (pace, tyre wear, pit loss, retirement and safety car rates,
typical strategies) is fitted on earlier races only. Three runs per race:
  forecast     pace forecast, typical strategies, random retirements and safety cars. The honest test.
  replay       pace forecast, but the race's real pit stops and retirements. Tests the lap-by-lap mechanics.
  replay-true  as replay, with the race's own measured pace. Tests the mechanics alone.
Usage: python -m f1pred.lab.validate
"""
import json
import sys
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

from ..config import DATA
from ..evaluate import walk_forward
from ..features import build
from . import model
from .sim import Setup, simulate

LAB_EVALUATION = DATA / "lab_evaluation.json"
MIN_TRAIN = 5
warnings.filterwarnings("ignore", category=FutureWarning)


class Context:
    """Everything fitted once from the lap data."""

    def __init__(self):
        d = model.load()
        self.m = model.prepare(d["laps"], d["stints"])
        self.fits, self.wet = model.race_fits(self.m)
        self.losses = model.pit_losses(self.m)
        self.pace = model.pace_table(self.fits)
        self.df = build()
        self.events = d["events"]
        self.stints = d["stints"].dropna(subset=["driver"])
        self.laps_in_race = self.m.groupby(["year", "round"])["lap"].max().to_dict()
        self.circuit = self.df.drop_duplicates(["year", "round"]).set_index(["year", "round"])["location"].to_dict()
        self.sc_races = set(zip(*self.events[self.events["kind"] == "safety_car"][["year", "round"]].drop_duplicates().values.T))
        self.plans = self._plans()

    def _plans(self):
        res = self.df[["year", "round", "Abbreviation", "position"]].rename(columns={"Abbreviation": "driver"})
        st = self.stints.merge(res, on=["year", "round", "driver"])
        out = []
        for (y, r, d), g in st.groupby(["year", "round", "driver"]):
            g = g.sort_values("stint")
            n = self.laps_in_race.get((y, r))
            if not n or g["position"].iloc[0] > 12 or len(g) > 4 or (y, r) in self.wet:
                continue
            out.append({"year": y, "round": r, "circuit": self.circuit.get((y, r)),
                        "frac": [e / n for e in g["lap_end"].iloc[:-1]], "comps": list(g["compound"])})
        return out


def pace_for(ctx, race_id, rows):
    """Forecast pace per driver (seconds per lap vs the field) and its uncertainty."""
    coef, sd = model.pace_model(ctx.pace, race_id)
    hist = ctx.pace[ctx.pace["race_id"] < race_id]
    out = []
    for r in rows.itertuples():
        th = hist[hist["team"] == r.TeamName].groupby("race_id")["off"].mean().tail(model.FORM)
        dh = hist[hist["driver"] == r.Abbreviation]["rel"].tail(model.FORM)
        gap = 0.0 if pd.isna(r.quali_time_s) else min(r.quali_gap_s, 3)
        x = np.array([th.mean() if len(th) else 0.0, dh.mean() if len(dh) else 0.0, gap if not pd.isna(gap) else 0.0])
        out.append(float(x @ coef))
    return np.array(out), sd


def one_race(ctx, y, r, variant, n=500, margin=2.0, seed=0, sd_scale=0.75, lap_scale=0.5, ablate=()):
    rid = y * 100 + r
    rows = ctx.df[ctx.df["race_id"] == rid].reset_index(drop=True)
    L = ctx.laps_in_race[(y, r)]
    pace, sd = pace_for(ctx, rid, rows)
    p = model.pooled(ctx.fits, (y, r), ctx.losses, ctx.circuit, ctx.circuit[(y, r)])
    if variant == "replay-true":
        off = ctx.fits[(y, r)]["driver_off"]
        pace = np.array([off.get(d, pace[i]) for i, d in enumerate(rows["Abbreviation"])])
    s = Setup(laps=L, grid=rows["grid"].fillna(20).values.astype(int), pace=pace, pace_sd=sd * sd_scale * (0.0 if variant == "replay-true" else 1.0),
              comp_off=p["comp_off"], deg=p["deg"], fuel=p["fuel"], pit_loss=p["pit_loss"], pit_sd=min(p["pit_sd"], 3.0),
              lap_sd=p["sigma"] * lap_scale, p_dnf=np.zeros(len(rows)), margin=margin)
    if variant == "forecast":
        base = np.nanmean(ctx.df[ctx.df["race_id"] < rid]["dnf"])
        s.p_dnf = np.nan_to_num(0.5 * rows["driver_dnf_rate"].values + 0.5 * rows["team_dnf_rate"].values, nan=base)
        past = [k for k in ctx.fits if k < (y, r)]
        same = [k for k in past if ctx.circuit.get(k) == ctx.circuit[(y, r)]]
        g = np.mean([k in ctx.sc_races for k in past])
        s.p_sc = (sum(k in ctx.sc_races for k in same) + 2 * g) / (len(same) + 2)
        pool = [q for q in ctx.plans if (q["year"], q["round"]) < (y, r)]
        near = [q for q in pool if q["circuit"] == ctx.circuit[(y, r)]]
        pool = pool + near * 4  # strategies at this circuit count five times
        s.plans = [([int(round(f * L)) for f in q["frac"]], q["comps"]) for q in pool]
    else:
        fixed, out = [], []
        for d, done in zip(rows["Abbreviation"], rows["dnf"]):
            g = ctx.stints[(ctx.stints["year"] == y) & (ctx.stints["round"] == r) & (ctx.stints["driver"] == d)].sort_values("stint")
            fixed.append(([int(e) for e in g["lap_end"].iloc[:-1]], list(g["compound"])) if len(g) else ([], ["MEDIUM"]))
            last = ctx.m[(ctx.m["year"] == y) & (ctx.m["round"] == r) & (ctx.m["driver"] == d)]["lap"].max()
            out.append(np.inf if not done else float(last if pd.notna(last) else 1))
        s.fixed, s.dnf_laps = fixed, np.array(out)
    if "dnf" in ablate:
        s.p_dnf = s.p_dnf * 0
    if "sc" in ablate:
        s.p_sc = 0.0
    if "pit" in ablate:
        s.pit_sd = 0.0
    if "plans" in ablate:
        s.plans = s.plans[:1]
    rank = simulate(s, n=n, seed=seed)
    return rows, rank


def races(ctx, years=None):
    keys = sorted(ctx.fits)
    keys = [k for i, k in enumerate(keys) if i >= MIN_TRAIN]
    return [k for k in keys if years is None or k[0] in years]


def score_forecast(ctx, keys, **kw):
    # kw goes to one_race
    out = []
    for y, r in keys:
        rows, rank = one_race(ctx, y, r, "forecast", **kw)
        rows = rows.assign(p_sim=(rank <= 3).mean(0), p_sim_win=(rank == 1).mean(0), e_pos=rank.mean(0))
        out.append(rows[["year", "round", "Abbreviation", "podium", "position", "grid", "p_sim", "p_sim_win", "e_pos"]])
    return pd.concat(out)


def summarise(res, col, probability=True):
    hits = [len(set(g.nlargest(3, col).index) & set(g[g["podium"] == 1].index)) for _, g in res.groupby(["year", "round"])]
    out = {"races": len(hits), "top3_overlap": float(np.mean(hits) / 3), "exact_podium": float(np.mean([h == 3 for h in hits])),
           "brier": None, "logloss": None}
    if probability:
        out["brier"] = float(brier_score_loss(res["podium"], res[col]))
        out["logloss"] = float(log_loss(res["podium"], res[col].clip(1e-4, 1 - 1e-4)))
    return out


def replay_scores(ctx, keys, variant, **kw):
    rho, mae, win, top3 = [], [], [], []
    for y, r in keys:
        rows, rank = one_race(ctx, y, r, variant, **kw)
        ok = rows["position"].notna() & (rows["dnf"] == 0)
        sim, act = rank.mean(0)[ok.values], rows.loc[ok, "position"].values
        rho.append(pd.Series(sim).corr(pd.Series(act), method="spearman"))
        order = pd.Series(sim).rank().values
        mae.append(float(np.abs(order - pd.Series(act).rank().values).mean()))
        win.append(bool(np.argmin(sim) == np.argmin(act)))
        top3.append(len(set(np.argsort(sim)[:3]) & set(np.argsort(act)[:3])) / 3)
    return {"races": len(keys), "spearman": float(np.nanmean(rho)), "mean_place_error": float(np.mean(mae)),
            "winner_right": float(np.mean(win)), "top3_overlap": float(np.mean(top3))}


TUNED_ON = 2023  # margin and pace spread were chosen on this season only


def tables(f):
    """Podium scores for the simulator, the podium model and the baselines on the races in f."""
    t = {name: summarise(f, col) for name, col in
         [("simulator", "p_sim"), ("blend", "p_blend"), ("grid logistic", "p_grid_lr"), ("simulator + blend", "p_mix")]}
    t["grid order"] = summarise(f.assign(g=-f["grid"].fillna(20)), "g", probability=False)
    ok = f["position"].notna()
    t["place_error"] = {"simulator": float((f.loc[ok, "e_pos"] - f.loc[ok, "position"]).abs().mean()),
                        "grid": float((f.loc[ok, "grid"] - f.loc[ok, "position"]).abs().mean())}
    return t


def bootstrap(f, a, b, reps=2000, seed=0):
    """Brier of a minus Brier of b, with a 95% interval from resampling whole races. Negative: a is better."""
    per = f.assign(d=(f[a] - f["podium"]) ** 2 - (f[b] - f["podium"]) ** 2).groupby(["year", "round"])["d"].mean().values
    rng = np.random.default_rng(seed)
    means = [rng.choice(per, len(per)).mean() for _ in range(reps)]
    return {"diff": float(per.mean()), "low": float(np.percentile(means, 2.5)), "high": float(np.percentile(means, 97.5))}


def run(n=500, quick=False):
    ctx = Context()
    keys = races(ctx)
    if quick:
        keys = keys[::4]
    f = score_forecast(ctx, keys, n=n).reset_index(drop=True)
    base = walk_forward(ctx.df)[["year", "round", "Abbreviation", "p_model", "p_grid_lr"]]
    f = f.merge(base.rename(columns={"p_model": "p_blend"}), on=["year", "round", "Abbreviation"], how="inner")
    f["p_mix"] = (f["p_sim"] + f["p_blend"]) / 2
    return ctx, keys, f


def build_evaluation(n=500, quick=False):
    ctx, keys, f = run(n, quick)
    out = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "races": int(f.groupby(["year", "round"]).ngroups), "races_fitted": len(ctx.fits), "wet_races_skipped": len(ctx.wet), "tuned_on": TUNED_ON,
           "simulations_per_race": n,
           "all": tables(f), "holdout": tables(f[f["year"] > TUNED_ON]),
           "brier_difference": {"simulator minus blend": bootstrap(f[f["year"] > TUNED_ON], "p_sim", "p_blend"),
                                "simulator minus grid logistic": bootstrap(f[f["year"] > TUNED_ON], "p_sim", "p_grid_lr")},
           "replay": replay_scores(ctx, keys, "replay", n=300), "replay_true_pace": replay_scores(ctx, keys, "replay-true", n=300)}
    last = max(ctx.fits)
    p = model.pooled(ctx.fits, (last[0], last[1] + 1), ctx.losses, ctx.circuit, None)
    out["fitted"] = {"compound_offset_s": {k: round(v, 3) for k, v in p["comp_off"].items()},
                     "wear_s_per_lap": {k: round(v, 3) for k, v in p["deg"].items()},
                     "fuel_and_track_s_per_lap": round(p["fuel"], 3), "pit_loss_s": round(p["pit_loss"], 1)}
    return out


if __name__ == "__main__":
    out = build_evaluation(quick="--quick" in sys.argv)
    if "--quick" not in sys.argv:
        LAB_EVALUATION.write_text(json.dumps(out, indent=2))
    print(json.dumps({k: v for k, v in out.items() if k in ("races", "fitted", "replay", "replay_true_pace")}, indent=1))
    for part in ("all", "holdout"):
        print(part)
        print(pd.DataFrame({k: v for k, v in out[part].items() if k != "place_error"}).T.round(3).to_string())
        print("place error", out[part]["place_error"])
