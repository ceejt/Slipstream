import pandas as pd

from f1pred.features import build
from f1pred.predict import predict_frame
from f1pred.report import _apply_outcome, _baseline_line, render, render_index
from tests.test_no_leakage import _fake


def test_predict_uses_only_earlier_races_and_renders():
    df = build(*_fake(n_races=9))
    race_id = int(df["race_id"].max())
    out = predict_frame(df, race_id, min_train_races=3)
    assert len(out) == 6
    assert out["p_podium"].between(0, 1).all()
    assert out.iloc[0]["p_podium"] >= out.iloc[-1]["p_podium"]
    payload = {"year": 2024, "round": 9, "event": "<Test>", "mode": "backtest", "created_utc": "x",
               "trained_on_races": 8, "location": "Monza", "drivers": [
                   {"driver": r["Abbreviation"], "team": r["TeamName"], "grid": int(r["grid"]),
                    "p_podium": float(r["p_podium"]), "actual_position": int(r["position"]),
                    "reasons": r["reasons"]} for _, r in out.iterrows()]}
    html = render(payload)
    assert "&lt;Test&gt;" in html and "<Test>" not in html


def _payload(mode="upcoming", drivers=None):
    return {"year": 2026, "round": 18, "event": "X", "mode": mode, "created_utc": "2026-10-25T17:52:10+00:00",
            "trained_on_races": 87, "location": "Austin", "drivers": drivers or []}


def _driver(code, team, p, actual=None, status=None, grid=1):
    return {"driver": code, "team": team, "grid": grid, "p_podium": p, "actual_position": actual,
            "status": status, "reasons": [{"feature": "driver_form_pos", "value": 3.4, "shap": 0.2}]}


def test_unknown_team_and_missing_grid_do_not_break_render():
    d = _driver("ZZZ", "Brand New Team", 0.5, grid=None)
    d["reasons"] = [{"feature": "driver_form_pos", "value": None, "shap": 0.2}]
    html = render(_payload(drivers=[d]))
    assert "unmapped" in html and "grid unknown" in html and "driver form pos" in html
    assert "2026-10-25 17:52 UTC" in html


def test_known_teams_get_a_color_and_reasons_read_as_plain_words():
    html = render(_payload(drivers=[_driver("VER", "Red Bull", 0.8), _driver("GAS", "Alpine F1 Team", 0.1)]))
    assert "#3671C6" in html and "#00A1E8" in html
    assert "Recent average finish of 3.4" in html and ">P1<" in html


def test_backtest_summary_marks_hits_misses_dnf_and_near_misses():
    ds = [_driver("AAA", "Red Bull", .9, 1, "Finished"), _driver("BBB", "Ferrari", .8, 9, "+1 Lap"),
          _driver("CCC", "Mercedes", .7, 2, "Retired"), _driver("DDD", "McLaren", .1, 2, "Finished"),
          _driver("EEE", "Williams", .0, 3, "Finished")]
    html = render(_payload("backtest", ds))
    assert "1 of 3 picks finished on the podium." in html
    assert "On the podium but not picked: DDD (2nd), EEE (3rd)." in html
    assert "Did not finish" in html and "DNF" in html


def test_baseline_line_follows_the_saved_numbers():
    ev = {"races": 82, "through": {"year": 2026, "round": 17}, "models": {
        "grid order": {"top3_overlap": .67, "brier": None, "logloss": None},
        "grid logistic": {"top3_overlap": .67, "brier": .068, "logloss": .239},
        "xgboost": {"top3_overlap": .68, "brier": .071, "logloss": .234}}}
    assert "Has not yet beaten a grid-order baseline (82 races through 2026 round 17)." == _baseline_line(ev)
    ev["models"]["xgboost"].update(brier=.060, logloss=.200)
    assert _baseline_line(ev).startswith("Has beaten a grid-order baseline")
    assert _baseline_line(None) == ""


def test_footer_credits_the_author_with_a_safe_external_link():
    html = render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))
    assert 'href="https://ceejt-portfolio.vercel.app/"' in html
    assert 'rel="noopener noreferrer"' in html and "Made by" in html


def test_index_lists_races_newest_first_and_links_to_each_report():
    a = _payload(drivers=[_driver("VER", "Red Bull", 0.8)])
    b = dict(_payload("backtest", [_driver("AAA", "Ferrari", .9, 1, "Finished")]), round=17, event="Singapore Grand Prix")
    html = render_index([a, b])
    assert html.index("2026_R18.html") < html.index("2026_R17.html")
    assert "1 of 3 picks on the podium" in html and "Waiting for the race" in html
    assert "No predictions yet." in render_index([])


def test_method_section_is_on_the_report_and_its_table_uses_the_saved_numbers():
    ev = {"races": 82, "through": {"year": 2026, "round": 17}, "models": {
        "grid order": {"top3_overlap": .671, "exact_podium": .244, "brier": None, "logloss": None},
        "grid logistic": {"top3_overlap": .671, "exact_podium": .244, "brier": .068, "logloss": .239},
        "xgboost": {"top3_overlap": .683, "exact_podium": .232, "brier": .071, "logloss": .234}}}
    p = dict(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]), evaluation=ev)
    html = render(p)
    assert "How it works" in html and "walk-forward" in html and "XGBoost" in html
    assert "68.3%" in html and "0.071" in html and "has not clearly beaten" in html
    assert "<caption>82 races, through 2026 round 17</caption>" in html
    plain = render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))
    assert "How it works" in plain and "<caption>" not in plain
    assert "How it works" in render_index([p], ev)


def test_outcome_fills_results_without_changing_the_saved_prediction():
    ds = [_driver("AAA", "Red Bull", .9), _driver("BBB", "Ferrari", .8), _driver("CCC", "Mercedes", .7)]
    p = _payload(drivers=ds)
    o = {"created_utc": "2026-10-26T02:10:33+00:00", "drivers": {
        "AAA": {"position": 1, "status": "Finished"}, "BBB": {"position": 12, "status": "Finished"},
        "CCC": {"position": 14, "status": "Retired"}}}
    scored = _apply_outcome(p, o)
    assert scored["mode"] == "scored" and scored["drivers"][0]["actual_position"] == 1
    assert p["mode"] == "upcoming" and p["drivers"][0]["actual_position"] is None  # original untouched
    html = render(scored)
    assert "1 of 3 picks finished on the podium." in html and "Result added 2026-10-26 02:10 UTC" in html
    assert "Did not finish" in html and _apply_outcome(p, None) is p
    assert "post-race" in html and "Cool-down room" in html and "AAA won." in html
    assert "Biggest miss" in html and "Cool-down room" not in render(p)


def test_wordmark_links_to_the_repo_on_report_and_index():
    link = 'href="https://github.com/ceejt/Slipstream"'
    html = render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))
    assert link in html and 'rel="noopener noreferrer"' in html
    assert link in render_index([])


def test_race_pages_have_a_back_button_and_the_index_does_not():
    html = render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))
    assert 'class="back" href="index.html"' in html and "Back to all races" in html
    assert "Back to all races" not in render_index([])


def test_vercel_analytics_script_is_on_report_and_index():
    tag = '<script defer src="/_vercel/insights/script.js"></script>'
    assert tag in render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))
    assert tag in render_index([])


def test_intro_is_on_the_index_only_and_draws_a_car_when_no_file_is_given(tmp_path, monkeypatch):
    monkeypatch.setattr("f1pred.report.REPORTS", tmp_path)  # an empty folder, so no car or sound file is found
    html = render_index([])
    assert 'id="intro"' in html and "data-skip" in html and "ss-intro" in html and "data-start" not in html
    assert '<svg class="car"' in html and "<audio" not in html
    race = render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))
    assert 'id="intro"' not in race and "ss-intro" not in race


def test_intro_uses_a_car_and_sound_file_dropped_into_assets(tmp_path, monkeypatch):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "car.png").write_bytes(b"x")
    (tmp_path / "assets" / "engine.mp3").write_bytes(b"x")
    monkeypatch.setattr("f1pred.report.REPORTS", tmp_path)
    html = render_index([])
    assert '<img class="car" src="assets/car.png" alt="">' in html
    assert '<audio id="vroom" src="assets/engine.mp3" preload="none">' in html and '<svg class="car"' not in html


def test_method_section_is_laid_out_as_heading_and_text_rows():
    html = render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))
    assert html.count('class="mrow"') == 5 and html.count('class="mtext"') == 5
    assert html.count("<div") == html.count("</div>")


def test_start_grid_gives_positions_and_rejects_bad_lists():
    from f1pred.predict import _start_positions
    assert _start_positions(["A", "B", "C"], None) is None
    assert _start_positions(["A", "B", "C"], ["B", "C", "A"]) == {"B": 1, "C": 2, "A": 3}
    for bad in (["A", "A", "B"], ["A", "B"], ["A", "B", "C", "D"]):
        try:
            _start_positions(["A", "B", "C"], bad)
        except ValueError:
            continue
        raise AssertionError(f"{bad} should be rejected")


def test_report_says_which_grid_it_used():
    html = render(dict(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]), official_grid=True))
    assert "official starting order, including penalties" in html
    assert "qualifying order, so penalties are not included" in render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))


def test_blend_and_older_predictions_each_show_their_own_method_text_and_table():
    ev = {"races": 83, "through": {"year": 2026, "round": 18}, "models": {
        "grid order": {"top3_overlap": .671, "exact_podium": .241, "brier": None, "logloss": None},
        "grid logistic": {"top3_overlap": .671, "exact_podium": .241, "brier": .068, "logloss": .238},
        "xgboost": {"top3_overlap": .675, "exact_podium": .217, "brier": .070, "logloss": .231},
        "blend": {"top3_overlap": .691, "exact_podium": .253, "brier": .066, "logloss": .214}}}
    base = _payload(drivers=[_driver("VER", "Red Bull", 0.8)])
    new = render(dict(base, model="blend", evaluation=ev))
    assert "average of two simpler models" in new and "Earlier version: XGBoost alone" in new
    assert "Has beaten a grid-order baseline" in new and "69.1%" in new
    old = render(dict(base, evaluation=ev))  # no "model" key: made by the plain XGBoost
    assert "The model is XGBoost" in old and "Earlier version" not in old
    assert "Has not yet beaten a grid-order baseline" in old and "67.5%" in old


def test_predict_frame_gives_a_win_chance_between_0_and_1():
    df = build(*_fake(n_races=9))
    out = predict_frame(df, int(df["race_id"].max()), min_train_races=3)
    assert out["p_win"].between(0, 1).all()


def test_cards_show_the_win_chance_when_saved_and_older_predictions_still_render():
    with_win = _driver("VER", "Red Bull", 0.8)
    with_win["p_win"] = 0.4321
    assert "win chance 43.2%" in render(_payload(drivers=[with_win]))
    assert "win chance" not in render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))


def test_method_text_mentions_the_win_chance_only_when_a_page_shows_one():
    with_win = _driver("VER", "Red Bull", 0.8)
    with_win["p_win"] = 0.4
    assert "Each pick card also shows a win chance" in render(_payload(drivers=[with_win]))
    assert "Each pick card also shows a win chance" not in render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)]))
    assert "have not been checked for calibration" not in render(_payload(drivers=[with_win]))


def test_index_splits_upcoming_and_results_into_tabs_and_opens_the_right_one():
    up = _payload(drivers=[_driver("VER", "Red Bull", 0.8)])
    done = dict(_payload("scored", [_driver("AAA", "Ferrari", .9, 1, "Finished")]), round=17, event="Singapore Grand Prix")
    html = render_index([up, done])
    assert 'data-tab="upcoming"' in html and 'data-tab="results"' in html and 'data-first="upcoming"' in html
    up_panel, res_panel = html.split('id="panel-results"')
    assert "2026_R18.html" in up_panel and "2026_R17.html" not in up_panel.split('id="panel-upcoming"')[1]
    assert "2026_R17.html" in res_panel
    only_done = render_index([done])
    assert 'data-first="results"' in only_done and "No upcoming races yet." in only_done


def test_index_shows_a_placeholder_for_the_next_race_without_a_prediction():
    nxt = {"year": 2026, "round": 20, "event": "Brazilian Grand Prix", "date": "2026-11-08", "quali_date": "2026-11-07"}
    done = dict(_payload("scored", [_driver("AAA", "Ferrari", .9, 1, "Finished")]), round=19)
    html = render_index([done], next_race=nxt)
    assert "Brazilian Grand Prix" in html and "Prediction after qualifying on 7 Nov" in html and "Race on 8 Nov" in html
    assert 'data-first="upcoming"' in html and "2026_R20.html" not in html
    assert "Brazilian" not in render_index([done])


def test_next_race_skips_a_race_that_already_has_a_prediction(monkeypatch, tmp_path):
    from f1pred import report
    monkeypatch.setattr(report, "NEXT_RACE", tmp_path / "next_race.json")
    sched = {"RaceTable": {"Races": [
        {"season": "2099", "round": "1", "raceName": "A GP", "date": "2099-03-01"},
        {"season": "2099", "round": "2", "raceName": "B GP", "date": "2099-03-08", "Qualifying": {"date": "2099-03-07"}}]}}
    monkeypatch.setattr(report.jolpica, "get", lambda *a, **k: sched)
    monkeypatch.setattr(report, "date", type("D", (), {"today": staticmethod(lambda: __import__("datetime").date(2099, 2, 1)),
                                                        "fromisoformat": staticmethod(__import__("datetime").date.fromisoformat)}))
    assert report._next_race([])["event"] == "A GP"
    assert report._next_race([{"year": 2099, "round": 1}])["event"] == "B GP"
    monkeypatch.setattr(report.jolpica, "get", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")))
    assert report._next_race([{"year": 2099, "round": 1}])["event"] == "B GP"  # falls back to the saved file


def test_footer_has_a_github_icon_link_to_the_repo_on_report_and_index():
    for html in (render(_payload(drivers=[_driver("VER", "Red Bull", 0.8)])), render_index([])):
        assert 'class="gh" href="https://github.com/ceejt/Slipstream"' in html
        assert 'aria-label="Slipstream on GitHub"' in html and 'rel="noopener noreferrer"' in html
