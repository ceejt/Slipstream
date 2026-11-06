"""The Race lab page (reports/lab/index.html), written from data/lab_evaluation.json."""
import json
from html import escape

from ..config import REPORTS
from ..report import ANALYTICS, CREDIT, CSS, FAVICON, FONT_LINK, _top
from . import charts
from .season import CHAMPIONSHIP
from .strategy import STRATEGY
from .validate import LAB_EVALUATION

BACKTEST = CHAMPIONSHIP.with_name("championship_backtest.json")
STRATEGY_CHECK = STRATEGY.with_name("strategy_check.json")

LAB_CSS = """
.lab-grid{display:grid;gap:16px;margin:0 0 32px}
@media(min-width:735px){.lab-grid{grid-template-columns:1fr 1fr}}
.lab-grid .scroll{margin:0}
.verdict{border-left:2px solid #E10600;padding:4px 0 4px 16px;margin:24px 0}
.verdict p{margin:0;font-weight:400}
.verdict .vhead b{font-weight:700}
.vrows{margin:12px 0;padding:0;max-width:44em}
.vrows div{display:grid;grid-template-columns:minmax(0,15em) 1fr;gap:4px 16px;padding:6px 0;border-top:1px solid var(--rule)}
.vrows dt{color:var(--muted)}
.vrows dd{margin:0;font-weight:700;font-variant-numeric:tabular-nums}
.vrows dd span{font-weight:400;color:var(--muted)}
.verdict .vnote{color:var(--muted);font-size:14px;line-height:20px}
.method .soon-list{list-style:none;padding:0;margin:0}
.method .soon-list li{padding:0;margin:0}
.method h3{margin:32px 0 8px}
.soon-list b{font-weight:700}
.back{margin:0 0 32px}
.back a{display:inline-block;padding:12px 0;min-height:44px;color:var(--text);font:600 14px/20px var(--body)}
"""


def _rows(pairs):
    return "".join(f'<tr><td>{a}</td><td class="num">{b}</td></tr>' for a, b in pairs)


def _table(caption, head, body):
    return (f'<div class="scroll"><table><caption>{caption}</caption><thead><tr><th scope="col">{head[0]}</th>'
            + "".join(f'<th scope="col" class="num">{h}</th>' for h in head[1:]) + f'</tr></thead><tbody>{body}</tbody></table></div>')


def _verdict(ev):
    d = ev["brier_difference"]
    vs_blend, vs_grid = d["simulator minus blend"], d["simulator minus grid logistic"]
    fmt = lambda x: f'{x["diff"]:+.3f} <span>(95% interval {x["low"]:+.3f} to {x["high"]:+.3f})</span>'
    rel = lambda x, name: (f"better than {name}" if x["high"] < 0 else f"worse than {name}" if x["low"] > 0
                           else f"not clearly different from {name}")
    return (f'<p class="vhead"><b>As a podium forecaster, the simulator is {rel(vs_blend, "the podium model")} and '
            f'{rel(vs_grid, "a formula on grid position alone")}.</b></p>'
            f'<dl class="vrows"><div><dt>Against the podium model</dt><dd>{fmt(vs_blend)}</dd></div>'
            f'<div><dt>Against the grid formula</dt><dd>{fmt(vs_grid)}</dd></div></dl>'
            '<p class="vnote">These are differences in Brier score, the average squared miss of the chances. Negative means the simulator is better. '
            'Intervals come from resampling whole races, on the seasons it was not tuned on.</p>')


def _chance(p):
    return ">99.9%" if p > 0.999 else "<0.1%" if p < 0.001 else f"{p * 100:.1f}%"


def _champ_tables(ch):
    def table(rows, head, n):
        body = "".join(f'<tr><td>{r["name"]}</td><td class="num">{r["now"]:.0f}</td><td class="num">{r["expected"]:.0f}</td>'
                       f'<td class="num">{r["low"]:.0f} to {r["high"]:.0f}</td><td class="num">{_chance(r["p_title"])}</td></tr>' for r in rows[:n])
        cap = f'After round {ch["after_round"]} of {ch["year"]}, {ch["races_left"]} races left, {ch["simulations"]:,} simulated seasons'
        return _table(cap, (head, "Points now", "Expected final", "90% range", "Title chance"), body)
    return table(ch["drivers"], "Driver", 10) + table(ch["constructors"], "Team", 6)


def _bars(rows):
    top = max(v for _, v, _ in rows) or 1
    return "".join(f'<div class="figrow"><span>{label}</span><b>{text}</b><i style="width:{max(v / top * 100, 2):.0f}%"></i></div>' for label, v, text in rows)


def _champ_check(bt):
    if not bt:
        return ""
    early = [b for b in bt if b["after_round"] <= 12]
    late = [b for b in bt if b["after_round"] > 12]
    avg = lambda rows, k: sum(r[k] for r in rows) / len(rows)
    seasons = len({b["year"] for b in bt})
    eb, ee, lb, le = avg(early, "extrapolation_error"), avg(early, "driver_points_error"), avg(late, "extrapolation_error"), avg(late, "driver_points_error")
    return (f'<div class="trust"><p class="tl"><b>Rough: checked on only {seasons} seasons.</b> After rounds 8 to 20, using only earlier races, the real drivers\' champion was given '
            f'{avg(bt, "p_driver_champion") * 100:.0f}% on average and the real constructors\' champion {avg(bt, "p_constructor_champion") * 100:.0f}%.</p>'
            f'<figure class="fig"><figcaption>Average miss in final points, after rounds 8 and 12</figcaption>'
            f'{_bars([("Simulator", ee, f"{ee:.0f} points"), ("Keep scoring at the rate so far", eb, f"{eb:.0f} points")])}'
            f'<p>Later in the season it is {le:.0f} points against {lb:.0f}.</p></figure></div>')


def _plan(x):
    tyres = " then ".join(t.title() for t in x["tyres"])
    laps = " and ".join(str(l) for l in x["laps"])
    return f'{x["stops"]} stop, {tyres}, stop on lap {laps}' if x["stops"] == 1 else f'{x["stops"]} stops, {tyres}, stops on laps {laps}'


def _strategy_tables(st):
    pct = lambda v: f"{v * 100:.0f}%"
    tables = ""
    for d in st["drivers"]:
        t = d["typical"]
        body = f'<tr><td>Typical plan for the field</td><td class="num">{t["points"]:.1f}</td><td class="num">{pct(t["podium"])}</td><td class="num">{pct(t["win"])}</td></tr>'
        body += "".join(f'<tr><td>{_plan(x)}</td><td class="num">{x["points"]:.1f}</td><td class="num">{pct(x["podium"])}</td><td class="num">{pct(x["win"])}</td></tr>'
                        for x in d["best"][:3])
        grid = "qualifying not run, grid simulated" if d["grid"] is None else f'starting P{d["grid"]}'
        tables += _table(f'{d["driver"]} ({d["team"]}), {grid}', ("Plan", "Expected points", "Podium", "Win"), body)
    ks = ("-3", "-2", "-1", "0", "1", "2")
    head = ("Gap behind the car ahead", "3 laps earlier", "2 earlier", "1 earlier", "Same lap", "1 later", "2 later")
    tables += _table("Chance of finishing ahead, two cars level on pace", head, "".join(
        f'<tr><td>{g} s</td>' + "".join(f'<td class="num">{pct(st["undercut"][g][k])}</td>' for k in ks) + "</tr>" for g in ("1.0", "2.0")))
    return tables


def _strategy_answer(st):
    """The answer in one sentence, before the chart that lets the reader look further."""
    firsts = {(tuple(d["best"][0]["tyres"]), d["best"][0]["stops"]) for d in st["drivers"]}
    if len(firsts) != 1:
        return '<p class="answer"><b>The best plan differs by driver.</b> Choose a driver below.</p>'
    (tyres, stops), laps = next(iter(firsts)), [d["best"][0]["laps"][0] for d in st["drivers"]]
    return (f'<p class="answer"><b>{stops} stop, {" then ".join(t.title() for t in tyres)}, first stop around lap {round(sum(laps) / len(laps))}.</b> '
            f'It is the best plan for all {len(st["drivers"])} drivers.</p>')


def _strategy_caveat(chk):
    if not chk:
        return ""
    real = chk["slope"] * 100
    return (f'<div class="trust"><p class="tl"><b>Trust the ranking of plans, not the size of the gain.</b> Across {chk["drivers"]} drivers in {chk["races"]} past races, '
            'the simulator\'s rating of a plan moved with how far ahead the driver finished.</p>'
            f'<figure class="fig"><figcaption>Real gain as a share of the simulated gain</figcaption>'
            f'{_bars([("In the simulator", 100, "100%"), ("In real races", real, f"about {real:.0f}%")])}'
            f'<p>95% interval {chk["low"] * 100:.0f}% to {chk["high"] * 100:.0f}%.</p></figure></div>')


def _strategy_notes(st):
    pct = lambda v: f"{v * 100:.0f}%"
    u = st["undercut"]["1.0"]
    return ('<ul class="notes">'
            '<li><b>Why the soft tyre starts.</b> The fitted wear is nearly the same for the soft and the medium, so the faster soft tyre wins. '
            'Real soft tyres fall off more sharply than straight-line wear shows, so the optimiser probably favours softs and long stints too much.</li>'
            f'<li><b>Undercut and overcut.</b> Two cars level on pace, one second apart, stopping on the same lap: the car behind finishes ahead {pct(u["0"])} of the time. '
            f'One lap earlier it is {pct(u["-1"])}, two laps earlier {pct(u["-2"])}, one lap later {pct(u["1"])}. '
            'The simulator has no tyre warm-up or traffic on rejoining, so it probably overstates the undercut and cannot show an overcut. The full table is under "Show as tables".</li>'
            '</ul>')


def _tiles(ev, ch, st):
    tiles = []
    if ch:
        lead = ch["drivers"][0]
        who = f'<span class="tc c-{charts._key(lead["name"])}">{escape(lead["name"])}</span>'  # in the team's colour
        v = f'{who}, decided' if ch["driver_title_clinched"] else f'{who} {_chance(lead["p_title"])}'
        tiles.append(("Drivers' title", v, f'After round {ch["after_round"]} of {ch["year"]}, {ch["races_left"]} races left.'))
    if st:
        firsts = {(tuple(d["best"][0]["tyres"]), d["best"][0]["stops"]) for d in st["drivers"]}
        if len(firsts) == 1:
            (tyres, stops), = firsts
            lap = round(sum(d["best"][0]["laps"][0] for d in st["drivers"]) / len(st["drivers"]))
            tiles.append((f'Best plan, {st["event"]}', f'{stops} stop',
                          " then ".join(t.title() for t in tyres) + f", first stop near lap {lap}, for the {len(st['drivers'])} fastest cars."))
        else:
            tiles.append((f'Best plan, {st["event"]}', "Differs", "The best plan is not the same for each driver."))
    h = ev["holdout"]
    d = ev["brier_difference"]["simulator minus blend"]
    word = "Better" if d["high"] < 0 else "Worse" if d["low"] > 0 else "No different"
    tiles.append(("Simulator against the podium model", word,
                  f'Brier score {h["simulator"]["brier"]:.3f} against {h["blend"]["brier"]:.3f} over {h["simulator"]["races"]} races. '
                  'It is the average squared miss of the chances, so lower is better. <a href="#checks">See the check</a>.'))
    return '<div class="tiles">' + "".join(f'<div class="tile"><p class="k">{k}</p><p class="v">{v}</p><p class="c">{c}</p></div>' for k, v, c in tiles) + "</div>"


def render(ev, ch=None, bt=None, st=None, chk=None):
    f = ev["fitted"]
    comp = _table("Fitted from earlier races", ("Tyre compound", "vs medium", "Wear per lap"),
                  "".join(f'<tr><td>{k.title()}</td><td class="num">{f["compound_offset_s"][k]:+.2f} s</td>'
                          f'<td class="num">{f["wear_s_per_lap"][k]:.3f} s</td></tr>' for k in ("SOFT", "MEDIUM", "HARD")))
    other = _table("Fitted from earlier races", ("Quantity", "Value"),
                   _rows([("Time lost in a pit stop", f'{f["pit_loss_s"]:.1f} s'),
                          ("Fuel burn and track grip", f'{f["fuel_and_track_s_per_lap"]:+.3f} s per lap')]))
    h = ev["holdout"]
    pct = lambda v: "n/a" if v is None else f"{v * 100:.1f}%"
    num = lambda v: "n/a" if v is None else f"{v:.3f}"
    body = ""
    for key, label in (("simulator", "Race simulator"), ("blend", "Podium model (Slipstream)"), ("grid logistic", "Formula on grid position only"),
                       ("simulator + blend", "Simulator and podium model averaged"), ("grid order", "First three on the grid")):
        m = h[key]
        body += (f'<tr><td>{label}</td><td class="num">{pct(m["top3_overlap"])}</td><td class="num">{pct(m["exact_podium"])}</td>'
                 f'<td class="num">{num(m["brier"])}</td><td class="num">{num(m["logloss"])}</td></tr>')
    compare = _table(f'{h["simulator"]["races"]} races, {ev["tuned_on"] + 1} onward', ("Method", "Top-3 overlap", "Exact podium", "Brier score", "Log loss"), body)
    rp, rt = ev["replay"], ev["replay_true_pace"]
    mech = _table(f'{rt["races"]} dry races, drivers who finished', ("Run", "Rank correlation", "Places off", "Winner right"), (
        f'<tr><td>Real stops and retirements, race pace known</td><td class="num">{rt["spearman"]:.2f}</td><td class="num">{rt["mean_place_error"]:.1f}</td><td class="num">{pct(rt["winner_right"])}</td></tr>'
        f'<tr><td>Real stops and retirements, pace forecast</td><td class="num">{rp["spearman"]:.2f}</td><td class="num">{rp["mean_place_error"]:.1f}</td><td class="num">{pct(rp["winner_right"])}</td></tr>'))
    data, team_css = charts.build(ch, st)
    nav = [("championship", "Championship"), ("strategy", "Pit strategy"), ("checks", "Checks"), ("method", "How it works")]
    status = ""
    if ch:
        who = lambda n: f'<span class="tc c-{charts._key(n)}">{escape(n)}</span>'
        done = [f'{who(ch[k][0]["name"])} has clinched the {t} title' for k, t in
                (("drivers", "drivers'"), ("constructors", "constructors'")) if ch[f"{k[:-1]}_title_clinched"]]
        if done:
            status = f'<p class="status"><b>{" and ".join(done)}.</b> The points left are not enough for anyone else to catch up.</p>'
    champ = f"""<section class="sec" id="championship"><h2>Championship</h2>
{status}<p class="lead">Every remaining race is simulated thousands of times and the points are added up. Lines are the average; shaded bands cover 90% of simulated seasons.</p>
<div id="fan-root"></div>
{_champ_check(bt)}
<details class="tables"><summary>Show as tables</summary>{_champ_tables(ch)}</details></section>""" if ch else ""
    when = "Qualifying has not been run, so each simulated race draws its own grid from the pace forecast. " if st and not st["grid_known"] else "The grid is the real qualifying order. "
    strat = f"""<section class="sec" id="strategy"><h2>Pit strategy</h2>
{_strategy_answer(st)}
<p class="lead">{escape(st["event"])}, {st["laps"]} laps, a pit stop costs {st["pit_loss_s"]} s. {when}Each square is a one-stop plan, played {st["simulations"]:,} times for the chosen driver while the rest of the field follows typical strategies. A stronger colour means more expected points.</p>
<div id="heat-root"></div>
{_strategy_caveat(chk)}
{_strategy_notes(st)}
<details class="tables"><summary>Show as tables</summary>{_strategy_tables(st)}</details></section>""" if st else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Slipstream Race lab</title>{FAVICON.replace('href="favicon', 'href="../favicon')}{FONT_LINK}{ANALYTICS}<style>{CSS}{LAB_CSS}{charts.CSS}{team_css}</style></head><body><main>
{_top(current="lab", root="../")}
<h1>Race lab</h1>
<p class="claim">A lap-by-lap race simulator built from public lap data. It is separate from the podium predictions: those come from a model trained on results, this one replays the race.</p>
{_tiles(ev, ch, st)}
<nav class="subnav" aria-label="On this page">{"".join(f'<a href="#{i}">{t}</a>' for i, t in nav)}</nav>
{champ}{strat}
<section class="sec" id="checks"><h2>Checks</h2>
<p class="lead">Every result above comes with the test it was put through. The simulator was tested on past races it had not seen, from {ev["races_fitted"]} dry races since 2023 (wet races, {ev["wet_races_skipped"]}, are left out).</p>
<div class="verdict">{_verdict(ev)}</div>
<details class="tables"><summary>Show the tables</summary>
<div class="lab-grid">{comp}{other}</div>
{mech}
{compare}
</details>
<p class="note">Replaying a real race with its real stops and retirements, and the race's own pace, puts finishers in nearly the right order. With pace forecast from earlier races it loses accuracy, so the pace forecast is the weak part. The simulator is a fair podium forecaster but not a better one; its use is that it produces whole races, which the podium model cannot.</p></section>
<section class="sec method" id="method"><h2>How it works</h2>
<ul>
<li>Each lap a car's time is its pace, plus the tyre offset, plus tyre wear, plus the fuel slope, plus noise.</li>
<li>A car cannot pass the one ahead unless it is faster by a margin. Otherwise it is held behind it. A car in the pit lane is not held.</li>
<li>A pit stop costs the pit loss and changes the tyre. Under a safety car it costs less.</li>
<li>Cars can retire, using each driver's and team's past retirement rate, and a safety car can close up the field, using each circuit's past rate.</li>
<li>The whole field follows one typical strategy per simulated race, taken from earlier races at that circuit, with small differences in stop laps.</li>
<li>Pace is forecast from team and driver form and the qualifying gap. All fitting uses earlier races only.</li>
<li>Not modelled: rain, tyre warm-up and sudden tyre drop-off, damage, penalties during the race, team orders and the effect of fuel on tyre wear.</li>
</ul>
<h3>Next</h3>
<ul class="soon-list"><li><b>Real race replay.</b> A real race lap by lap against the simulated one, then an undercut explorer and validation charts.</li></ul>
</section>
<p class="back"><a href="../index.html">Back to the podium predictions</a></p>
{CREDIT}
</main><script type="application/json" id="lab-data">{data}</script><script>{charts.JS}</script></body></html>"""


def write():
    ev = json.loads(LAB_EVALUATION.read_text())
    path = REPORTS / "lab" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    load = lambda f: json.loads(f.read_text()) if f.exists() else None
    path.write_text(render(ev, load(CHAMPIONSHIP), load(BACKTEST), load(STRATEGY), load(STRATEGY_CHECK)))
    return path


if __name__ == "__main__":
    print(write())
