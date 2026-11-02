from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
CACHE = DATA / "cache"
CIRCUITS_CSV = DATA / "circuits.csv"
RESULTS_CSV = RAW / "results.csv"
RACES_CSV = RAW / "races.csv"

FORM_WINDOW = 5
PREDICTIONS = DATA / "predictions"
EVALUATION = DATA / "evaluation.json"
NEXT_RACE = DATA / "next_race.json"
OUTCOMES = DATA / "outcomes"
REPORTS = ROOT / "reports"
