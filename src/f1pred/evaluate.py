"""Walk-forward evaluation: for each race, train only on earlier races.

Compares the model (an average of a small logistic regression and a regularised
XGBoost) with two baselines, grid order and a logistic regression on grid position
alone, and with the earlier plain XGBoost. Metrics: top-3 hit rate (overlap with the
true podium), exact podium rate, Brier score and log loss on podium probabilities.
"""
import json
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from .config import EVALUATION
from .features import FEATURES, build

MIN_TRAIN_RACES = 5


def _top3_hits(g, score_col):
    pred = set(g.nlargest(3, score_col).index)
    actual = set(g[g["podium"] == 1].index)
    return len(pred & actual)


# The few facts the logistic half of the blend sees: where the driver starts and how strong the driver and team are.
SMALL_FEATURES = ["grid", "quali_pos", "quali_gap_s", "grid_penalty", "team_form_pts", "driver_form_pos"]


def make_xgb_v1():
    """The first XGBoost setup, kept so the evaluation can show what the blend improved on."""
    return XGBClassifier(n_estimators=200, max_depth=3, learning_rate=0.05,
                         subsample=0.8, colsample_bytree=0.8, min_child_weight=3,
                         eval_metric="logloss", random_state=42, verbosity=0)


def make_xgb():
    """Shallower trees and stronger regularisation: the training set is only a few dozen races."""
    return XGBClassifier(n_estimators=150, max_depth=2, learning_rate=0.03, subsample=0.7,
                         colsample_bytree=0.7, min_child_weight=10, reg_lambda=5,
                         eval_metric="logloss", random_state=42, verbosity=0)


class Blend:
    """Podium probability = the average of a small logistic regression and a regularised XGBoost."""

    def __init__(self):
        self.logistic = make_pipeline(StandardScaler(), LogisticRegression(C=0.3, max_iter=2000))
        self.xgb = make_xgb()

    def fit(self, X, y):
        self.logistic.fit(X[SMALL_FEATURES].fillna(0), y)
        self.xgb.fit(X, y)
        return self

    def predict_proba(self, X):
        p = (self.logistic.predict_proba(X[SMALL_FEATURES].fillna(0))[:, 1] + self.xgb.predict_proba(X)[:, 1]) / 2
        return np.column_stack([1 - p, p])


def walk_forward(df):
    race_ids = sorted(df["race_id"].unique())
    out = []
    for i, rid in enumerate(race_ids):
        if i < MIN_TRAIN_RACES:
            continue
        train, test = df[df["race_id"] < rid], df[df["race_id"] == rid].copy()
        if train["podium"].nunique() < 2 or test["podium"].sum() == 0:
            continue
        med = train[FEATURES].median(numeric_only=True)
        Xtr, Xte = train[FEATURES].fillna(med), test[FEATURES].fillna(med)

        test["p_xgb"] = make_xgb_v1().fit(Xtr, train["podium"]).predict_proba(Xte)[:, 1]
        test["p_model"] = Blend().fit(Xtr, train["podium"]).predict_proba(Xte)[:, 1]

        lr = LogisticRegression().fit(train[["grid"]].fillna(20), train["podium"])
        test["p_grid_lr"] = lr.predict_proba(test[["grid"]].fillna(20))[:, 1]
        test["p_grid"] = -test["grid"].fillna(20)  # ranking only
        out.append(test)
    return pd.concat(out) if out else pd.DataFrame()


def report(res):
    rows = []
    for name, col in [("grid order", "p_grid"), ("grid logistic", "p_grid_lr"), ("xgboost", "p_xgb"), ("blend", "p_model")]:
        hits = [_top3_hits(g, col) for _, g in res.groupby("race_id")]
        row = {"model": name, "races": len(hits),
               "top3_overlap": np.mean(hits) / 3, "exact_podium": np.mean([h == 3 for h in hits])}
        if col != "p_grid":
            row["brier"] = brier_score_loss(res["podium"], res[col])
            row["logloss"] = log_loss(res["podium"], res[col].clip(1e-6, 1 - 1e-6))
        rows.append(row)
    return pd.DataFrame(rows).round(3)


def save(res, table):
    """Write the latest table so reports can state it as of the day they were made."""
    last = int(res["race_id"].max())
    models = {r["model"]: {k: None if pd.isna(v) else float(v) for k, v in r.items() if k != "model"}
              for r in table.to_dict("records")}
    out = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "races": int(res["race_id"].nunique()),
           "through": {"year": last // 100, "round": last % 100}, "models": models}
    EVALUATION.write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    res = walk_forward(build())
    table = report(res)
    print(table.to_string(index=False))
    save(res, table)
