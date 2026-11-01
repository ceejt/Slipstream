# Product

## Platform

web

## Users

- **The project owner, checking the model.** Opens a report before a race to read the picks, and after the race to see how they scored (HIT or MISS). The job is to judge whether the model is any good.
- **F1 fans.** Open a race's report to see the predicted podium and the reasons behind each pick. They do not need to know the code.

Not written for recruiters or interviewers. Reports should explain the model to a curious fan, not present it as a portfolio piece.

## Product Purpose

Slipstream predicts the Formula 1 podium (top 3 finishers) for one race at a time and publishes each prediction as a static HTML report. The main job of a report is to be a public pre-race prediction log: a dated record of what the model said before the race, with the actual result added beside it afterward.

Success is a record that can be checked. A reader can see when a prediction was made, how many races the model trained on, how each driver's probability was reached, and, after the race, what happened.

## Positioning

Honest evaluation. Features for race N use only information known before race N. Validation is walk-forward (train on earlier races, test on the next). Results are compared with grid-order baselines, and a tie with the baseline is reported as a tie.

## Operating Context

- Data comes from the Jolpica F1 API (the Ergast successor, no login). F1's own live timing service now requires authentication, so it is not used.
- A prediction is made after qualifying and before the race. Qualifying order is the grid, so grid penalties are not reflected.
- The workflow is command line: `fetch`, `evaluate`, `predict <year> <round>`, which writes `data/predictions/<year>_R<round>.json` and `reports/<year>_R<round>.html`. After the race, `fetch` then `outcome` adds the result in `data/outcomes/` and rebuilds the page. The saved prediction is not touched.
- A report has three modes. **Upcoming**: the race has not run. **Scored**: a pre-race prediction with the real result added afterward, showing HIT or MISS for the three picks. **Backtest**: a prediction made for a race already in the data, so it was not made before the race.
- For now, predictions are committed and pushed by hand, so the commit time on a prediction is the proof it came before the race.

## Capabilities and Constraints

- Per race, per driver: a podium probability (independent per driver, so they do not sum to 100%), the grid position, and the three features that moved the score most (SHAP reasons).
- Probabilities are raw model output and not calibrated.
- A race report is one self-contained HTML file: no images, no icons, and no JavaScript of its own. The index page has two small inline scripts: one opens the race named in the link, and one runs a once-per-session intro (a cartoon car that drives across by itself, optional engine sound that browsers may block, and a Skip button). The intro is skipped for reduced motion and for links to a race. Optional files in `reports/assets/` (`car.svg|png|webp`, `engine.mp3|ogg|wav|m4a`) replace the drawn car and add the sound. The only external requests are the web font link and the Vercel Web Analytics script, which counts visits without cookies.
- No weather features and no safety car features yet. Both were removed when the data source changed.
- Terminology: **podium** means finishing in the top 3. **Grid** means qualifying order. **Backtest** means a race already in the data.
- The `reports/` folder is the whole site: each race has a page, and `index.html` lists them. It is meant to be served as static files (Vercel, with `reports` as the root directory).
- Planned, not built: a scheduled job that makes each prediction after qualifying and runs the `outcome` step after the race. Until then, both are run by hand.

## Brand Commitments

- Name: Slipstream, shown as a plain text wordmark.
- Voice: plain and factual. No promotional claims about accuracy that the evaluation does not support.

## Evidence on Hand

- `data/predictions/2026_R18.json` and `reports/2026_R18.html`: the pre-race prediction for the 2026 United States GP (VER, ANT, HAD as the top three by probability).
- Walk-forward evaluation on 83 races (2023 to 2026 data, saved in `data/evaluation.json`): the model is now an average of a 6-feature logistic regression and a regularised XGBoost. It has a top-3 overlap of 0.691 against 0.671 for both grid baselines, an exact-podium rate of 0.253 against 0.241, a Brier score of 0.066 against 0.068 and a log loss of 0.214 against 0.238. The earlier plain XGBoost scored 0.675, 0.217, 0.070 and 0.231. The gaps are small and a bootstrap over races does not rule out chance, so the model has not clearly beaten the baseline. Predictions saved before the blend (R18, R19) were made by the plain XGBoost.
- Tests that check features do not use the current race's outcome.
- Absent, so future work must not invent them: a track record of scored predictions across many races, calibration results, user counts, and any published URL.

## Product Principles

1. **Pre-race information only.** A feature for race N uses nothing from race N or later.
2. **Report the result as it is.** A tie with the baseline is stated as a tie. No accuracy claim goes in without an evaluation behind it.
3. **A prediction is fixed once made.** The actual result is added beside it, never in place of it.
4. **Probabilities are not certainty.** Show them as model output, say they are uncalibrated, and never present a pick as a call.
5. **Show enough to check the claim.** Every report states when it was made, how many races it trained on, and why each top pick scored as it did.
