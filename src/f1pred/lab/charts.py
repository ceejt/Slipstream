"""Interactive charts for the Race lab page: data for them, their styles and their scripts.

The page works without JavaScript (every chart has its table inside a closed details element); the script only
adds the charts. Data is embedded in the page as JSON, so the page opens from a file as well as from a server.
"""
import json
import re

from ..report import _team_info


def _key(name):
    return re.sub(r"\W", "", str(name))


def _rgb(h):
    return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def _hex(c):
    return "#" + "".join(f"{round(v):02X}" for v in c)


def _mix(a, b, t):
    """Colour a moved a share t of the way towards b."""
    return _hex([x + (y - x) * t for x, y in zip(_rgb(a), _rgb(b))])


def _lum(h):
    f = lambda v: v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = (f(v / 255) for v in _rgb(h))
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _contrast(a, b):
    hi, lo = sorted((_lum(a), _lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def _readable(colour, bg, towards):
    """The colour, moved towards white or black in small steps until text of it reads at 4.5:1 on bg."""
    for k in range(21):
        c = _mix(colour, towards, k / 20)
        if _contrast(c, bg) >= 4.5:
            return c
    return towards


DARK_BG, LIGHT_BG = "#15151E", "#F7F4F1"


def team_css(pairs):
    """CSS classes that give each driver or team its colours.

    --c is the colour for fills (stripe on dark, card colour on light); --l is for lines and bands, a mid tone on light so
    lines are not near black; --l2 is a lighter tint for a team's second driver; --t is the colour for text, moved until it reads at 4.5:1; --hi is the extreme end of the heatmap ramp (lighter on dark, darker on light).
    """
    dark, light = "", ""
    for key, team in pairs:
        stripe, card = _team_info(team) or ("#888888", "#555555")
        mid = _mix(stripe, card, 0.5)
        dark += f".c-{key}{{--c:{stripe};--l:{stripe};--l2:{_mix(stripe, '#FFFFFF', 0.45)};--hi:{_mix(stripe, '#FFFFFF', 0.45)};--t:{_readable(stripe, DARK_BG, '#FFFFFF')}}}"
        light += f".c-{key}{{--c:{card};--l:{mid};--l2:{_mix(mid, '#FFFFFF', 0.4)};--hi:{_mix(card, '#000000', 0.3)};--t:{_readable(card, LIGHT_BG, '#000000')}}}"
    return f"{dark}@media(prefers-color-scheme:light){{{light}}}"


def build(ch, st):
    """(data for the script, team colour css)."""
    pairs, data = [], {"ch": None, "st": None}
    if ch:
        def rows(rs, driver):
            seen, out = {}, []
            for r in rs:
                team = r["team"] if driver else r["name"]
                k = _key(r["name"])
                n = seen.get(team, 0)
                seen[team] = n + 1
                pairs.append((k, team))
                out.append({"name": r["name"], "key": k, "dash": n > 0, "now": r["now"], "expected": r["expected"],
                            "low": r["low"], "high": r["high"], "p": r["p_title"], "path": r["path"]})
            return out
        labels = ["Now"] + [re.sub(r" Grand Prix$", "", c["event"]) for c in ch["remaining"]]
        data["ch"] = {"year": ch["year"], "after": ch["after_round"], "sims": ch["simulations"], "labels": labels,
                      "drivers": rows(ch["drivers"][:10], True), "constructors": rows(ch["constructors"][:6], False),
                      "decided": {"drivers": ch["driver_title_clinched"], "constructors": ch["constructor_title_clinched"]}}
    if st:
        drivers = []
        for d in st["drivers"]:
            pairs.append((d["driver"], d["team"]))
            drivers.append({"driver": d["driver"], "team": d["team"], "grid": d["grid"], "typical": d["typical"],
                            "typical_plan": d["typical_plan"], "best": d["best"][0], "heat": d["heat"]})
        data["st"] = {"event": st["event"], "laps": st["laps"], "pit_loss": st["pit_loss_s"], "grid_known": st["grid_known"],
                      "drivers": drivers}
    return json.dumps(data, separators=(",", ":")).replace("</", "<\\/"), team_css(pairs)


CSS = """
.subnav{position:sticky;top:0;z-index:5;display:flex;gap:4px;flex-wrap:wrap;background:var(--bg);border-bottom:1px solid var(--rule);margin:0 0 32px}
.subnav a{color:var(--muted);text-decoration:none;font:600 14px/20px var(--body);padding:12px;min-height:44px;border-bottom:2px solid transparent;margin-bottom:-1px}
.subnav a:hover{color:var(--text)}
.subnav a[aria-current=true]{color:var(--text);border-bottom-color:#E10600}
.sec{scroll-margin-top:64px;margin:0 0 64px}
.sec>h2{font:900 24px/28px var(--display);text-transform:uppercase;margin:0 0 8px}
.sec>.lead{font:400 16px/24px var(--body);color:var(--muted);margin:0 0 24px;max-width:54ch;text-wrap:pretty}
.sec p,.sec li,.tile .c{text-wrap:pretty}
.status,.answer{font:400 20px/28px var(--body);margin:0 0 16px;max-width:36em;text-wrap:balance}
.status b,.answer b{font-weight:700}
.status .tc{color:var(--t)}
.trust{display:grid;gap:16px 48px;margin:24px 0 0;border-top:1px solid var(--rule);padding-top:16px}
@media(min-width:735px){.trust{grid-template-columns:1fr 1fr;align-items:start}}
.trust p{font:400 14px/20px var(--body);color:var(--muted);margin:0}
.trust .tl b{color:var(--text)}
.fig{margin:0}.fig figcaption{font:500 12px/16px var(--display);text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 8px}
.figrow{display:grid;grid-template-columns:1fr auto;gap:2px 12px;font:600 14px/20px var(--body);margin:0 0 8px}
.figrow b{font-variant-numeric:tabular-nums}
.figrow i{grid-column:1/3;display:block;height:6px;background:var(--text)}
.figrow:nth-of-type(2) i{background:var(--muted)}
.fig p{margin:4px 0 0}
.notes{list-style:none;margin:24px 0 0;padding:0;max-width:54ch}
.notes li{font:400 14px/20px var(--body);color:var(--muted);padding:12px 0;border-top:1px solid var(--rule)}
.notes b{color:var(--text)}
.tiles{display:grid;gap:16px;margin:0 0 48px}
@media(min-width:735px){.tiles{grid-template-columns:repeat(3,1fr)}}
.tile{background:var(--surface);border:1px solid var(--rule);padding:16px}
.tile .k{font:500 12px/16px var(--display);text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 8px}
.tile .v{font:900 32px/36px var(--display);margin:0 0 8px}
.tile .v .tc{color:var(--t)}
.tile .c{font:400 14px/20px var(--body);color:var(--muted);margin:0}
.tile .c a{color:var(--text);text-underline-offset:3px;display:inline-block;padding:12px 0;margin:-12px 0}
.panel-lab{background:var(--surface);border:1px solid var(--rule);padding:16px;margin:0 0 16px}
.seg{display:inline-flex;border:1px solid var(--rule);margin:0 8px 16px 0}
.seg button,.chip{background:none;border:0;color:var(--muted);font:600 14px/20px var(--body);padding:10px 16px;min-height:44px;cursor:pointer}
.seg button+button{border-left:1px solid var(--rule)}
.seg button[aria-pressed=true]{background:var(--surface-2);color:var(--text)}
.seg button:hover,.chip:hover{color:var(--text)}
.chip{border:1px solid var(--rule);margin:0 8px 8px 0;padding:6px 12px;min-height:44px}
.chip[aria-pressed=true]{background:var(--surface-2);color:var(--text)}
.fan-wrap{display:grid;gap:16px}
@media(min-width:735px){.fan-wrap{grid-template-columns:1fr 240px}}
.lab svg{display:block;width:100%;height:auto;overflow:visible}
.lab svg text{font:600 12px var(--body);fill:var(--muted)}
.lab svg .grid{stroke:var(--rule);stroke-width:1}
.lab svg .axis{fill:var(--muted)}
.lab .alt{--l:var(--l2)}
.lab svg .band{fill:var(--l);opacity:.16}
.lab svg.dense .band{opacity:.09}
.lab svg .line{fill:none;stroke:var(--l);stroke-width:2.5;stroke-linejoin:round}
.lab svg .dot{fill:var(--l)}
.lab svg .minor .line{stroke-width:1.5;opacity:.75}
.lab svg .minor .band{opacity:.07}
.lab svg .minor .dot{opacity:.75}
.lab svg .endlab{fill:var(--t);font-weight:700}
.lab svg .cross{stroke:var(--text);stroke-width:1;opacity:.5}
.lab svg .hit{fill:transparent;cursor:crosshair}
.fan-svg:focus-visible,.heat-svg:focus-visible{outline:2px solid var(--text);outline-offset:4px}
.rel{position:relative}
.tip{position:absolute;z-index:3;pointer-events:none;background:var(--surface-2);border:1px solid var(--rule);padding:8px 12px;font:600 14px/20px var(--body);color:var(--text);white-space:nowrap;display:none}
.tip .t{display:block;color:var(--muted);font:500 12px/16px var(--display);text-transform:uppercase;letter-spacing:.5px;margin:0 0 4px}
.tip .r{display:flex;justify-content:space-between;gap:16px;color:var(--t)}
.tip .r b{color:var(--text);font-variant-numeric:tabular-nums}
.tip .u{display:block;color:var(--muted);font-weight:400;font-size:12px;line-height:16px;margin:0 0 4px}
.fan-wrap .tip .r{display:grid;grid-template-columns:3.2em 2.6em auto;gap:12px}
.fan-wrap .tip .r b{text-align:right}
.tip .rg{color:var(--muted);font-weight:400;font-variant-numeric:tabular-nums}
.side{list-style:none;margin:0;padding:0}
.side button{display:grid;grid-template-columns:28px 1fr auto;gap:8px;align-items:center;width:100%;background:none;border:0;border-top:1px solid var(--rule);
color:var(--text);text-align:left;padding:8px 0;min-height:44px;cursor:pointer;font:600 14px/18px var(--body)}
.side button[aria-pressed=false] .nm{text-decoration:line-through;text-decoration-thickness:1px;color:var(--muted)}
.side button[aria-pressed=false] .sw{opacity:.35}
.side button[aria-pressed=false] .p{color:var(--muted);font-weight:400}
.side .more{display:block;grid-template-columns:none}
.more{background:none;border:0;border-top:1px solid var(--rule);color:var(--muted);font:600 14px/20px var(--body);width:100%;text-align:left;padding:12px 0;min-height:44px;cursor:pointer}
.more:hover{color:var(--text)}
.side .sw{width:28px;height:0;border-top:3px solid var(--l)}
.side .sw.dash{border-top-style:dashed}
.side .p{font-variant-numeric:tabular-nums;font-weight:700}
.side small{display:block;color:var(--muted);font-weight:400;font-size:12px}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.pick{display:flex;align-items:center;gap:12px;margin:0 0 16px;font:600 14px/20px var(--body);color:var(--muted)}
.pick select{background:var(--surface);color:var(--text);border:1px solid var(--rule);font:600 14px/20px var(--body);padding:10px 12px;min-height:44px;border-radius:0}
.hint{font:400 14px/20px var(--body);color:var(--muted);margin:8px 0 0;max-width:54ch}
.kbd{font:400 12px/16px var(--body);color:var(--muted);margin:6px 0 0;max-width:60ch}
@media(max-width:734px),(hover:none){.kbd{display:none}}
.heat-svg .cell{fill:var(--c);cursor:pointer}
.heat-svg .tick{stroke:var(--text);stroke-width:2.5}
.planwrap{display:none;margin:0 0 16px}
.pltitle{font:500 12px/16px var(--display);text-transform:uppercase;letter-spacing:.5px;color:var(--muted);margin:0 0 4px}
.planlist{list-style:none;margin:0;padding:0}
.planlist button{display:grid;grid-template-columns:20px 1fr auto;gap:2px 12px;align-items:center;width:100%;text-align:left;background:none;border:0;border-top:1px solid var(--rule);color:var(--text);padding:10px 8px;min-height:44px;font:600 14px/20px var(--body);cursor:pointer}
.planlist button[aria-pressed=true]{background:var(--surface-2)}
.planlist .n{color:var(--muted);font-variant-numeric:tabular-nums}
.planlist b{font-variant-numeric:tabular-nums}
.pbar{grid-column:2/4;height:4px;background:var(--surface-2)}
.planlist button[aria-pressed=true] .pbar{background:var(--surface)}
.pbar i{display:block;height:100%;background:var(--c)}
.cellcap{display:none;font:600 14px/20px var(--body);margin:12px 0 0}
@media(max-width:734px){.planwrap{display:block}.cellcap{display:block}.panel-lab .tip{display:none!important}}
.heat-svg .ring{fill:none;stroke:var(--text);stroke-width:2;pointer-events:none}
.heat-svg .best{fill:none;stroke:var(--text);stroke-width:1.5;stroke-dasharray:4 3;pointer-events:none}
.heat-svg .rowlab{fill:var(--text)}
.detail{margin:16px 0 0;display:grid;gap:16px}
@media(min-width:735px){.detail{grid-template-columns:1fr 1fr}}
.dtitle{font:700 18px/24px var(--body);margin:0 0 8px}
.dstats{display:flex;flex-wrap:wrap;gap:4px 24px;margin:0 0 8px;font:400 14px/20px var(--body);color:var(--muted)}
.dstats b{color:var(--text);font-weight:700;font-variant-numeric:tabular-nums}
.dbar{fill:var(--c)}
.detail svg text{font-size:14px}
.barref{stroke:var(--text);stroke-width:2.5}
.hkey{list-style:none;display:flex;flex-wrap:wrap;gap:8px 24px;margin:12px 0 0;padding:0;font:600 14px/20px var(--body);color:var(--muted)}
.hkey li{display:flex;align-items:center;gap:8px}
.hkey i{display:inline-block;width:24px;height:14px;box-sizing:border-box;border:2px solid var(--text);font-style:normal}
.hkey i.d{border:1.5px dashed var(--text)}
.hkey li[hidden]{display:none}
.scroll:focus-visible{outline:2px solid var(--text);outline-offset:2px}
.cellval{fill:var(--text);stroke:var(--surface);stroke-width:3px;paint-order:stroke;font:700 12px var(--body);text-anchor:middle;pointer-events:none}
.tyre{stroke:var(--rule);stroke-width:1}
.lab svg .tyretxt{fill:#15151E;font-weight:700;text-anchor:middle}
.lab svg .pitlab{font-size:13px;text-anchor:middle}
.lab svg .lead-line{stroke:var(--l);stroke-width:1;opacity:.6}
.tables{margin:16px 0 0}
.tables summary{cursor:pointer;color:var(--muted);font:600 14px/20px var(--body);padding:12px 0;min-height:44px}
.tables summary:hover{color:var(--text)}
.note{font:400 14px/20px var(--body);color:var(--muted);margin:16px 0 0;max-width:54ch}
.verdict p{max-width:54ch;text-wrap:pretty}
.note b{color:var(--text)}
.sec b,.tile b{font-weight:700}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
"""

JS = r"""(function(){
var D=JSON.parse(document.getElementById('lab-data').textContent);
var NS='http://www.w3.org/2000/svg';
var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
function el(n,a,p,t){var e=document.createElementNS(NS,n);for(var k in a)e.setAttribute(k,a[k]);if(t!=null)e.textContent=t;if(p)p.appendChild(e);return e}
function h(t,a,html){var e=document.createElement(t);for(var k in a)e.setAttribute(k,a[k]);if(html!=null)e.innerHTML=html;return e}
function pc(p){return p>0.999?'>99.9%':p<0.001?'<0.1%':(p*100).toFixed(p<0.1?1:0)+'%'}
function cap(s){return s.charAt(0)+s.slice(1).toLowerCase()}
function clear(n){while(n.firstChild)n.removeChild(n.firstChild)}
function ease(t){return 1-Math.pow(1-t,3)}

/* ---------- championship fan chart ---------- */
function fan(root){
  var C=D.ch;if(!C)return;
  var st={mode:'drivers',off:{},all:false,idx:C.labels.length-1,played:true};
  var W=900,H=470,ml=46,mr=110,mt=16,mb=36,pw=W-ml-mr,ph=H-mt-mb,narrow=false;
  var seg=h('div',{'class':'seg',role:'group','aria-label':'Show'});
  var bd=h('button',{type:'button','aria-pressed':'true'},'Drivers'),bc=h('button',{type:'button','aria-pressed':'false'},'Constructors');
  var rep=h('button',{type:'button','class':'chip'},'Replay animation');
  seg.appendChild(bd);seg.appendChild(bc);root.appendChild(seg);root.appendChild(rep);
  var wrap=h('div',{'class':'fan-wrap'});root.appendChild(wrap);
  var left=h('div',{'class':'rel'});wrap.appendChild(left);
  var tip=h('div',{'class':'tip'});left.appendChild(tip);
  document.addEventListener('pointerdown',function(e){if(!left.contains(e.target))tip.style.display='none'});
  function size(){var w=Math.round(left.getBoundingClientRect().width)||900;W=Math.max(300,Math.min(w,900));narrow=W<520;mr=narrow?60:110;ml=narrow?38:46;H=narrow?300:Math.round(W*0.56);pw=W-ml-mr;ph=H-mt-mb}
  var svg=el('svg',{viewBox:'0 0 '+W+' '+H,'class':'fan-svg',role:'img',tabindex:'0',
    'aria-label':'Points after each remaining race, with a 90 percent band. Use the left and right arrow keys to move between races.'},left);
  var hint=h('p',{'class':'hint'});left.appendChild(hint);left.appendChild(h('p',{'class':'kbd'},'Keyboard: click the chart first, then use the left and right arrow keys to step through the races.'));
  var side=h('ul',{'class':'side'});wrap.appendChild(side);
  var out=h('div',{'class':'sr','aria-live':'polite'});root.appendChild(out);
  var clip=null;
  function rows(){return C[st.mode]}
  function lead(){return C.decided[st.mode]?1:0}
  function isOn(r,i){var on=st.off[st.mode+r.key];return on===undefined?((i<6&&i>=lead())||st.all):on}
  function shown(){var r=rows(),s=[];for(var i=0;i<r.length;i++)if(isOn(r[i],i))s.push(r[i]);return s}
  function draw(){
    size();svg.setAttribute('viewBox','0 0 '+W+' '+H);clear(svg);var S=shown(),R=C.labels.length;
    svg.setAttribute('class','fan-svg'+(S.length>4?' dense':''));
    var champ=rows()[0],hid=lead()&&st.off[st.mode+champ.key]===undefined&&!st.all;
    hint.textContent=(hid?champ.name+' has clinched the title, so the chart shows the fight for second. Click '+champ.name+' in the list to add the line. ':'')+'Click a name to show or hide it.';
    var lo=1e9,hi=-1e9;S.forEach(function(r){r.path.low.forEach(function(v){lo=Math.min(lo,v)});r.path.high.forEach(function(v){hi=Math.max(hi,v)})});
    if(!S.length){lo=0;hi=100}
    var step=[10,25,50,100,200].filter(function(s){return (hi-lo)/s<=6})[0]||200;
    lo=Math.floor((lo-5)/step)*step;hi=Math.ceil((hi+5)/step)*step;
    var X=function(i){return ml+pw*i/(R-1)},Y=function(v){return mt+ph*(1-(v-lo)/(hi-lo))};
    for(var v=lo;v<=hi;v+=step){el('line',{x1:ml,x2:ml+pw,y1:Y(v),y2:Y(v),'class':'grid'},svg);el('text',{x:ml-8,y:Y(v)+4,'text-anchor':'end'},svg,v)}
    C.labels.forEach(function(l,i){el('text',{x:X(i),y:H-10,'text-anchor':i==0?'start':i==R-1?'end':'middle'},svg,l)});
    var defs=el('defs',{},svg);clip=el('clipPath',{id:'fanclip'},defs);var cr=el('rect',{x:0,y:0,width:reduce||st.played?W:0,height:H},clip);
    var g=el('g',{'clip-path':'url(#fanclip)'},svg);
    var ends=[];
    S.forEach(function(r){
      var gs=el('g',{'class':'c-'+r.key+(rows().indexOf(r)>=6?' minor':'')+(r.dash?' alt':'')},g),p=r.path,d='';
      for(var i=0;i<R;i++)d+=(i?'L':'M')+X(i)+','+Y(p.high[i]);
      for(var i=R-1;i>=0;i--)d+='L'+X(i)+','+Y(p.low[i]);
      el('path',{d:d+'Z','class':'band'},gs);
      var l='';for(var i=0;i<R;i++)l+=(i?'L':'M')+X(i)+','+Y(p.mean[i]);
      el('path',{d:l,'class':'line','stroke-dasharray':r.dash?'7 5':'none'},gs);
      for(var i=0;i<R;i++){var cx=X(i),cy=Y(p.mean[i]);if(r.dash)el('rect',{x:cx-3.5,y:cy-3.5,width:7,height:7,transform:'rotate(45 '+cx+' '+cy+')','class':'dot'},gs);else el('circle',{cx:cx,cy:cy,r:3,'class':'dot'},gs)}
      ends.push({r:r,y0:Y(p.mean[R-1]),y:Y(p.mean[R-1])});
    });
    ends.sort(function(a,b){return a.y-b.y});
    for(var i=1;i<ends.length;i++)if(ends[i].y<ends[i-1].y+15)ends[i].y=ends[i-1].y+15;
    var labs=el('g',{},svg);
    ends.forEach(function(e){var cl='c-'+e.r.key+(e.r.dash?' alt':'');if(Math.abs(e.y-e.y0)>2)el('line',{x1:ml+pw+2,y1:e.y0,x2:ml+pw+8,y2:e.y,'class':'lead-line '+cl},labs);
      var mk=el('g',{'class':cl},labs);if(e.r.dash)el('rect',{x:ml+pw+10,y:e.y-3,width:6,height:6,transform:'rotate(45 '+(ml+pw+13)+' '+e.y+')','class':'dot'},mk);else el('circle',{cx:ml+pw+13,cy:e.y,r:3,'class':'dot'},mk);
      el('text',{x:ml+pw+22,y:e.y+4,'class':'endlab '+cl},labs,(e.r.name.length>9?e.r.name.slice(0,9):e.r.name)+(narrow?'':' '+Math.round(e.r.path.mean[R-1])))});
    var cross=el('line',{x1:0,x2:0,y1:mt,y2:mt+ph,'class':'cross'},svg);
    var hit=el('rect',{x:ml,y:mt,width:pw,height:ph,'class':'hit'},svg);
    function at(i,ui){st.idx=Math.max(0,Math.min(R-1,i));cross.setAttribute('x1',X(st.idx));cross.setAttribute('x2',X(st.idx));if(!ui||st.lastRead!==st.idx){read();st.lastRead=st.idx}if(ui)showTip(S,X(st.idx));else tip.style.display='none'}
    function showTip(S,x){
      var k=svg.getBoundingClientRect().width/W,i=st.idx,a='<span class="t">After '+(i?C.labels[i]:'round '+C.after)+'</span><span class="u">Average and 90% range</span>';
      S.slice().sort(function(p,q){return q.path.mean[i]-p.path.mean[i]}).forEach(function(r){a+='<span class="r c-'+r.key+'"><span>'+r.name+'</span><b>'+Math.round(r.path.mean[i])+'</b><span class="rg">'+Math.round(r.path.low[i])+' to '+Math.round(r.path.high[i])+'</span></span>'});
      tip.innerHTML=a;tip.style.display='block';
      var w=tip.offsetWidth,px=x*k,lx=px+14;if(lx+w>left.clientWidth)lx=px-w-14;
      tip.style.left=Math.max(0,lx)+'px';tip.style.top=(mt*k+6)+'px';
    }
    hit.addEventListener('pointermove',function(e){var b=svg.getBoundingClientRect();at(Math.round(((e.clientX-b.left)*W/b.width-ml)/pw*(R-1)),true)});
    hit.addEventListener('pointerdown',function(e){var b=svg.getBoundingClientRect();at(Math.round(((e.clientX-b.left)*W/b.width-ml)/pw*(R-1)),true)});
    hit.addEventListener('pointerleave',function(e){if(e.pointerType!=='touch'&&document.activeElement!==svg)tip.style.display='none'});
    svg.onblur=function(){tip.style.display='none'};
    svg.onkeydown=function(e){if(e.key=='ArrowLeft'){at(st.idx-1,true);e.preventDefault()}else if(e.key=='ArrowRight'){at(st.idx+1,true);e.preventDefault()}};
    at(st.idx);
    // side list
    clear(side);
    var all=rows();
    all.forEach(function(r,i){
      if(!st.all&&i>=6)return;
      var on=isOn(r,i);
      var li=h('li');var b=h('button',{type:'button','aria-pressed':on?'true':'false','class':'c-'+r.key+(r.dash?' alt':''),title:'Show or hide '+r.name});
      b.innerHTML='<span class="sw'+(r.dash?' dash':'')+'"></span><span><span class="nm">'+r.name+'</span><small>'+(on?'':'hidden, ')+Math.round(r.now)+' now, '+Math.round(r.expected)+' expected</small></span><span class="p">'+(C.decided[st.mode]?(i==0?'Clinched':''):pc(r.p))+'</span>';
      b.onclick=function(){st.off[st.mode+r.key]=!on;draw()};
      li.appendChild(b);side.appendChild(li);
    });
    if(all.length>6){var li=h('li'),m=h('button',{type:'button','class':'more','aria-expanded':st.all?'true':'false'},st.all?'Show the default view':'Show all '+all.length+(st.mode=='drivers'?' drivers':' teams'));m.onclick=function(){st.all=!st.all;all.forEach(function(r,i){if(i>=6)delete st.off[st.mode+r.key]});draw()};li.appendChild(m);side.appendChild(li)}
  }
  function read(){
    var S=shown(),i=st.idx,a='<div class="t">Points after '+(i?C.labels[i]:'round '+C.after)+(i?'':' (now)')+', average and 90% range</div>';
    S.forEach(function(r){var p=r.path;a+='<div class="c-'+r.key+'"><span class="nm">'+r.name+'</span><b>'+Math.round(p.mean[i])+'</b><span>'+Math.round(p.low[i])+' to '+Math.round(p.high[i])+'</span></div>'});
    out.innerHTML=a;
  }
  function play(){
    st.played=false;draw();if(reduce||!clip){st.played=true;draw();return}
    var t0=null;
    function f(t){if(t0===null)t0=t;var k=Math.min(1,(t-t0)/1500);if(clip&&clip.firstChild)clip.firstChild.setAttribute('width',W*ease(k));if(k<1)requestAnimationFrame(f);else st.played=true}
    requestAnimationFrame(f);
  }
  bd.onclick=function(){st.mode='drivers';bd.setAttribute('aria-pressed','true');bc.setAttribute('aria-pressed','false');st.idx=C.labels.length-1;st.played=true;draw()};
  bc.onclick=function(){st.mode='constructors';bc.setAttribute('aria-pressed','true');bd.setAttribute('aria-pressed','false');st.idx=C.labels.length-1;st.played=true;draw()};
  rep.onclick=play;
  draw();
  var rt=null;window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(draw,150)});
  if('IntersectionObserver' in window&&!reduce){var io=new IntersectionObserver(function(es){if(es[0].isIntersecting){io.disconnect();play()}},{threshold:.35});io.observe(root)}
}

/* ---------- strategy heatmap ---------- */
var GAM=3,CUT=.6;
function hx(v){v=(v||'').trim();return /^#[0-9a-f]{6}$/i.test(v)?[1,3,5].map(function(i){return parseInt(v.substr(i,2),16)}):null}
function mx(a,b,t){return a.map(function(v,i){return v+(b[i]-v)*t})}
function rgb(a){return 'rgb('+a.map(Math.round).join(',')+')'}
function lum(a){var f=a.map(function(v){v/=255;return v<=.03928?v/12.92:Math.pow((v+.055)/1.055,2.4)});return .2126*f[0]+.7152*f[1]+.0722*f[2]}
function ink(a){return a&&(1.05/(lum(a)+.05)>(lum(a)+.05)/.058)?'fill:#FFFFFF;stroke:none':a?'fill:#15151E;stroke:none':''}
var TYRE={SOFT:'#F2433B',MEDIUM:'#FFD12E',HARD:'#F2F2F0'};
function planText(p){var t=p.tyres.map(cap).join(' then ');return p.stops+(p.stops==1?' stop, ':' stops, ')+t+', '+(p.stops==1?'stop on lap ':'stops on laps ')+p.laps.join(' and ')}
function stints(L,rows){
  var W=420,lw=104,rh=30,H=rows.length*rh+6;
  var s=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Tyre stints for the selected plan against other plans'});
  rows.forEach(function(r,i){
    var y=i*rh+14,x0=lw,sw=W-lw-4,b=[0].concat(r.plan.laps).concat([L]);
    el('text',{x:0,y:y+12},s,r.label);
    for(var k=0;k<b.length-1;k++){
      var xa=x0+sw*b[k]/L,xb=x0+sw*b[k+1]/L,c=r.plan.tyres[Math.min(k,r.plan.tyres.length-1)];
      el('rect',{x:xa,y:y,width:Math.max(xb-xa-1,1),height:18,fill:TYRE[c],'class':'tyre'},s);
      el('text',{x:(xa+xb)/2,y:y+13,'class':'tyretxt'},s,c.charAt(0));
      if(k>0)el('text',{x:xa,y:y-3,'class':'pitlab'},s,r.plan.laps[k-1]);
    }
  });
  return s;
}
function dist(d,ref){
  var W=420,H=120,mt=8,mb=22,pw=W-8,bw=pw/11,mx=Math.max.apply(null,d.concat(ref||[]).concat([.05]));
  var s=el('svg',{viewBox:'0 0 '+W+' '+H,role:'img','aria-label':'Chance of each finishing position'});
  d.forEach(function(v,i){
    var hh=(H-mt-mb)*v/mx,x=4+i*bw;
    el('rect',{x:x+3,y:H-mb-hh,width:bw-6,height:Math.max(hh,1),'class':'dbar'},s);
    el('text',{x:x+bw/2,y:H-6,'text-anchor':'middle'},s,i<10?'P'+(i+1):'11+');
    var rh=ref?(H-mt-mb)*ref[i]/mx:0;if(Math.max(hh,rh)>14)el('text',{x:x+bw/2,y:H-mb-Math.max(hh,rh)-5,'text-anchor':'middle'},s,Math.round(v*100));
    if(ref)el('line',{x1:x+1,x2:x+bw-1,y1:H-mb-rh,y2:H-mb-rh,'class':'barref'},s);
  });
  return s;
}
function heat(root){
  var S=D.st;if(!S)return;
  var di=0,sel=null,hv=null;
  var tabs=h('label',{'class':'pick'},'Driver '),pk=h('select',{});tabs.appendChild(pk);root.appendChild(tabs);
  var pw=h('div',{'class':'planwrap'});root.appendChild(pw);
  var box=h('div',{'class':'panel-lab rel'});root.appendChild(box);
  var tip=h('div',{'class':'tip'});box.appendChild(tip);
  var quick=h('div');root.appendChild(quick);
  var detail=h('div',{'class':'detail','aria-live':'polite'});root.appendChild(detail);
  var svg=el('svg',{'class':'heat-svg',role:'application',tabindex:'0','aria-label':'Expected points for each one stop plan. Use the arrow keys to move between plans, or B for the best plan.'});
  box.appendChild(svg);
  S.drivers.forEach(function(d,i){pk.appendChild(h('option',{value:i},d.driver+' ('+d.team+')'))});
  var ccap=h('p',{'class':'cellcap'});box.appendChild(ccap);
  pk.onchange=function(){di=+pk.value;sel=null;draw()};
  var hk=h('ul',{'class':'hkey','aria-label':'How to read the squares'});box.appendChild(hk);
  [['sel','Plan shown'],['d','Best plan']].forEach(function(k){var li=h('li');li.appendChild(h('i',{'class':k[0],'aria-hidden':'true'}));li.appendChild(document.createTextNode(k[1]));hk.appendChild(li)});
  var nt=h('span',{},' The three highest squares show their points.');
  var hn=h('p',{'class':'hint'},'Columns are the lap of the stop.');hn.appendChild(nt);box.appendChild(hn);box.appendChild(h('p',{'class':'kbd'},'Keyboard: click the grid first, then use the arrow keys to move between plans, or B to jump to the best plan.'));
  var G={};
  function cells(){var d=S.drivers[di],H=d.heat,v=[];H.points.forEach(function(r){r.forEach(function(x){v.push(x)})});return {min:Math.min.apply(null,v),max:Math.max.apply(null,v)}}
  function pick(r,c,ui){var d=S.drivers[di],H=d.heat;sel={r:r,c:c,plan:{stops:1,laps:[H.laps[c]],tyres:H.orders[r]},m:{points:H.points[r][c],podium:H.podium[r][c],win:H.win[r][c],dist:H.dist[r][c]}};mark();info();if(ui)cellTip(r,c);else tip.style.display='none'}
  function cellTip(r,c){
    var d=S.drivers[di],H=d.heat,m=sel.m,b=svg.getBoundingClientRect(),bb=box.getBoundingClientRect(),k=b.width/G.W;
    tip.innerHTML='<span class="t">'+cap(H.orders[r][0])+' then '+cap(H.orders[r][1])+', stop on lap '+H.laps[c]+'</span><span class="r"><span>Expected points</span><b>'+m.points.toFixed(1)+'</b></span><span class="r"><span>Podium</span><b>'+Math.round(m.podium*100)+'%</b></span><span class="r"><span>Win</span><b>'+Math.round(m.win*100)+'%</b></span>';
    tip.style.display='block';var w=tip.offsetWidth,hh=tip.offsetHeight,cx=b.left-bb.left+(G.ml+c*G.cw+G.cw/2)*k,cy=b.top-bb.top+(G.mt+r*G.rh)*k;
    var lx=Math.min(Math.max(4,cx-w/2),box.clientWidth-w-4),ty=cy-hh-8;if(ty<4)ty=cy+G.rh*k+8;
    tip.style.left=lx+'px';tip.style.top=ty+'px';
  }
  function choose(plan,m){sel={r:null,c:null,plan:plan,m:m};mark();info()}
  function draw(){
    var keep=sel;clear(svg);var d=S.drivers[di],H=d.heat,nL=H.laps.length,nO=H.orders.length;
    var W=Math.max(300,Math.min(Math.round(box.clientWidth-34)||900,900)),nar=W<520,ml=nar?108:150,mr=8,mt=28,cw=(W-ml-mr)/nL,rh=nar?30:36,ph=nO*rh,Ht=mt+ph+(nar?60:58);
    svg.setAttribute('viewBox','0 0 '+W+' '+Ht);svg.setAttribute('class','heat-svg c-'+d.driver);
    var r0=cells(),best=null,all=[];
    var cs=getComputedStyle(svg),C0=hx(cs.getPropertyValue('--surface')),C1=hx(cs.getPropertyValue('--c')),C2=hx(cs.getPropertyValue('--hi'));
    function toneA(k){if(!C0||!C1||!C2)return null;var u=Math.pow(k,GAM),b=mx(C0,C1,.28+.72*Math.min(1,u/CUT));return u>CUT?mx(b,C2,(u-CUT)/(1-CUT)):b}
    function tone(k){var a=toneA(k);return a?rgb(a):null}
    var fills={};
    H.orders.forEach(function(o,r){
      el('text',{x:ml-10,y:mt+r*rh+rh/2+4,'text-anchor':'end','class':'rowlab'},svg,cap(o[0])+' then '+cap(o[1]));
      H.laps.forEach(function(lap,c){
        var v=H.points[r][c],k=(v-r0.min)/Math.max(r0.max-r0.min,.01);
        var ta=toneA(k),tn=ta&&rgb(ta),a={x:ml+c*cw+.5,y:mt+r*rh+.5,width:cw-1,height:rh-1,'class':'cell'};if(tn)a.style='fill:'+tn;else a['fill-opacity']=(.22+.78*Math.pow(k,GAM)).toFixed(3);el('rect',a,svg);
        fills[r+','+c]=ta;all.push({v:v,r:r,c:c});if(!best||v>best.v)best={v:v,r:r,c:c};
      });
    });
    H.laps.forEach(function(lap,c){if(c%(nar?6:4)==0)el('text',{x:ml+c*cw+cw/2,y:mt-10,'text-anchor':'middle'},svg,lap)});
    G={ml:ml,mt:mt,cw:cw,rh:rh,W:W,nL:nL,nO:nO,best:best};nt.hidden=cw<26;
    el('rect',{x:ml+best.c*cw-1,y:mt+best.r*rh-1,width:cw+2,height:rh+2,'class':'best'},svg);
    var ring=el('rect',{x:0,y:0,width:cw,height:rh,'class':'ring',id:'heatring'},svg);G.ring=ring;
    G.top={};all.sort(function(p,q){return q.v-p.v});
    if(cw>=26){all.slice(0,3).forEach(function(t){G.top[t.r+','+t.c]=1;el('text',{x:ml+t.c*cw+cw/2,y:mt+t.r*rh+rh/2+4,'class':'cellval',style:ink(fills[t.r+','+t.c])},svg,t.v.toFixed(1))});G.fills=fills;G.vs=el('text',{'class':'cellval',visibility:'hidden'},svg,'')}else{G.vs=null}
    // legend
    var ly=mt+ph+22,defs=el('defs',{},svg),lg=el('linearGradient',{id:'heatgrad'},defs);
    [0,.2,.4,.6,.8,1].forEach(function(o){var tn=tone(o);el('stop',{offset:o,style:tn?'stop-color:'+tn:'stop-color:var(--c);stop-opacity:'+(.22+.78*Math.pow(o,GAM)).toFixed(3)},lg)});
    var lw=Math.min(260,W-ml-8);el('rect',{x:ml,y:ly,width:lw,height:10,fill:'url(#heatgrad)'},svg);
    el('text',{x:ml,y:ly+26},svg,r0.min.toFixed(1)+' points');el('text',{x:ml+lw,y:ly+26,'text-anchor':'end'},svg,r0.max.toFixed(1));
    var tp=d.typical.points,tk=(tp-r0.min)/Math.max(r0.max-r0.min,.01);
    if(tk>=0&&tk<=1){el('line',{x1:ml+lw*tk,x2:ml+lw*tk,y1:ly-6,y2:ly+16,'class':'tick'},svg);el('text',{x:ml+lw*tk,y:ly+26,'text-anchor':'middle'},svg,'typical '+tp.toFixed(1))}
    else el('text',{x:ml+lw/2,y:ly+26,'text-anchor':'middle'},svg,'typical plan: '+tp.toFixed(1)+' (below this range)');
    clear(pw);pw.className='planwrap c-'+d.driver;
    var ord=H.orders.map(function(o,r){var bc=0;H.points[r].forEach(function(v,c){if(v>H.points[r][bc])bc=c});return {r:r,c:bc,v:H.points[r][bc]}}).sort(function(p,q){return q.v-p.v}).slice(0,5);
    pw.appendChild(h('p',{'class':'pltitle'},'Best stop lap for each tyre order, top '+ord.length));
    var ol=h('ol',{'class':'planlist'});pw.appendChild(ol);
    ord.forEach(function(o,i){
      var li=h('li'),b=h('button',{type:'button','aria-pressed':'false','data-r':o.r,'data-c':o.c});
      b.innerHTML='<span class="n">'+(i+1)+'</span><span>'+cap(H.orders[o.r][0])+' then '+cap(H.orders[o.r][1])+', stop on lap '+H.laps[o.c]+'</span><b>'+o.v.toFixed(1)+'</b><span class="pbar"><i style="width:'+Math.max(4,Math.round(100*(o.v-r0.min)/Math.max(r0.max-r0.min,.01)))+'%"></i></span>';
      b.onclick=function(){pick(o.r,o.c,false)};li.appendChild(b);ol.appendChild(li);
    });
    clear(quick);
    [['Best plan overall',function(){choose({stops:d.best.stops,laps:d.best.laps,tyres:d.best.tyres},d.best)}],
     ['Best two stop',function(){var b=H.best_two;choose({stops:b.stops,laps:b.laps,tyres:b.tyres},b)}],
     ['Typical plan for the field',function(){choose(d.typical_plan,d.typical)}]].forEach(function(q){var b=h('button',{type:'button','class':'chip'},q[0]);b.onclick=q[1];quick.appendChild(b)});
    if(keep&&keep.r!==null&&keep.r<nO&&keep.c<nL)pick(keep.r,keep.c);else pick(best.r,best.c);
  }
  function mark(){if(!sel||!G.ring)return;
    [].forEach.call(pw.querySelectorAll('button'),function(b){b.setAttribute('aria-pressed',sel.r!==null&&+b.getAttribute('data-r')===sel.r&&+b.getAttribute('data-c')===sel.c?'true':'false')});
    if(G.vs){if(sel.r===null||G.top[sel.r+','+sel.c])G.vs.setAttribute('visibility','hidden');else{G.vs.setAttribute('visibility','visible');G.vs.setAttribute('style',ink(G.fills[sel.r+','+sel.c]));G.vs.setAttribute('x',G.ml+sel.c*G.cw+G.cw/2);G.vs.setAttribute('y',G.mt+sel.r*G.rh+G.rh/2+4);G.vs.textContent=sel.m.points.toFixed(1)}}
    if(sel.r===null){G.ring.setAttribute('width',0);G.ring.setAttribute('height',0)}else{G.ring.setAttribute('width',G.cw-2);G.ring.setAttribute('height',G.rh-2);G.ring.setAttribute('x',G.ml+sel.c*G.cw+1);G.ring.setAttribute('y',G.mt+sel.r*G.rh+1)}}
  function info(){
    var d=S.drivers[di],m=sel.m,t=d.typical,diff=m.points-t.points;
    ccap.textContent=planText(sel.plan)+': '+m.points.toFixed(1)+' points, podium '+Math.round(m.podium*100)+'%, win '+Math.round(m.win*100)+'%.';
    clear(detail);detail.className='detail c-'+d.driver;
    var a=h('div'),b=h('div');detail.appendChild(a);detail.appendChild(b);
    a.appendChild(h('div',{'class':'dtitle'},planText(sel.plan)));
    a.appendChild(h('div',{'class':'dstats'},'<span>Expected points <b>'+m.points.toFixed(1)+'</b></span><span>Against typical <b>'+(diff>=0?'+':'')+diff.toFixed(1)+'</b></span><span>Podium <b>'+Math.round(m.podium*100)+'%</b></span><span>Win <b>'+Math.round(m.win*100)+'%</b></span>'));
    a.appendChild(h('div',{'class':'dstats'},'Where the driver finishes, percent. The white line marks the typical plan.'));
    a.appendChild(dist(m.dist,t.dist));
    var rows=[{label:'Selected',plan:sel.plan},{label:'Typical',plan:d.typical_plan},{label:'Best overall',plan:{stops:d.best.stops,laps:d.best.laps,tyres:d.best.tyres}},{label:'Best two stop',plan:{stops:d.heat.best_two.stops,laps:d.heat.best_two.laps,tyres:d.heat.best_two.tyres}}];
    var shown=planText(sel.plan),same=[];rows=rows.filter(function(r,i){if(i==0||planText(r.plan)!=shown)return true;same.push(r.label=='Best overall'?'best':r.label.toLowerCase());return false});
    if(same.length)rows[0].label='Selected, '+same.join(', ');
    b.appendChild(h('div',{'class':'dtitle'},'Tyre stints, '+S.laps+' laps'));
    b.appendChild(h('div',{'class':'dstats'},'Letters are the tyre: S soft, M medium, H hard. Numbers are the stop laps.'));
    b.appendChild(stints(S.laps,rows));
  }
  function loc(e){var b=svg.getBoundingClientRect(),x=(e.clientX-b.left)*G.W/b.width,y=(e.clientY-b.top)*(parseFloat(svg.viewBox.baseVal.height))/b.height,c=Math.floor((x-G.ml)/G.cw),r=Math.floor((y-G.mt)/G.rh);return(c>=0&&c<G.nL&&r>=0&&r<G.nO)?[r,c]:null}
  svg.addEventListener('pointermove',function(e){if(e.pointerType=='touch')return;var l=loc(e);if(l&&(!sel||sel.r!==l[0]||sel.c!==l[1]))pick(l[0],l[1],true)});
  svg.addEventListener('pointerleave',function(){if(document.activeElement!==svg)tip.style.display='none'});
  svg.addEventListener('blur',function(){tip.style.display='none'});
  svg.addEventListener('click',function(e){var l=loc(e);if(l)pick(l[0],l[1],true)});
  svg.addEventListener('keydown',function(e){
    var r=sel&&sel.r!==null?sel.r:G.best.r,c=sel&&sel.c!==null?sel.c:G.best.c,k=e.key;
    if(k=='b'||k=='B'){e.preventDefault();pick(G.best.r,G.best.c,true);return}
    if(k=='ArrowLeft')c--;else if(k=='ArrowRight')c++;else if(k=='ArrowUp')r--;else if(k=='ArrowDown')r++;else return;
    e.preventDefault();pick(Math.max(0,Math.min(G.nO-1,r)),Math.max(0,Math.min(G.nL-1,c)),true);
  });
  draw();
  var rt=null;window.addEventListener('resize',function(){clearTimeout(rt);rt=setTimeout(draw,150)});
}

/* ---------- sub navigation ---------- */
function spy(){
  var links=[].slice.call(document.querySelectorAll('.subnav a'));if(!links.length||!('IntersectionObserver' in window))return;
  var io=new IntersectionObserver(function(es){es.forEach(function(e){if(e.isIntersecting){links.forEach(function(a){a.removeAttribute('aria-current')});var a=document.querySelector('.subnav a[href="#'+e.target.id+'"]');if(a)a.setAttribute('aria-current','true')}})},{rootMargin:'-30% 0px -60% 0px'});
  links.forEach(function(a){var s=document.getElementById(a.getAttribute('href').slice(1));if(s)io.observe(s)});
}
/* ---------- tables that scroll sideways can be reached from the keyboard ---------- */
function scrollers(){
  [].forEach.call(document.querySelectorAll('.scroll'),function(s){
    if(s.scrollWidth>s.clientWidth+1){var c=s.querySelector('caption');s.setAttribute('tabindex','0');s.setAttribute('role','region');if(c)s.setAttribute('aria-label',c.textContent)}
    else{s.removeAttribute('tabindex');s.removeAttribute('role');s.removeAttribute('aria-label')}
  });
}
[].forEach.call(document.querySelectorAll('details.tables'),function(d){d.addEventListener('toggle',scrollers)});
window.addEventListener('resize',scrollers);scrollers();
var f=document.getElementById('fan-root'),hm=document.getElementById('heat-root');
if(f){f.classList.add('lab');fan(f)}if(hm){hm.classList.add('lab');heat(hm)}spy();
})();"""
