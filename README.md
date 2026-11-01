# Slipstream

Leak-free F1 podium prediction.

Podium prediction with one rule: a feature for race N only uses what is known before race N.

## Setup
    python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

## Run
    .venv/bin/python -m f1pred.fetch 2023 2024 2025 2026   # Jolpica API, about a minute
    .venv/bin/python -m f1pred.evaluate                    # walk-forward vs baselines
    .venv/bin/python -m f1pred.predict 2026 18             # one race, saves JSON + HTML
    .venv/bin/python -m f1pred.predict 2026 18 --grid VER,LEC,...   # if qualifying is not on Jolpica yet
    .venv/bin/python -m f1pred.outcome                      # after the race: adds the result beside the saved prediction
    .venv/bin/pytest                                       # leakage tests

## Index intro

The index page opens with a short intro: a cartoon car drives across by itself with smoke behind it, once per browser session, and a Skip button ends it. It draws its own car and plays no sound by default. To use your own, put the files in `reports/assets/` and rebuild the pages (`.venv/bin/python -c "from f1pred.report import write_index; write_index()"`; any `predict` run does it too):

- `car.svg`, `car.png` or `car.webp`: a side view facing right
- `engine.mp3`, `.ogg`, `.wav` or `.m4a`: a short clip (1 to 3 seconds), tried when the car starts (browsers often block sound before a visitor has clicked anything on the site, so it may stay silent for new visitors)

Check that you are allowed to use each file. The intro is skipped for reduced motion and for links to a race.

## Layout
- `src/f1pred/jolpica.py`: small Jolpica API client with paging, rate limiting and a disk cache
- `src/f1pred/fetch.py`: Jolpica to `data/raw/` (results, qualifying). No weather or safety car data yet
- `src/f1pred/predict.py`, `report.py`: one-race prediction as JSON and a static HTML page, plus the index
- `src/f1pred/outcome.py`: adds the real result to a saved prediction (`data/outcomes/`) and rebuilds its page; the prediction file is never changed
- `src/f1pred/features.py`: leak-free rolling driver, team and circuit features
- `src/f1pred/evaluate.py`: walk-forward split, baselines, metrics
- `data/circuits.csv`: static circuit attributes (starter rows, verify values, add the rest). The `location` must match Jolpica's locality, for example `Spa`

## Roadmap
1. Fetch 2018 to 2025 and read the first honest baseline numbers
2. Separate DNF model: P(podium) = P(finish) x P(top 3 | finish)
3. Weather forecast input (Open-Meteo) in place of observed race weather
4. FP2 long-run pace and tire degradation slope
5. Climate table per circuit and month; more circuit attributes
6. SHAP explanations, calibration, dashboard, public prediction log
