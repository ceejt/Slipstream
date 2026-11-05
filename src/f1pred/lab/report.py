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
.verdict p{margin:0}
.soon-list{list-style:none;padding:0;margin:0}
.soon-list li{padding:12px 0;border-top:1px solid var(--rule)}
.soon-list b{font-weight:700}
"""


def _rows(pairs):
    return "".join(f'<tr><td>{a}</td><td class="num">{b}</td></tr>' for a, b in pairs)


def _table(caption, head, body):
    return (f'<div class="scroll"><table><caption>{caption}</caption><thead><tr><th scope="col">{head[0]}</th>'
            + "".join(f'<th scope="col" class="num">{h}</th>' for h in head[1:]) + f'</tr></thead><tbody>{body}</tbody></table></div>')


def _verdict(ev):
    d = ev["brier_difference"]
    vs_blend, vs_grid = d["simulator minus blend"], d["simulator minus grid logistic"]
    fmt = lambda x: f'{x["diff"]:+.4f} (95% interval {x["low"]:+.4f} to {x["high"]:+.4f})'
    rel = lambda x, name: (f"better than {name}" if x["high"] < 0 else f"worse than {name}" if x["low"] > 0
                           else f"not clearly different from {name}")
    return (f'<p><b>As a podium forecaster, the simulator is {rel(vs_blend, "the podium model")} and '
            f'{rel(vs_grid, "a formula on grid position alone")}.</b> '
            f'Brier score difference to the podium model: {fmt(vs_blend)}. To the grid formula: {fmt(vs_grid)}. '
            'Negative means the simulator is better. Intervals come from resampling whole races, on the seasons it was not tuned on.</p>')


def _chance(p):
    return ">99.9%" if p > 0.999 else "<0.1%" if p < 0.001 else f"{p * 100:.1f}%"


def _champ_tables(ch):
    def table(rows, head, n):
        body = "".join(f'<tr><td>{r["name"]}</td><td class="num">{r["now"]:.0f}</td><td class="num">{r["expected"]:.0f}</td>'
                       f'<td class="num">{r["low"]:.0f} to {r["high"]:.0f}</td><td class="num">{_chance(r["p_title"])}</td></tr>' for r in rows[:n])
        cap = f'After round {ch["after_round"]} of {ch["year"]}, {ch["races_left"]} races left, {ch["simulations"]:,} simulated seasons'
        return _table(cap, (head, "Points now", "Expected final", "90% range", "Title chance"), body)
    return table(ch["drivers"], "Driver", 8) + table(ch["constructors"], "Team", 5)


def _champ_check(bt):
    if not bt:
        return ""
    early = [b for b in bt if b["after_round"] <= 12]
    late = [b for b in bt if b["after_round"] > 12]
    avg = lambda rows, k: sum(r[k] for r in rows) / len(rows)
    return (f'<b>Checked on {len(bt)} points in 2023 to 2025</b> (after rounds 8 to 20, using only earlier races). '
            f'The real drivers\' champion was given {avg(bt, "p_driver_champion") * 100:.0f}% on average and the real constructors\' champion '
            f'{avg(bt, "p_constructor_champion") * 100:.0f}%. Expected final points were {avg(early, "driver_points_error"):.0f} off after rounds 8 and 12, '
            f'against {avg(early, "extrapolation_error"):.0f} for assuming each driver keeps scoring at the rate so far; later the two are about equal '
            f'({avg(late, "driver_points_error"):.0f} against {avg(late, "extrapolation_error"):.0f}). Three seasons is little, so the title chances are rough.')


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


def _strategy_notes(st, chk):
    pct = lambda v: f"{v * 100:.0f}%"
    u = st["undercut"]["1.0"]
    out = ""
    firsts = {(tuple(d["best"][0]["tyres"]), d["best"][0]["stops"]) for d in st["drivers"]}
    if len(firsts) == 1:
        (tyres, stops), laps = next(iter(firsts)), [d["best"][0]["laps"][0] for d in st["drivers"]]
        out += (f'<p class="note"><b>Same answer for all {len(st["drivers"])} drivers:</b> {stops} stop, {" then ".join(t.title() for t in tyres)}, first stop around lap {round(sum(laps) / len(laps))}. '
                'The fitted wear is nearly the same for the soft and the medium, so the faster soft tyre wins as the start. Real soft tyres fall off more sharply than straight-line wear can show, '
                'so the optimiser probably favours softs and long stints more than it should.</p>')
    if chk:
        out += (f'<p class="note"><b>Checked on {chk["drivers"]} drivers in {chk["races"]} past races:</b> the simulator\'s view of a plan moves with how far ahead the driver finished, '
                f'but real gains were about {chk["slope"] * 100:.0f}% of the simulated ones (95% interval {chk["low"] * 100:.0f}% to {chk["high"] * 100:.0f}%). Read the ranking of plans, not the size of the gain.</p>')
    out += (f'<p class="note"><b>Undercut and overcut.</b> Two cars level on pace, one second apart: stopping on the same lap gives the car behind {pct(u["0"])} to finish ahead; '
            f'one lap earlier {pct(u["-1"])}, two laps earlier {pct(u["-2"])}, one lap later {pct(u["1"])}. An undercut helps and an overcut does not. The simulator has no tyre warm-up on the out-lap and no traffic on rejoining, '
            'so it probably overstates the undercut and cannot show an overcut. The full table is under "Show as tables".</p>')
    return out


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
            tiles.append((f'Best plan, {st["event"]}', f'{stops} stop', " then ".join(t.title() for t in tyres) + ", for the three fastest cars."))
        else:
            tiles.append((f'Best plan, {st["event"]}', "Differs", "The best plan is not the same for each driver."))
    h = ev["holdout"]
    tiles.append(("As a podium forecaster", f'{h["simulator"]["brier"]:.3f} vs {h["blend"]["brier"]:.3f}',
                  f'Brier score of the simulator against the podium model over {h["simulator"]["races"]} races. Lower is better.'))
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
    decided = ""
    if ch:
        tags = [n for n, k in (("Drivers' title decided", "driver_title_clinched"), ("Constructors' title decided", "constructor_title_clinched")) if ch[k]]
        decided = "".join(f'<span class="decided">{t}</span> ' for t in tags)
    champ = f"""<section class="sec" id="championship"><h2>Championship</h2>
<p class="lead">Every remaining race of the season is simulated thousands of times and the points are added up. Lines are the average, shaded bands cover 90% of simulated seasons. Move over the chart, or use the arrow keys, to read each race. Click a name to show or hide it.</p>
{decided}<div id="fan-root"></div>
<p class="note">{_champ_check(bt)}</p>
<details class="tables"><summary>Show as tables</summary>{_champ_tables(ch)}</details></section>""" if ch else ""
    when = "Qualifying has not been run, so each simulated race draws its own grid from the pace forecast. " if st and not st["grid_known"] else "The grid is the real qualifying order. "
    strat = f"""<section class="sec" id="strategy"><h2>Pit strategy</h2>
<p class="lead">{escape(st["event"])}, {st["laps"]} laps, a pit stop costs {st["pit_loss_s"]} s. {when}Each square is a one-stop plan, played {st["simulations"]:,} times for the chosen driver while the rest of the field follows typical strategies. A stronger colour means more expected points. Move over the squares, or use the arrow keys.</p>
<div id="heat-root"></div>
{_strategy_notes(st, chk)}
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
<ul class="soon-list"><li><b>Race replay.</b> A real race lap by lap against the simulated one, then an undercut explorer and validation charts. Later: a live track map, a fantasy score and a race engineer game.</li></ul>
</section>
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
