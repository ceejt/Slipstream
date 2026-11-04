"""Rain forecast for a race, from Open-Meteo. Shown on the pages only: the model does not use weather.

The model is trained on past races and would need a forecast for every one of them, with only about
9 clearly wet races in the data, so weather is displayed for readers and kept out of the features.
"""
from datetime import date

import requests

from . import jolpica

URL = "https://api.open-meteo.com/v1/forecast"


def rain_forecast(race: dict):
    """Highest hourly rain chance (%) from the race start to two hours later, plus the expected mm.
    `race` is a Jolpica race entry. Returns None if anything is missing or the call fails."""
    try:
        loc = race["Circuit"]["Location"]
        start = int(race["time"][:2])
        j = requests.get(URL, timeout=20, params={
            "latitude": loc["lat"], "longitude": loc["long"], "timezone": "UTC",
            "hourly": "precipitation_probability,precipitation",
            "start_date": race["date"], "end_date": race["date"]}).json()["hourly"]
        hours = range(start, min(start + 3, 24))
        probs = [j["precipitation_probability"][h] for h in hours]
        mm = [j["precipitation"][h] for h in hours]
        if any(p is None for p in probs):
            return None
        return {"rain_chance": int(max(probs)), "rain_mm": round(float(sum(m or 0 for m in mm)), 1),
                "asof": date.today().isoformat()}
    except Exception:
        return None


def for_race(year: int, rnd: int):
    """The forecast for one race of the calendar, or None."""
    try:
        races = jolpica.get(f"{year}/{rnd}", year)["RaceTable"]["Races"]
        return rain_forecast(races[0]) if races else None
    except Exception:
        return None
