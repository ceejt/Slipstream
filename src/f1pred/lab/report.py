"""The Race lab page (reports/lab/index.html), written from data/lab_evaluation.json."""
import json
from html import escape

from ..config import REPORTS
from ..report import ANALYTICS, CREDIT, CSS, FAVICON, FONT_LINK, _top
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


def _championship(ch, bt):
    """The forecast tables and what the backtest says about them, or empty text if they were not made."""
    if not ch:
        return ""
    def table(rows, cap, head, n):
        body = "".join(f'<tr><td>{r["name"]}</td><td class="num">{r["now"]:.0f}</td><td class="num">{r["expected"]:.0f}</td>'
                       f'<td class="num">{r["low"]:.0f} to {r["high"]:.0f}</td><td class="num">{_chance(r["p_title"])}</td></tr>' for r in rows[:n])
        return _table(cap, (head, "Points now", "Expected final", "90% range", "Title chance"), body)
    left = ch["races_left"]
    cap = f'After round {ch["after_round"]} of {ch["year"]}, {left} races left, {ch["simulations"]:,} simulated seasons'
    notes = []
    if ch["driver_title_clinched"]:
        notes.append(f'The drivers\' title is already decided: {ch["drivers"][0]["name"]} leads by more than the points still available.')
    if ch["constructor_title_clinched"]:
        notes.append("The constructors' title is already decided.")
    note = f'<p>{" ".join(notes)}</p>' if notes else ""
    check = ""
    if bt:
        early = [b for b in bt if b["after_round"] <= 12]
        late = [b for b in bt if b["after_round"] > 12]
        avg = lambda rows, k: sum(r[k] for r in rows) / len(rows)
        check = (f'<p>Checked on {len(bt)} points in the 2023 to 2025 seasons (after rounds 8 to 20), each time using only earlier races. '
                 f'The average chance given to the real drivers\' champion was {avg(bt, "p_driver_champion") * 100:.0f}%, and to the real constructors\' champion '
                 f'{avg(bt, "p_constructor_champion") * 100:.0f}%. The expected final points were off by {avg(early, "driver_points_error"):.0f} points on average '
                 f'after rounds 8 and 12, against {avg(early, "extrapolation_error"):.0f} for assuming each driver keeps scoring at the rate so far. '
                 f'Later in the season the two are about equal ({avg(late, "driver_points_error"):.0f} against {avg(late, "extrapolation_error"):.0f}). '
                 'That is only three seasons, so treat the title chances as rough.</p>')
    return f"""<h3>Championship forecast</h3>
<p>The simulator runs every remaining race of the season, thousands of times, and adds up the points. Qualifying is simulated too, from the same pace forecast. Each simulated season also gives every driver a pace shift that lasts all its races, so a quick car stays quick. Retirements and safety cars are random, from past rates. Sprint races are included.</p>
{note}
{table(ch["drivers"], cap, "Driver", 8)}
{table(ch["constructors"], cap, "Team", 5)}
{check}
"""


def _plan(x):
    tyres = " then ".join(t.title() for t in x["tyres"])
    laps = " and ".join(str(l) for l in x["laps"])
    return f'{x["stops"]} stop, {tyres}, stop on lap {laps}' if x["stops"] == 1 else f'{x["stops"]} stops, {tyres}, stops on laps {laps}'


def _strategy(st, chk):
    """Best plans for the next race, the undercut table and what the check says about them."""
    if not st:
        return ""
    pct = lambda v: f"{v * 100:.0f}%"
    tables = ""
    for d in st["drivers"]:
        t = d["typical"]
        body = f'<tr><td>Typical plan for the field</td><td class="num">{t["points"]:.1f}</td><td class="num">{pct(t["podium"])}</td><td class="num">{pct(t["win"])}</td></tr>'
        body += "".join(f'<tr><td>{_plan(x)}</td><td class="num">{x["points"]:.1f}</td><td class="num">{pct(x["podium"])}</td><td class="num">{pct(x["win"])}</td></tr>'
                        for x in d["best"][:3])
        grid = "qualifying not run, grid simulated" if d["grid"] is None else f'starting P{d["grid"]}'
        tables += _table(f'{d["driver"]} ({d["team"]}), {grid}', ("Plan", "Expected points", "Podium", "Win"), body)
    u = st["undercut"]["1.0"]
    ks = ("-3", "-2", "-1", "0", "1", "2")
    head = ("Gap behind the car ahead", "3 laps earlier", "2 earlier", "1 earlier", "Same lap", "1 later", "2 later")
    under = _table("Chance of finishing ahead, two cars level on pace", head, "".join(
        f'<tr><td>{g} s</td>' + "".join(f'<td class="num">{pct(st["undercut"][g][k])}</td>' for k in ks) + "</tr>" for g in ("1.0", "2.0")))
    check = ""
    if chk:
        check = (f'<p>Does the simulator understand strategy? For {chk["drivers"]} drivers in {chk["races"]} past races, I compared how much better '
                 f'the simulator thought their real plan was than a typical plan with how much further ahead they finished than the simulator expected. '
                 f'The two do move together, but weakly: real gains were about {chk["slope"] * 100:.0f}% of what the simulator claimed '
                 f'(95% interval {chk["low"] * 100:.0f}% to {chk["high"] * 100:.0f}%). Read the ranking of plans, not the size of the gain.</p>')
    firsts = {(tuple(d["best"][0]["tyres"]), d["best"][0]["stops"]) for d in st["drivers"]}
    verdict = ""
    if len(firsts) == 1:
        (tyres, stops), laps = next(iter(firsts)), [d["best"][0]["laps"][0] for d in st["drivers"]]
        verdict = (f'<p>All {len(st["drivers"])} drivers come out on the same plan: {stops} stop, {" then ".join(t.title() for t in tyres)}, first stop around lap {round(sum(laps) / len(laps))}. '
                   'The fitted tyre wear is nearly the same for the soft and the medium, so the faster soft tyre wins as the start. '
                   'Real soft tyres fall off more sharply than this straight-line wear can show, so the optimiser probably favours softs and long stints more than it should.</p>')
    when = "Qualifying has not been run, so each simulated race draws its own grid from the pace forecast. " if not st["grid_known"] else "The grid is the real qualifying order. "
    return f"""<h3>Pit strategy optimiser</h3>
<p>For one driver, the simulator plays the race {st["simulations"]:,} times on each candidate plan: one or two stops, any order of tyres that uses at least two kinds, and stop laps in steps of a few laps. The rest of the field follows typical strategies. Every plan sees the same random draws, so plans are compared fairly. Plans are ranked by expected points.</p>
<p><b>{escape(st["event"])}, {st["laps"]} laps, pit stop costs {st["pit_loss_s"]} s.</b> {when}Re-run after qualifying for the real grid.</p>
{tables}
{verdict}
<h3>Undercut and overcut</h3>
<p>Two cars level on pace, the second a set gap behind. The table shows how often the second car finishes ahead when it stops earlier (an undercut) or later (an overcut) than the first. At a one second gap, stopping on the same lap gives it {pct(u["0"])}; one lap earlier gives {pct(u["-1"])}, two laps earlier {pct(u["-2"])}; one lap later only {pct(u["1"])}. So in this simulator an undercut helps and an overcut does not. The simulator has no tyre warm-up on the out-lap and no traffic on rejoining, which are what make an overcut work in real races, and it probably overstates the undercut. Treat these as an upper bound for the undercut.</p>
{under}
{check}
"""


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
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Slipstream Race lab</title>{FAVICON.replace('href="favicon', 'href="../favicon')}{FONT_LINK}{ANALYTICS}<style>{CSS}{LAB_CSS}</style></head><body><main>
{_top(current="lab", root="../")}
<h1>Race lab</h1>
<p class="claim">A lap-by-lap race simulator built from public lap data. It is separate from the podium predictions: those come from a model trained on results, this one replays the race. Status: the simulator is built and tested. The championship forecast and the pit strategy optimiser are built.</p>
<div class="method">
<h3>What it learned from {ev["races_fitted"]} races</h3>
<p>Lap times, tyre stints and pit stops for every race since 2023 come from OpenF1. For each race the lab fits the pace of every driver, how much slower or faster each tyre is, how fast it wears, and how much time a pit stop costs. Wet races ({ev["wet_races_skipped"]}) are left out, because the tyre model is for dry running. For each target race only earlier races are used.</p>
<div class="lab-grid">{comp}{other}</div>
<h3>Does it reproduce real races?</h3>
<p>Two checks. The first replays a real race with the real pit stops and retirements, to test the lap-by-lap mechanics. Given the race's own pace the simulator puts finishers in nearly the right order. With pace forecast from earlier races and the qualifying gap, it loses accuracy, so the pace forecast is the weaker part.</p>
{mech}
<p>The second check is a forecast with nothing known about the race: forecast pace, typical strategies, random retirements and safety cars, {ev["simulations_per_race"]} simulated races each. Each driver's podium chance is how often they finish in the top three. The margin for passing and the pace spread were tuned on {ev["tuned_on"]} only.</p>
{compare}
<div class="verdict">{_verdict(ev)}</div>
<p>What this means: the simulator is a fair podium forecaster but not a better one. Its strength is a different one: it produces whole races, so it can test a pit stop plan or play out a season, which the podium model cannot. The next steps build on that.</p>
<h3>How it works</h3>
<ul>
<li>Each lap a car's time is its pace, plus the tyre offset, plus tyre wear, plus the fuel slope, plus noise.</li>
<li>A car cannot pass the one ahead unless it is faster by a margin. Otherwise it is held behind it.</li>
<li>A pit stop costs the pit loss and changes the tyre. Under a safety car it costs less.</li>
<li>Cars can retire, using each driver's and team's past retirement rate, and a safety car can close up the field, using each circuit's past rate.</li>
<li>The whole field follows one typical strategy per simulated race, taken from earlier races at that circuit, with small differences in stop laps.</li>
<li>Not modelled: rain, tyre warm-up and sudden tyre drop-off, damage, penalties during the race, team orders and the effect of fuel on tyre wear.</li>
</ul>
{_championship(ch, bt)}{_strategy(st, chk)}<h3>Next</h3>
<ul class="soon-list">
<li><b>Later.</b> Live track map from OpenF1 positions, a fantasy score for the podium model, and a race engineer game.</li>
</ul>
</div>
{CREDIT}
</main></body></html>"""


def write():
    ev = json.loads(LAB_EVALUATION.read_text())
    path = REPORTS / "lab" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    load = lambda f: json.loads(f.read_text()) if f.exists() else None
    path.write_text(render(ev, load(CHAMPIONSHIP), load(BACKTEST), load(STRATEGY), load(STRATEGY_CHECK)))
    return path


if __name__ == "__main__":
    print(write())
