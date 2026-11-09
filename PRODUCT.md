# Product

## Platform

web

## Users

- **The project owner, checking the model.** Opens a report before a race to read the picks, and after the race to see how they scored (HIT or MISS). The job is to judge whether the model is any good.
- **F1 fans.** Open a race's report to see the predicted podium and the reasons behind each pick. They do not need to know the code.
- **Fans who want to see how a race could play out.** Open the Race lab for the championship forecast and for pit stop plans, and for how far to trust them.

Not written for recruiters or interviewers. Reports should explain the model to a curious fan, not present it as a portfolio piece.

## Product Purpose

Slipstream predicts the Formula 1 podium (top 3 finishers) for one race at a time and publishes each prediction as a static HTML report. The main job of a report is to be a public pre-race prediction log: a dated record of what the model said before the race, with the actual result added beside it afterward.

The site has two sections, shown in a navbar. **Podium predictor** is the prediction log above. **Race lab** is a separate section: a lap-by-lap race simulator built from public lap data, with a championship forecast and a pit strategy optimiser on top of it. The lab does not feed the podium predictions and its results are never mixed into the podium track record.

Success is a record that can be checked. A reader can see when a prediction was made, how many races the model trained on, how each driver's probability was reached, and, after the race, what happened.

## Positioning

Honest evaluation. Features for race N use only information known before race N. Validation is walk-forward (train on earlier races, test on the next). Results are compared with grid-order baselines, and a tie with the baseline is reported as a tie.

## Operating Context

- Data comes from the Jolpica F1 API (the Ergast successor, no login). F1's own live timing service now requires authentication, so it is not used.
- A prediction is made after qualifying and before the race. Qualifying order is the grid unless the official starting grid is passed with `--start-grid`, so grid penalties are reflected only then.
- Qualifying is on Saturday and the race on Sunday. Between races, the Upcoming list shows the next race as an orange placeholder ("Prediction after qualifying on 7 Nov"), with a forecast rain chance from Open-Meteo. The forecast is shown to readers only and is not a model input. The race is cached in `data/next_race.json` and the page falls back to that file if the network is down.
- The workflow is command line: `fetch`, `evaluate`, `predict <year> <round>`, which writes `data/predictions/<year>_R<round>.json` and `reports/<year>_R<round>.html`. After the race, `fetch` then `outcome` adds the result in `data/outcomes/` and rebuilds the page. The saved prediction is not touched.
- A report has three modes. **Upcoming**: the race has not run. **Scored**: a pre-race prediction with the real result added afterward, showing HIT or MISS for the three picks. **Backtest**: a prediction made for a race already in the data, so it was not made before the race.
- For now, predictions are committed and pushed by hand, so the commit time on a prediction is the proof it came before the race.

## Capabilities and Constraints

- Per race, per driver: a podium probability (independent per driver, so they do not sum to 100%), a win chance (from a second blend, scaled so the field sums to 100%; saved from the first prediction made after this change, so earlier pages (R18, R19) show none), the grid position, and the three features that moved the score most (SHAP reasons).
- Probabilities are raw model output, with no calibration step applied. A calibration check on the walk-forward predictions found them close to the real rates and slightly cautious (see Evidence on Hand).
- The model is no better than grid order at the order of the podium, so the three picks are ordered by podium probability and the order is not a claim.
- A race report is one self-contained HTML file: no images, no icons, and no JavaScript of its own. Every page has a navbar (Podium predictor, Race lab) that is plain links. The Race lab page is static HTML with one inline script that draws its charts (championship lines with a 90% band, a pit stop plan heatmap with stint bars) from data embedded in the page; with no JavaScript the same numbers show as tables under "For the data nerds". The charts respect reduced motion and resize with the window. The index page has two small inline scripts: one splits the race list into Upcoming and Results tabs (it also opens the race named in the link and switches to its tab; without JavaScript both lists show one after the other), and one runs a once-per-session intro (a cartoon car that drives across by itself, optional engine sound that browsers may block, and a Skip button). The intro is skipped for reduced motion and for links to a race. Optional files in `reports/assets/` (`car.svg|png|webp`, `engine.mp3|ogg|wav|m4a`) replace the drawn car and add the sound. The only external requests are the web font link and the Vercel Web Analytics script, which counts visits without cookies.
- No weather and no safety car features in the podium model. Weather was tested and not adopted: only 9 of 89 races had at least 2 mm of rain. The forecast rain chance is shown on the next-race row and on upcoming race pages, for readers. In the Race lab, safety cars are random events in the simulator, from each circuit's past rate.
- Planned for the Race lab, not built: a live track map from OpenF1 positions (needs a backend, so it breaks the static-page model), a fantasy score for the podium model, and a race engineer game.
- Terminology: **podium** means finishing in the top 3. **Grid** means qualifying order. **Backtest** means a race already in the data.
- The `reports/` folder is the whole site: each race has a page, and `index.html` lists them. It is meant to be served as static files (Vercel, with `reports` as the root directory).
- **Race lab.** Data comes from OpenF1 (no login, 2023 onward): laps, tyre stints, pit stops and safety car events. Commands, all run by hand:
  - `python -m f1pred.lab.fetch` downloads and caches the lap data in `data/raw/lab/` (git-ignored). 88 of 89 races are available; 2024 round 22 is not on OpenF1.
  - `python -m f1pred.lab.validate` checks the simulator against past races and writes `data/lab_evaluation.json`.
  - `python -m f1pred.lab.season` writes the championship forecast to `data/championship.json`; `--backtest` writes `data/championship_backtest.json`.
  - `python -m f1pred.lab.strategy [CODES]` writes the best pit plans for the next race to `data/strategy.json`; `--check` writes `data/strategy_check.json`. Run it again after qualifying so it uses the real grid.
  - `python -m f1pred.lab.report` writes `reports/lab/index.html` from those files. After each race, refresh the forecast and the strategy and rebuild the page.
- The simulator: each lap, a car's time is its pace plus the tyre offset, tyre wear, a fuel and track slope and noise. A car is held behind the one ahead unless it is faster by a margin; a car in the pit lane is neither held nor holds. Stops cost the fitted pit loss. Cars can retire, and a safety car can close the field. Pace is forecast from team and driver form and the qualifying gap. All fitting uses earlier races only. Wet races (7) and one race the lap data did not fit are left out of the fits.
- The simulator does not model rain, tyre warm-up or sudden tyre drop-off, damage, penalties during the race, team orders, or the effect of fuel on tyre wear. Fuel load is not a strategy choice: F1 has no refuelling, so the burn is in the pace.
- Planned, not built: a scheduled job that makes each prediction after qualifying and runs the `outcome` step after the race. Until then, both are run by hand.

## Brand Commitments

- Name: Slipstream, shown as a plain text wordmark.
- Voice: plain and factual. No promotional claims about accuracy that the evaluation does not support.

## Evidence on Hand

- `data/predictions/2026_R18.json` and `reports/2026_R18.html`: the pre-race prediction for the 2026 United States GP (VER, ANT, HAD as the top three by probability).
- Walk-forward evaluation on 85 races (2023 to 2026 round 20 data, saved in `data/evaluation.json`): the model is now an average of a 6-feature logistic regression and a regularised XGBoost. It has a top-3 overlap of 0.682 against 0.663 for both grid baselines, an exact-podium rate of 0.247 against 0.235, a Brier score of 0.066 against 0.069 and a log loss of 0.215 against 0.243. The earlier plain XGBoost scored 0.667, 0.224, 0.071 and 0.231. The gaps are small and a bootstrap over races does not rule out chance, so the model has not clearly beaten the baseline. Predictions saved before the blend (R18, R19) were made by the plain XGBoost.
- Calibration check on the first 84 of those races (blend, not re-run for round 20): mean predicted podium chance 15.0% against an actual rate of 14.7%; calibration slope 1.18 (95% interval 1.03 to 1.34), so the model is mildly cautious. Drivers rated above 35% reached the podium 3 to 8 points more often than predicted; drivers rated below 10% about 1 to 2 points less often. The 20 to 35% band was the weakest (27% predicted, 20% actual).
- Experiments that did not help and were not adopted: driver racecraft features (places gained from the grid, plain, recent and teammate-relative; Brier slightly worse, intervals include zero), recency weighting, extra seasons from 2018, and separate P1, P2, P3 order models (no better than ordering by podium probability; exact order 10.7%, the same as grid order). The win head alone is useful: Brier 0.030 against 0.047 for a constant guess.
- Race lab, simulator as a podium forecaster (75 dry races, 60 from 2024 on, which it was not tuned on; passing margin and pace spread were tuned on 2023 only): Brier score 0.067 against 0.061 for the podium model and 0.063 for a formula on grid position alone. It is clearly worse than the podium model (Brier difference +0.006, 95% interval +0.002 to +0.010) and not clearly different from the grid formula (+0.004, interval -0.002 to +0.011). Averaging it with the podium model did not help. So it is not used for the podium predictions.
- Race lab, mechanics: replaying a real race with its real stops and retirements, and the race's own pace, puts finishers in nearly the right order (rank correlation 0.89, 1.5 places off on average). With pace forecast from earlier races the figures fall to 0.82 and 2.1 places, so the pace forecast is the weak part.
- Race lab, championship forecast, checked on 10 points in 2023 to 2025 (after rounds 8, 12, 16, 20; 2024 round 12 was a wet race and is not included): the real drivers' champion got 69% on average and the real constructors' champion 92%. Expected final points were 21 off after rounds 8 and 12 against 29 for assuming each driver keeps scoring at the rate so far; later in the season the two are about equal. Three seasons is too few to judge the title chances, so they are labelled rough. The 2026 drivers' title is decided mathematically (Antonelli leads by more than the points left).
- Race lab, pit strategy: for 552 drivers in 72 past races, how much better the simulator rated a driver's real plan than a typical plan moved with how far ahead they finished, but real gains were about 27% of the simulated ones (95% interval 9% to 49%). The ranking of plans carries some signal; the size of the gains does not. The straight-line tyre wear probably favours soft tyres and long stints too much, and with no tyre warm-up the undercut is probably overstated and the overcut cannot show.
- A pit-lane blocking bug in the simulator (a stopping car held the car behind) was found through an undercut table that made no sense, and fixed; the podium and championship results did not change.
- Tests that check features do not use the current race's outcome. The Race lab has its own tests (simulator, fitting, navbar, strategy).
- Absent, so future work must not invent them: a track record of scored predictions across many races, user counts, and a record of real races where the Race lab's pit advice was followed.

## Product Principles

1. **Pre-race information only.** A feature for race N uses nothing from race N or later.
2. **Report the result as it is.** A tie with the baseline is stated as a tie. No accuracy claim goes in without an evaluation behind it.
3. **A prediction is fixed once made.** The actual result is added beside it, never in place of it.
4. **Probabilities are not certainty.** Show them as model output, say no calibration is applied, and never present a pick as a call.
5. **Show enough to check the claim.** Every report states when it was made, how many races it trained on, and why each top pick scored as it did.
6. **The Race lab states how far to trust it.** Every lab result sits next to the check that was run on it and what that check found, including when the simulator does worse than the podium model. Strategy advice is a ranking of plans, not a promise of points.
