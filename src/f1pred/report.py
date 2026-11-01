"""Render a prediction payload as one self-contained HTML page (no external assets)."""
import json
import re
import sys
from html import escape

import pandas as pd

from .config import EVALUATION, OUTCOMES, PREDICTIONS, REPORTS, RESULTS_CSV

FAVICON = (
    '<link rel="icon" href="favicon-light.svg" type="image/svg+xml" media="(prefers-color-scheme: light)">'
    '<link rel="icon" href="favicon-dark.svg" type="image/svg+xml" media="(prefers-color-scheme: dark)">'
)

FONT_LINK = (
    '<link rel="preconnect" href="https://fonts.googleapis.com">'
    '<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>'
    '<link href="https://fonts.googleapis.com/css2?family=Titillium+Web:wght@400;600;700;900&display=swap" rel="stylesheet">'
)

# Team color (stripe) and card color (dark shade that keeps white text readable),
# both from formula1.com: the team logos on /en/results/2026/team and the driver
# cards on /en/drivers. Order matters: "racing bulls" before "red bull".
TEAM_COLORS = [
    ("racing bulls", "#6692FF", "#0038C2"), ("rb f1", "#6692FF", "#0038C2"),
    ("red bull", "#3671C6", "#142948"), ("mercedes", "#27F4D2", "#067E6A"),
    ("ferrari", "#E8002D", "#5C0012"), ("mclaren", "#FF8000", "#804000"),
    ("aston martin", "#229971", "#0F4331"), ("alpine", "#00A1E8", "#004E70"),
    ("audi", "#FF2D00", "#751500"), ("cadillac", "#AAAAAD", "#58585B"),
    ("williams", "#1868DB", "#082145"), ("haas", "#DEE1E2", "#667175"),
]

CSS = """
:root{--red:#E10600;--red-deep:#CA0500;--red-tint:#F6B4B2;
--bg:#15151E;--lime:#E9F877;--surface:#26262B;--surface-2:#303037;--rule:#47464C;
--text:#FFFFFF;--muted:#AAAAAA;--tag:var(--red-tint);--chrome-lo:#8A8A92;--chrome-hi:#FFFFFF;--chrome-edge:rgba(255,255,255,.18);
--display:"Formula1","Titillium Web",system-ui,sans-serif;--body:"Titillium Web",system-ui,sans-serif}
@media (prefers-color-scheme:light){:root{--bg:#F7F4F1;--lime:#6B7300;--surface:#FFFFFF;--surface-2:#E0DEDC;--rule:#CDCDCD;
--text:#15151E;--muted:#606066;--tag:var(--red-deep);--chrome-lo:#15151E;--chrome-hi:#5A5A62;--chrome-edge:rgba(0,0,0,.12)}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font:600 14px/16px var(--body)}
::selection{background:var(--red);color:#FFFFFF}
:focus-visible{outline:2px solid var(--text);outline-offset:2px}
main{max-width:973px;margin:0 auto;padding:24px 16px 48px}
@media(min-width:735px){main{padding:32px 24px 64px}}
@media(min-width:1069px){main{padding:32px 32px 64px}}
.top{display:flex;justify-content:space-between;align-items:center;gap:16px;margin:0 0 32px;
padding-bottom:12px;border-bottom:1px solid var(--rule)}
.brand{font:900 16px/22px var(--display);text-transform:uppercase;letter-spacing:.5px;margin:0}
.back{color:var(--text);text-decoration:none;border:1px solid var(--rule);border-radius:4px;padding:4px 12px;
font:600 14px/20px var(--body);transition:background-color .15s cubic-bezier(.4,0,.2,1)}
.back:hover{background:var(--surface-2)}
.brand a{color:inherit;text-decoration:none}
.brand a:hover{text-decoration:underline;text-underline-offset:4px}
h1{font:900 32px/38px var(--display);text-transform:uppercase;text-wrap:balance;margin:0 0 12px}
@media(min-width:735px){h1{font-size:40px;line-height:44px}}
.meta{display:flex;flex-wrap:wrap;align-items:center;gap:8px 16px;color:var(--muted);margin:0 0 16px}
.tag{background:rgb(225,6,0);color:#FFFFFF;border-radius:999px;padding:2px 12px;
font:500 12px/16px var(--display);text-transform:uppercase;letter-spacing:.5px}
.tag.back{background:var(--text);color:var(--bg)}
.claim{font:400 16px/24px var(--body);max-width:68ch;margin:0 0 32px}
.summary{font:600 16px/24px var(--body);margin:0 0 16px}
.label{font:500 12px/16px var(--display);text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 12px}
.podium{display:grid;grid-template-columns:1fr;gap:12px;margin-bottom:48px}
@media(min-width:735px){.podium{grid-template-columns:repeat(3,1fr);align-items:end}
.card.p1{order:2;min-height:460px}.card.p2{order:1;min-height:420px}.card.p3{order:3;min-height:380px}}
.card{display:flex;flex-direction:column;color:var(--on,var(--text));
clip-path:polygon(0 32px,56px 0,100% 0,100% 100%,0 100%)}
.cbody{flex:1;display:flex;flex-direction:column;gap:8px;padding:32px 16px 16px;
background:linear-gradient(200deg,var(--accent,var(--surface-2)) 0%,var(--card-bg,var(--surface-2)) 45%)}
.cname{background:var(--accent,var(--surface-2));color:var(--on-accent,var(--text));padding:12px 16px}
.pick{font:900 64px/64px var(--display);text-transform:uppercase;margin:0;color:var(--on-accent,var(--text))}
.first{font:600 14px/16px var(--body);text-transform:uppercase;letter-spacing:.5px;margin:0}
.last{font:900 26px/30px var(--display);text-transform:uppercase;margin:0;overflow-wrap:anywhere}
.team{font:600 14px/16px var(--body);margin:0}
.score{margin-top:auto;padding-top:16px}
.pct{font:700 36px/40px var(--body);margin:0;color:var(--accent,inherit);font-variant-numeric:tabular-nums}
.sub{font:600 14px/16px var(--body);margin:0}
.outcome{margin:0;display:flex;align-items:center;gap:8px;font:600 16px/20px var(--body)}
.why{margin:0;padding:0;list-style:none;font:600 14px/20px var(--body)}
.why b{display:inline-block;width:12px;font-weight:400}
.mark{display:inline-block;padding:0 6px;border:1px solid currentColor;border-radius:4px;
font:500 12px/18px var(--display);letter-spacing:.5px;text-transform:uppercase}
.mark.miss{border-style:dashed}
td .mark.miss{border-color:var(--muted);color:var(--muted)}
td .mark{border-color:var(--text)}
table{width:100%;border-collapse:collapse}
.scroll{overflow-x:auto;scrollbar-color:var(--rule) transparent}
th,td{padding:12px 6px;text-align:left;border-bottom:1px solid var(--rule)}
th{font:500 12px/16px var(--display);text-transform:uppercase;letter-spacing:.5px;color:var(--muted);padding-bottom:8px}
td{height:44px;transition:background-color .15s cubic-bezier(.4,0,.2,1)}
tbody tr:hover td{background:var(--surface-2)}
.num{text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.fin{white-space:nowrap}
.fin .mark{margin-right:20px;min-width:52px;text-align:center}
.fin .pos{display:inline-block;min-width:3ch;text-align:right;color:var(--lime)}
@media(min-width:735px){.fin .mark{margin-right:28px}}
.cell{display:flex;align-items:center;gap:12px;font:500 16px/22px var(--display);text-transform:uppercase}
.sv{flex:none;width:4px;height:24px;background:var(--team);box-shadow:inset 0 0 0 1px var(--rule)}
.unmapped .sv{background:transparent;box-shadow:inset 0 0 0 1px var(--muted)}
.team-col{display:none;color:var(--muted)}
@media(min-width:735px){.team-col{display:table-cell}th,td{padding:12px 8px}}
.pb{display:flex;align-items:center;gap:8px}
@media(min-width:735px){.pb{gap:12px}}
.bar{flex:1;height:8px;background:var(--surface-2);border-radius:4px;min-width:32px}
@media(min-width:735px){.bar{min-width:120px}}
.bar i{display:block;height:100%;min-width:2px;background:var(--red);border-radius:4px;
animation:grow .3s cubic-bezier(.4,0,.2,1) both;animation-delay:calc(var(--i)*30ms)}
@keyframes grow{from{width:0}}
.pv{flex:none;width:48px;text-align:right;font-weight:700;font-variant-numeric:tabular-nums}
.made{margin:48px 0 0;padding-top:16px;border-top:1px solid var(--rule);color:var(--muted);font:600 14px/20px var(--body)}
.made a{color:var(--text);font-weight:700;text-decoration:underline;text-decoration-color:var(--muted);text-underline-offset:3px}
@supports (background-clip:text) or (-webkit-background-clip:text){
.made a{background:repeating-linear-gradient(105deg,var(--chrome-lo) 0,var(--chrome-hi) 9px,var(--chrome-lo) 18px) 0 0/300% 100%;
-webkit-background-clip:text;background-clip:text;-webkit-text-fill-color:transparent;color:transparent;
font:900 17px/20px var(--body);transition:background-position .8s cubic-bezier(.4,0,.2,1);
filter:drop-shadow(0 1px 0 var(--chrome-edge))}
.made a:hover,.made a:focus-visible{background-position:-9px 0}}
.races{list-style:none;margin:0 0 16px;padding:0;display:grid;gap:12px}
.races>li{border:1px solid var(--rule);border-radius:8px;overflow:hidden}
.races summary{display:grid;grid-template-columns:1fr auto auto;align-items:center;gap:4px 16px;padding:16px;cursor:pointer;
list-style:none;transition:background-color .15s cubic-bezier(.4,0,.2,1)}
.races summary::-webkit-details-marker{display:none}
.races summary:hover{background:var(--surface-2)}
.races summary::after{content:"";width:8px;height:8px;border:solid var(--muted);border-width:0 2px 2px 0;transform:rotate(45deg);
transition:transform .2s cubic-bezier(.4,0,.2,1)}
.races details[open] summary::after{transform:rotate(-135deg)}
.races .ev{font:700 20px/24px var(--display);text-transform:uppercase}
.races .meta2{color:var(--muted);font:600 14px/20px var(--body);margin:0}
.races .when{color:var(--muted);font:500 12px/16px var(--display);text-transform:uppercase;letter-spacing:.5px;text-align:right}
.races .rbody{padding:16px;border-top:1px solid var(--rule)}
.races .open{display:inline-block;color:var(--text);font:600 14px/20px var(--body)}
@media(prefers-reduced-motion:reduce){.races summary::after{transition:none}}
.method{margin-top:64px}
.method h3{font:700 20px/24px var(--body);margin:32px 0 8px}
.mtext{max-width:68ch}
.method p,.method li{font:400 16px/24px var(--body);margin:0 0 12px}
.method ul{margin:0 0 12px;padding-left:20px}
.method li{margin-bottom:8px}
.method .scroll{margin:16px 0;max-width:none}
.method caption{caption-side:top;text-align:left;color:var(--muted);font:600 14px/20px var(--body);padding-bottom:8px}
@media(min-width:735px){.mrow{display:grid;grid-template-columns:180px minmax(0,68ch);gap:0 32px;
border-top:1px solid var(--rule);margin-top:24px;padding-top:24px}
.method h3{margin:0}.mtext>:last-child{margin-bottom:0}}
.insights{margin:16px 0 48px;padding:0 0 0 20px}
.insights li{font:400 16px/24px var(--body);margin:0 0 8px;break-inside:avoid}
@media(min-width:735px){.insights{column-count:2;column-gap:40px}}
.note{color:var(--muted);font:400 14px/20px var(--body);margin:32px 0 0}
.intro{position:fixed;inset:0;z-index:100;display:none;flex-direction:column;align-items:center;justify-content:center;
gap:8px;padding:24px 0;background:var(--bg);transition:opacity .3s cubic-bezier(.4,0,.2,1)}
.intro-pending .intro{display:flex}
.intro-pending body{overflow:hidden}
.intro.done{opacity:0;pointer-events:none}
.intro-title{font:900 40px/44px var(--display);text-transform:uppercase;margin:0}
.intro-sub{color:var(--muted);font:600 14px/20px var(--body);margin:0 0 24px}
.track{position:relative;width:100%;height:110px;overflow:hidden}
.track::after{content:"";position:absolute;left:0;right:0;bottom:10px;height:2px;
background:repeating-linear-gradient(90deg,var(--rule) 0 24px,transparent 24px 40px)}
.rig{position:absolute;left:calc(50% - 80px);bottom:6px;width:160px}
.rig .car{display:block;width:160px;height:auto}
.go .rig{animation:drive 1.7s linear forwards}
@keyframes drive{0.00%{transform:translate3d(0.00vw,0px,0) rotate(-2.2deg)}7.14%{transform:translate3d(7.14vw,-4px,0) rotate(1.6deg)}14.29%{transform:translate3d(14.29vw,-1px,0) rotate(-1.2deg)}21.43%{transform:translate3d(21.43vw,-5px,0) rotate(2.0deg)}28.57%{transform:translate3d(28.57vw,0px,0) rotate(-2.2deg)}35.71%{transform:translate3d(35.71vw,-4px,0) rotate(1.6deg)}42.86%{transform:translate3d(42.86vw,-1px,0) rotate(-1.2deg)}50.00%{transform:translate3d(50.00vw,-5px,0) rotate(2.0deg)}57.14%{transform:translate3d(57.14vw,0px,0) rotate(-2.2deg)}64.29%{transform:translate3d(64.29vw,-4px,0) rotate(1.6deg)}71.43%{transform:translate3d(71.43vw,-1px,0) rotate(-1.2deg)}78.57%{transform:translate3d(78.57vw,-5px,0) rotate(2.0deg)}85.71%{transform:translate3d(85.71vw,0px,0) rotate(-2.2deg)}92.86%{transform:translate3d(92.86vw,-4px,0) rotate(1.6deg)}100.00%{transform:translate3d(100.00vw,-1px,0) rotate(-1.2deg)}}
.rig .car{filter:drop-shadow(0 4px 0 rgba(0,0,0,.35))}
.smoke{position:absolute;left:0;bottom:2px;width:0;height:0}
.smoke i{position:absolute;left:0;bottom:0;width:26px;height:26px;border-radius:50%;background:var(--muted);opacity:0;filter:blur(6px)}
.go .smoke i{animation:puff .8s ease-out infinite}
.smoke i:nth-child(2){animation-delay:.14s;width:32px;height:32px}
.smoke i:nth-child(3){animation-delay:.28s}
.smoke i:nth-child(4){animation-delay:.42s;width:38px;height:38px}
.smoke i:nth-child(5){animation-delay:.56s;width:30px;height:30px}
@keyframes puff{0%{opacity:0;transform:translate(0,0) scale(.3)}25%{opacity:.4}100%{opacity:0;transform:translate(-100px,-26px) scale(2.2)}}
.intro-actions{margin-top:24px}
.skip{background:none;color:var(--muted);border:1px solid var(--rule);border-radius:4px;padding:8px 16px;cursor:pointer;
font:600 14px/24px var(--body);transition:background-color .15s cubic-bezier(.4,0,.2,1)}
.skip:hover{background:var(--surface-2)}
@media(min-width:735px){.intro-title{font-size:56px;line-height:60px}.rig{left:calc(50% - 130px);width:260px}.rig .car{width:260px}.track{height:150px}}
@media(prefers-reduced-motion:reduce){*{transition:none!important;animation:none!important}}
"""

# Optional intro on the index page. It is shown once per browser session, never with
# reduced motion or a #race link. The car drives off by itself; the sound is tried and
# skipped quietly if the browser blocks it. A car or sound file dropped in reports/assets/
# (car.svg|png|webp, engine.mp3|ogg|wav|m4a) replaces the drawn car and adds the sound.
INTRO_HEAD = ('<script>try{if(!sessionStorage.getItem("ss-intro")&&!location.hash'
              '&&!matchMedia("(prefers-reduced-motion:reduce)").matches)'
              'document.documentElement.classList.add("intro-pending")}catch(e){}</script>')

PLACEHOLDER_CAR = (
    '<svg class="car" viewBox="0 0 240 90" aria-hidden="true">'
    '<rect x="14" y="22" width="32" height="7" rx="2" fill="#4A4A52"/><rect x="14" y="22" width="3" height="24" fill="#4A4A52"/>'
    '<rect x="27" y="29" width="4" height="18" fill="#4A4A52"/>'
    '<path d="M26 52 L46 44 L108 40 L146 34 L176 44 L232 54 L232 61 L28 62 Z" fill="#E10600"/>'
    '<path d="M70 42 L96 24 L112 24 L114 42 Z" fill="#CA0500"/>'
    '<path d="M60 55 L172 51" stroke="#FFFFFF" stroke-width="3" fill="none"/>'
    '<circle cx="127" cy="31" r="9" fill="#FFD400"/><rect x="123" y="28" width="11" height="6" rx="2" fill="#111"/>'
    '<path d="M114 41 Q124 22 144 37" stroke="#111" stroke-width="3" fill="none"/>'
    '<rect x="204" y="62" width="34" height="6" rx="2" fill="#4A4A52"/>'
    '<circle cx="62" cy="64" r="19" fill="#222" stroke="#8A8A92" stroke-width="2"/><circle cx="62" cy="64" r="7" fill="#DDD"/>'
    '<circle cx="192" cy="66" r="16" fill="#222" stroke="#8A8A92" stroke-width="2"/><circle cx="192" cy="66" r="6" fill="#DDD"/>'
    '</svg>')

INTRO_SCRIPT = (
    '<script>(function(){var h=document.documentElement,o=document.getElementById("intro");'
    'if(!o||!h.classList.contains("intro-pending"))return;'
    'var m=document.querySelector("main"),a=document.getElementById("vroom"),t,'
    'k=o.querySelector("[data-skip]");'
    'm.inert=true;k.focus();'
    'function end(){clearTimeout(t);try{sessionStorage.setItem("ss-intro","1")}catch(e){}'
    'o.classList.add("done");m.inert=false;setTimeout(function(){h.classList.remove("intro-pending")},350)}'
    'function run(sound){clearTimeout(t);if(o.classList.contains("go"))return;o.classList.add("go");'
    'if(sound&&a){try{a.play().catch(function(){})}catch(e){}}t=setTimeout(end,1900)}'
        'k.onclick=function(){if(a)a.pause();end()};'
    'document.addEventListener("keydown",function(e){if(e.key==="Escape"){if(a)a.pause();end()}});'
    't=setTimeout(function(){run(true)},800)})()</script>')


def _asset(stem, exts):
    """Relative URL of reports/assets/<stem>.<ext> if the file exists, else None."""
    for ext in exts:
        if (REPORTS / "assets" / f"{stem}.{ext}").exists():
            return f"assets/{stem}.{ext}"
    return None


def _intro():
    """Overlay markup for the index page: a parked car that drives off by itself, and a Skip button."""
    car_src = _asset("car", ("svg", "png", "webp"))
    car = f'<img class="car" src="{car_src}" alt="">' if car_src else PLACEHOLDER_CAR
    sound_src = _asset("engine", ("mp3", "ogg", "wav", "m4a"))
    audio = f'<audio id="vroom" src="{sound_src}" preload="none"></audio>' if sound_src else ""
    return ('<div class="intro" id="intro" role="dialog" aria-modal="true" aria-label="SlipStream intro">'
            '<p class="intro-title">SlipStream</p><p class="intro-sub">Formula 1 podium predictions</p>'
            f'<div class="track"><div class="rig"><span class="smoke" aria-hidden="true"><i></i><i></i><i></i><i></i><i></i></span>{car}</div></div>'
            f'<div class="intro-actions"><button type="button" class="skip" data-skip>Skip</button></div>{audio}</div>')

FINISHED = re.compile(r"Finished|Lap")

# Vercel Web Analytics for plain HTML. The script is served by Vercel itself, so it
# does nothing (and fails quietly) when a page is opened from disk.
ANALYTICS = ('<script>window.va=window.va||function(){(window.vaq=window.vaq||[]).push(arguments)};</script>'
             '<script defer src="/_vercel/insights/script.js"></script>')

BRAND = ('<p class="brand"><a href="https://github.com/ceejt/Slipstream" target="_blank" rel="noopener noreferrer" '
         'aria-label="Slipstream, source code on GitHub (opens in a new tab)">Slipstream</a></p>')

def _top(back=False):
    """Top bar: wordmark on the left, and on race pages a button back to the index."""
    link = '<a class="back" href="index.html">Back to all races</a>' if back else ""
    return f'<header class="top">{BRAND}{link}</header>'


CREDIT = ('<footer class="made">Made by <a href="https://ceejt-portfolio.vercel.app/" '
          'target="_blank" rel="noopener noreferrer">ceejt</a></footer>')


def _ordinal(n):
    n = int(n)
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _team_info(team):
    """(stripe color, card color) for a team, or None if no verified color is on file."""
    name = str(team).lower()
    return next(((c, card) for key, c, card in TEAM_COLORS if key in name), None)


def _team_style(team):
    """Inline style and class for the table stripe. Unknown teams get a hollow stripe."""
    info = _team_info(team)
    return (f' style="--team:{info[0]}"', "") if info else ("", " unmapped")


def _on_color(hex_color):
    """White or dark text, whichever contrasts more with a #RRGGBB background."""
    def lum(h):
        c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
        c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
        return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]
    l = lum(hex_color)
    return "#FFFFFF" if (1.05) / (l + 0.05) >= (l + 0.05) / (lum("#15151E") + 0.05) else "#15151E"


def _card_style(team):
    """Card colors: F1's dark team shade with white text and the team color as accent for large text, or the neutral surface."""
    info = _team_info(team)
    return (f' style="--card-bg:{info[1]};--on:#FFFFFF;--accent:{info[0]};--on-accent:{_on_color(info[0])}"'
            if info else "")


def _names(code, names):
    """(first, last) for a driver code, falling back to the code itself."""
    first, last = (names or {}).get(code, ("", ""))
    return (escape(first), escape(last)) if last else ("", escape(code))


def _reason_text(feature, value):
    """Plain wording for a model feature and its value."""
    v = value
    if v is None:
        return escape(feature.replace("_", " "))
    text = {
        "grid": lambda: f"Starts {_ordinal(v)}",
        "quali_pos": lambda: f"Qualified {_ordinal(v)}",
        "quali_gap_s": lambda: "Set the pole time" if v < 0.0005 else f"{v:.3f} s off pole",
        "driver_form_pos": lambda: f"Recent average finish of {v:.1f}",
        "driver_dnf_rate": lambda: f"Retires in {v * 100:.0f}% of races",
        "team_form_pts": lambda: f"Team averages {v:.0f} points a race lately",
        "team_dnf_rate": lambda: f"Team cars retire in {v * 100:.0f}% of starts",
        "circuit_dnf_rate": lambda: f"{v * 100:.0f}% of cars retire at this circuit",
        "circuit_pos_gain": lambda: f"Drivers move {v:.1f} places here on average",
        "altitude_m": lambda: f"Altitude {v:.0f} m",
        "is_street": lambda: "Street circuit" if v >= 0.5 else "Permanent circuit",
    }.get(feature)
    return escape(text()) if text else escape(f"{feature.replace('_', ' ')} = {v}")


def _reasons(rs):
    items = []
    for r in rs:
        sign = "+" if r["shap"] > 0 else "-"
        items.append(f'<li><b>{sign}</b> {_reason_text(r["feature"], r["value"])}</li>')
    return "<ul class='why' aria-label='Reasons, strongest first'>" + "".join(items) + "</ul>"


def _beats(ev):
    """True if the model beats both grid baselines on every key metric, False if not, None if unknown."""
    try:
        m = ev["models"]
        x, g, o = m["xgboost"], m["grid logistic"], m["grid order"]
        return bool(x["brier"] < g["brier"] and x["logloss"] < g["logloss"]
                    and x["top3_overlap"] > o["top3_overlap"])
    except (KeyError, TypeError):
        return None


def _baseline_line(ev):
    """One sentence on how the model compares with grid baselines, from the saved evaluation."""
    beat = _beats(ev)
    if beat is None:
        return ""
    span = f'{ev["races"]} races through {ev["through"]["year"]} round {ev["through"]["round"]}'
    verdict = ("Has beaten a grid-order baseline on Brier score, log loss and top-3 overlap"
               if beat else "Has not yet beaten a grid-order baseline")
    return f"{verdict} ({span})."


def _method_table(ev):
    """Small comparison table from the saved evaluation, or empty text if there is none."""
    if _beats(ev) is None:
        return ""
    rows = ""
    for key, label in (("grid order", "First three on the grid"), ("grid logistic", "Formula on grid position only"),
                       ("xgboost", "SlipStream model")):
        m = ev["models"][key]
        pct = lambda v: "n/a" if v is None else f"{v * 100:.1f}%"
        num = lambda v: "n/a" if v is None else f"{v:.3f}"
        rows += (f'<tr><td>{label}</td><td class="num">{pct(m["top3_overlap"])}</td><td class="num">{pct(m["exact_podium"])}</td>'
                 f'<td class="num">{num(m["brier"])}</td><td class="num">{num(m["logloss"])}</td></tr>')
    span = f'{ev["races"]} races, through {ev["through"]["year"]} round {ev["through"]["round"]}'
    return (f'<div class="scroll"><table><caption>{span}</caption><thead><tr><th scope="col">Method</th>'
            '<th scope="col" class="num">Top-3 overlap</th><th scope="col" class="num">Exact podium</th>'
            '<th scope="col" class="num">Brier score</th><th scope="col" class="num">Log loss</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def _method_html(ev):
    """The "How it works" section, in plain words. Numbers come from the saved evaluation."""
    beat = _beats(ev)
    verdict = ""
    if beat is True:
        verdict = "<p>On every one of these measures the model does better than both simple guesses.</p>"
    elif beat is False:
        verdict = ("<p>So far the model has not clearly beaten the two simple guesses, so treat its picks with care. "
                   "That is why the top of each page says so.</p>")
    return f"""<section class="method" aria-labelledby="how">
<h2 class="label" id="how">How it works</h2>
<div class="mrow"><h3>What the model looks at</h3><div class="mtext">
<p>For every driver in a race, the model gets a short list of facts that were known before the start:</p>
<ul>
<li>Where the driver starts, where they qualified, and how far they were from the pole time.</li>
<li>How they finished in their last five races, and how often they retire.</li>
<li>How many points their team has scored lately, and how often the team's cars retire.</li>
<li>How often cars retire at this circuit, how many places drivers usually gain or lose there, whether it is a street circuit, and its altitude.</li>
</ul>
<p>Nothing from the race itself is ever used. That is the one rule the project is built around: a prediction for a race only uses what was known before that race.</p>
</div></div>
<div class="mrow"><h3>How it turns facts into a percentage</h3><div class="mtext">
<p>The model is XGBoost. It builds many small decision trees. Each tree asks simple questions, like "does this driver start in the top three?" or "has this team been scoring well?", and nudges the answer a little. Together, the trees settle on one number.</p>
<p>To learn, the model looks at every earlier race. For each driver it sees the facts above and whether they finished on the podium (the top three). Over time it learns which combinations of facts usually lead to a podium. For a new race, it gives each driver a number from 0% to 100%: how likely that driver is to finish in the top three, judging by how similar drivers did before. It is not a simulation of the race.</p>
<p>Each driver gets their own number, and a podium has three places, so across the whole field the numbers add up to around 300%, not 100%. A driver at 80% is not "80% to win". It means the model thinks a podium is very likely.</p>
</div></div>
<div class="mrow"><h3>Why each pick has reasons</h3><div class="mtext">
<p>Under each of the three picks you see the three facts that moved the number most. They come from a method called SHAP. A plus sign means the fact raised the driver's chance. A minus sign means it lowered it. The strongest comes first.</p>
</div></div>
<div class="mrow"><h3>How it is checked</h3><div class="mtext">
<p>A model can look clever by accident if it has already seen the answers. So every race is tested like this: pretend it is the day before that race, teach the model only with earlier races, make the predictions, then compare them with what really happened. This is called walk-forward testing, and it is repeated for every race after the first five.</p>
<p>The model is also compared with two simple guesses. One says the first three on the grid will finish on the podium. The other is a basic formula that only looks at starting position. If the model cannot beat these, it has not added anything useful.</p>
{_method_table(ev)}
<p>Top-3 overlap is the share of the real podium drivers that were in the model's top three picks. Exact podium counts the races where all three picks were right. Brier score and log loss judge the percentages themselves. For both of those, lower is better.</p>
{verdict}</div></div>
<div class="mrow"><h3>What it does not know</h3><div class="mtext">
<p>It does not know about grid penalties, because it uses the qualifying order. It also knows nothing about weather, tyre choices, safety cars or car upgrades, and it has only a few seasons of results, so some circuits have little history. The percentages are raw model output. They have not been checked for calibration, so a "70%" may not come true seven times in ten.</p>
<p>Treat the numbers as a ranking of who looks strongest, not as a promise. Results and qualifying come from the Jolpica F1 API.</p>
</div></div>
</section>"""


def _outcome(d):
    """Finished text for a driver in a backtest: ('DNF' | ordinal | None)."""
    status, pos = d.get("status"), d.get("actual_position")
    if status is not None and not FINISHED.search(status):
        return "DNF"
    return None if pos is None else _ordinal(pos)


def _load_outcome(p):
    """The saved result for a prediction, or None if the race has not been scored yet."""
    f = OUTCOMES / f'{p["year"]}_R{p["round"]:02d}.json'
    return json.loads(f.read_text()) if f.exists() else None


def _apply_outcome(p, o):
    """A copy of the prediction with the real result filled in. The saved prediction is never changed."""
    if not o:
        return p
    drivers = []
    for d in p["drivers"]:
        got = o["drivers"].get(d["driver"], {})
        drivers.append(dict(d, actual_position=got.get("position"), status=got.get("status")))
    return dict(p, mode="scored", outcome_utc=o["created_utc"], drivers=drivers)


def _is_hit(d):
    return _outcome(d) not in (None, "DNF") and d["actual_position"] <= 3


TAG_LABELS = {"scored": "post-race"}


def _debrief(drivers, names, evaluation):
    """Post-race section: the real podium next to what the model expected, plus plain-words insights."""
    def who(d):
        first, last = _names(d["driver"], names)
        return f"{first} {last}".strip()

    rank = {d["driver"]: i + 1 for i, d in enumerate(drivers)}
    podium = sorted((d for d in drivers if _is_hit(d)), key=lambda d: d["actual_position"])
    if not podium:
        return ""
    rows = ""
    for d in podium:
        style, cls = _team_style(d["team"])
        grid = d["grid"] if d["grid"] is not None else "-"
        rows += (f'<tr class="{cls.strip()}"{style}><td class="num">{d["actual_position"]}</td>'
                 f'<td><div class="cell"><span class="sv"></span>{escape(d["driver"])}</div></td>'
                 f'<td class="team-col">{escape(str(d["team"]))}</td><td class="num">{grid}</td>'
                 f'<td class="num">{rank[d["driver"]]}</td><td class="num">{d["p_podium"] * 100:.1f}%</td></tr>')

    notes = []
    winner = podium[0]
    if winner["actual_position"] == 1:
        notes.append(f'{who(winner)} won. The model ranked them {_ordinal(rank[winner["driver"]])}, '
                     f'with a {winner["p_podium"] * 100:.1f}% podium chance.')
    surprise = max(podium, key=lambda d: rank[d["driver"]])
    if rank[surprise["driver"]] > 3:
        notes.append(f'Biggest surprise: {who(surprise)} finished {_ordinal(surprise["actual_position"])} '
                     f'after being ranked {_ordinal(rank[surprise["driver"]])} at {surprise["p_podium"] * 100:.1f}%.')
    misses = [d for d in drivers[:3] if not _is_hit(d)]
    if misses:
        m = min(misses, key=lambda d: -(d["actual_position"] or 99) if _outcome(d) != "DNF" else -99)
        res = _outcome(m)
        end = "did not finish" if res == "DNF" else f"finished {res}" if res else "has no recorded result"
        notes.append(f'Biggest miss: {who(m)} was ranked {_ordinal(rank[m["driver"]])} at '
                     f'{m["p_podium"] * 100:.1f}% and {end}.')
    pole = next((d for d in drivers if d["grid"] == 1), None)
    if pole and _outcome(pole):
        res = _outcome(pole)
        notes.append(f'Pole sitter {who(pole)} ' + ("did not finish." if res == "DNF" else f"finished {res}."))
    scored = [d for d in drivers if _outcome(d) is not None]
    if scored:
        brier = sum((d["p_podium"] - float(_is_hit(d))) ** 2 for d in scored) / len(scored)
        avg = ((evaluation or {}).get("models", {}).get("xgboost", {}) or {}).get("brier")
        line = f"Score for this race (Brier, lower is better): {brier:.3f}."
        if avg:
            line += f" The average over earlier races is {avg:.3f}, so this one went " + ("better." if brier < avg else "worse.")
        notes.append(line)

    items = "".join(f"<li>{n}</li>" for n in notes)
    return f"""<h2 class="label">Cool-down room: how the prediction did</h2>
<div class="scroll"><table><thead><tr><th scope="col" class="num">Finish</th><th scope="col">Driver</th><th scope="col" class="team-col">Team</th>
<th scope="col" class="num">Grid</th><th scope="col" class="num">Model rank</th><th scope="col" class="num">Podium probability</th></tr></thead>
<tbody>{rows}</tbody></table></div>
<ul class="insights">{items}</ul>"""


def render_body(p: dict, evaluation=None, names=None) -> str:
    """Everything in a race report below its title: meta, picks, full field table."""
    drivers = p["drivers"]
    picks = drivers[:3]
    backtest = p["mode"] in ("backtest", "scored")
    evaluation = p.get("evaluation") or evaluation

    cards = ""
    for i, d in enumerate(picks):
        grid = f'starts {_ordinal(d["grid"])}' if d["grid"] is not None else "grid unknown"
        first, last = _names(d["driver"], names)
        out = ""
        if backtest:
            res = _outcome(d)
            text = {"DNF": "Did not finish", None: "Result missing"}.get(res, f"Finished {res}")
            mark = '<span class="mark">Hit</span>' if _is_hit(d) else '<span class="mark miss">Miss</span>'
            out = f'<p class="outcome">{mark} {text}</p>'
        cards += (
            f'<article class="card p{i + 1}"{_card_style(d["team"])}><div class="cbody"><p class="pick">P{i + 1}</p>'
            f'<p class="team">{escape(str(d["team"]))} · {grid}</p>'
            f'<div class="score"><p class="pct">{d["p_podium"] * 100:.1f}%</p><p class="sub">podium probability</p></div>'
            f'{out}{_reasons(d["reasons"])}</div>'
            f'<div class="cname">' + (f'<p class="first">{first}</p>' if first else "")
            + f'<p class="last">{last}</p></div></article>')

    summary = ""
    if backtest:
        hits = sum(_is_hit(d) for d in picks)
        missed = sorted((d for d in drivers[3:] if _is_hit(d)), key=lambda d: d["actual_position"])
        summary = f"{hits} of 3 picks finished on the podium."
        if missed:
            summary += " On the podium but not picked: " + ", ".join(
                f'{escape(d["driver"])} ({_ordinal(d["actual_position"])})' for d in missed) + "."
        summary = f'<p class="summary">{summary}</p>'

    pick_codes = {d["driver"] for d in picks}
    rows = ""
    for i, d in enumerate(drivers):
        style, cls = _team_style(d["team"])
        extra = ""
        if backtest:
            res = _outcome(d)
            call = ""
            if d["driver"] in pick_codes:
                call = '<span class="mark">Hit</span> ' if _is_hit(d) else '<span class="mark miss">Miss</span> '
            extra = f'<td class="num fin">{call}<span class="pos">{"n/a" if res is None else res}</span></td>'
        grid = d["grid"] if d["grid"] is not None else "-"
        rows += (
            f'<tr class="{cls.strip()}"{style}><td class="num">{i + 1}</td>'
            f'<td><div class="cell"><span class="sv"></span>{escape(d["driver"])}</div></td>'
            f'<td class="team-col">{escape(str(d["team"]))}</td><td class="num">{grid}</td>'
            f'<td><div class="pb"><div class="bar" aria-hidden="true">'
            f'<i style="width:{min(d["p_podium"], 1) * 100:.1f}%;--i:{i}"></i></div>'
            f'<span class="pv">{d["p_podium"] * 100:.1f}%</span></div></td>{extra}</tr>')
    extra_th = '<th scope="col" class="num">Finished</th>' if backtest else ""

    made = escape(p["created_utc"][:16].replace("T", " ")) + " UTC"
    result_added = (f'<span>Result added {escape(p["outcome_utc"][:16].replace("T", " "))} UTC</span>'
                    if p.get("outcome_utc") else "")
    tag = f'<span class="tag{" back" if backtest else ""}">{escape(TAG_LABELS.get(p["mode"], p["mode"]))}</span>'
    claim = " ".join(s for s in (
        "Raw model output, not calibrated.", _baseline_line(evaluation),
        "Grid is the qualifying order, so penalties are not included.") if s)
    debrief = _debrief(drivers, names, evaluation) if backtest else ""
    return f"""<p class="meta">{tag}<span>Round {p['round']}, {p['year']}</span><span>Trained on {p['trained_on_races']} earlier races</span><span>Made {made}</span>{result_added}</p>
<p class="claim">{escape(claim)}</p>
{summary}<h2 class="label">Highest podium probability</h2>
<section class="podium">{cards}</section>
{debrief}<h2 class="label">Full field</h2>
<div class="scroll"><table><thead><tr><th scope="col" class="num">Rank</th><th scope="col">Driver</th><th scope="col" class="team-col">Team</th>
<th scope="col" class="num">Grid</th><th scope="col">Podium probability</th>{extra_th}</tr></thead>
<tbody>{rows}</tbody></table></div>
<p class="note">Probabilities are independent for each driver, so they do not add up to 100%. Reasons are the three features that moved a pick's score most, strongest first: + raised it, - lowered it.</p>"""


def render(p: dict, evaluation=None, names=None) -> str:
    evaluation = p.get("evaluation") or evaluation
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SlipStream {p['year']} {escape(p['event'])}</title>{FAVICON}{FONT_LINK}{ANALYTICS}<style>{CSS}</style></head><body><main>
{_top(True)}
<h1>{escape(p['event'])}</h1>
{render_body(p, evaluation, names)}
{_method_html(evaluation)}
{CREDIT}
</main></body></html>"""


def _name_lookup():
    """Driver code -> (given, family), taken from the latest rows of results.csv."""
    if not RESULTS_CSV.exists():
        return {}
    df = pd.read_csv(RESULTS_CSV)
    if "FamilyName" not in df.columns:
        return {}
    latest = df.sort_values(["year", "round"]).drop_duplicates("Abbreviation", keep="last")
    return {r.Abbreviation: (str(r.GivenName) if pd.notna(r.GivenName) else "", str(r.FamilyName))
            for r in latest.itertuples() if pd.notna(r.FamilyName)}


def render_index(items, evaluation=None, names=None):
    """Landing page: one row per saved prediction, newest first."""
    rows = ""
    for p in items:
        top = p["drivers"][0]
        first, last = _names(top["driver"], names)
        who = f"{first} {last}".strip()
        backtest = p["mode"] in ("backtest", "scored")
        hits = sum(_is_hit(d) for d in p["drivers"][:3])
        detail = f'Top pick {who}, {top["p_podium"] * 100:.1f}% podium probability'
        status = f"{hits} of 3 picks on the podium" if backtest else "Waiting for the race"
        slug = f'{p["year"]}-R{p["round"]:02d}'
        rows += (f'<li><details id="{slug}"><summary><span><span class="ev">{escape(p["event"])}</span>'
                 f'<p class="meta2">{detail}</p></span><span class="when">Round {p["round"]}, {p["year"]}<br>{status}</span></summary>'
                 f'<div class="rbody">{render_body(p, evaluation, names)}'
                 f'<a class="open" href="{p["year"]}_R{p["round"]:02d}.html">Open as its own page</a></div></details></li>')
    if not rows:
        rows = '<li><p class="meta2" style="padding:16px">No predictions yet.</p></li>'
    claim = " ".join(s for s in ("Raw model output, not calibrated.", _baseline_line(evaluation)) if s)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SlipStream</title>{FAVICON}{FONT_LINK}{ANALYTICS}{INTRO_HEAD}<style>{CSS}</style></head><body>{_intro()}<main>
{_top()}
<h1>Formula 1 podium predictions</h1>
<p class="claim">Made after qualifying and saved before the race, then compared with the result. {escape(claim)}</p>
<h2 class="label">Races</h2>
<ul class="races">{rows}</ul>
<script>(function(){{var d=document.getElementById(location.hash.slice(1));if(d&&d.tagName==="DETAILS")d.open=true}})()</script>
{_method_html(evaluation)}
{CREDIT}
</main>{INTRO_SCRIPT}</body></html>"""


def write_index(fallback=None, names=None):
    items = [json.loads(f.read_text()) for f in PREDICTIONS.glob("*.json")]
    items = [_apply_outcome(p, _load_outcome(p)) for p in items]
    items.sort(key=lambda p: (p["year"], p["round"]), reverse=True)
    ev = (items[0].get("evaluation") if items else None) or fallback
    path = REPORTS / "index.html"
    path.write_text(render_index(items, ev, names))
    return path


def write_report(payload: dict):
    REPORTS.mkdir(parents=True, exist_ok=True)
    payload = _apply_outcome(payload, _load_outcome(payload))
    fallback = json.loads(EVALUATION.read_text()) if EVALUATION.exists() else None
    names = _name_lookup()
    path = REPORTS / f"{payload['year']}_R{payload['round']:02d}.html"
    path.write_text(render(payload, fallback, names))
    write_index(fallback, names)
    return path


if __name__ == "__main__":
    print(write_report(json.load(open(sys.argv[1]))))
