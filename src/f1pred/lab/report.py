"""The Race lab page (reports/lab/index.html), written from data/lab_evaluation.json."""
import json
from html import escape

from ..config import REPORTS
from ..report import ANALYTICS, CREDIT, CSS, FAVICON, FONT_LINK, _top
from .validate import LAB_EVALUATION

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


def render(ev):
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
<p class="claim">A lap-by-lap race simulator built from public lap data. It is separate from the podium predictions: those come from a model trained on results, this one replays the race. Status: the simulator is built and tested. Strategy and championship tools are not built yet.</p>
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
<li>Not modelled: rain, tyre warm-up, damage, penalties during the race, team orders and the effect of fuel on tyre wear.</li>
</ul>
<h3>Next</h3>
<ul class="soon-list">
<li><b>Championship forecast.</b> Run the simulator for each remaining race of the season, thousands of times, and count points.</li>
<li><b>Pit strategy optimiser.</b> Search stop counts, tyre choices and stop laps, and compare undercut and overcut.</li>
<li><b>Later.</b> Live track map from OpenF1 positions, a fantasy score for the podium model, and a race engineer game.</li>
</ul>
</div>
{CREDIT}
</main></body></html>"""


def write():
    ev = json.loads(LAB_EVALUATION.read_text())
    path = REPORTS / "lab" / "index.html"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render(ev))
    return path


if __name__ == "__main__":
    print(write())
