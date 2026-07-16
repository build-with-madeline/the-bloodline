#!/usr/bin/env python3
"""
Generate the multi-page Bloodline website from structured data.

  data/genealogy.json  (people, unions, edges)  +  data/dynasty.json (page map)
        |
        v
  index.html  +  pages/<dynasty>.html  +  assets/style.css + assets/panzoom.js

Key design points:
  * Each house page renders ONLY its own subgraph, so no single SVG is ever huge.
  * Foreign spouses/children/parents of boundary marriages render as BRIDGE STUBS:
    dashed, muted nodes that hyperlink to that person's home house page. This is
    how the 31 cross-house marriages stitch the site together.
  * The whole Mermaid block is assembled in clean form (-->, <br/>, &bull;) then
    html.escape()'d on emit -> the escaping conventions hold everywhere by construction.
"""
import json
import html
import sys
import hashlib
from pathlib import Path

ROOT = Path("/Users/madelinevinson/Downloads/the-bloodline")
sys.path.insert(0, str(Path(__file__).parent))
from model import load_merged

G = load_merged()
D = json.load(open(ROOT / "data/dynasty.json", encoding="utf-8"))

def _asset_v(name):
    """Content hash for cache-busting; changes only when the asset changes."""
    p = ROOT / "assets" / name
    return hashlib.sha1(p.read_bytes()).hexdigest()[:8] if p.exists() else "0"

CSS_V = _asset_v("style.css")
JS_V = _asset_v("panzoom.js")

PEOPLE = G["people"]
UNIONS = G["unions"]
DYN_OF = D["dynasty_of"]
DYNASTIES = D["dynasties"]           # [(key, title), ...] in page order

# accent color per house (drawn from the couple fills already in use)
ACCENT = {
    "CAROLINGIAN": "#e8dcb0", "KIEV": "#e0c8a8", "HRE": "#d0d8f0",
    "FRANCE": "#f0e8d0", "IBERIA": "#e0d0c8", "NORMANDY": "#f0dcc0",
    "PLANTAGENET": "#fdf0d5", "TUDOR": "#e8d9f0", "SCOTLAND": "#dae3eb",
    "MEDICI": "#e6cba0", "BYZANTIUM": "#cdbce8", "ANTIQUITY": "#d8c4a0", "SCRIPTURE": "#cbb89a",
    "SUMER": "#c98f5a", "EGYPT": "#cba13a", "CHINA": "#7fae86", "INDIA": "#e0913a",
    "ELAM": "#b08a6a", "ASSYRIA": "#8a95ad", "BABYLON": "#c07a4a", "MARI": "#9c7ab0", "YAMHAD": "#b0895a", "HITTITE": "#a86a6a", "HYKSOS": "#c0a24a", "MITANNI": "#6a9ca8", "ARZAWA": "#9aa86a", "CRETE": "#5a9ca0", "MYCENAE": "#c08a6a", "TROY": "#b06a7a", "PHOENICIA": "#5a9c7a", "ARAM": "#a89a5a",
}
SLUG = {k: k.lower() for k, _ in DYNASTIES}
TITLE = dict(DYNASTIES)

def name_of(pid):
    lab = PEOPLE[pid]["label"] or pid
    return lab.split("<br/>")[0]

# ---------- per-page subgraph selection ----------
def page_members(key):
    return {pid for pid, dy in DYN_OF.items() if dy == key}

def build_page_mermaid(key):
    primary = page_members(key)
    # unions relevant to this page: any parent OR child is primary here
    rel = []
    for u in UNIONS.values():
        endpoints = u["parents"] + u["children"]
        if any(p in primary for p in endpoints):
            rel.append(u)
    stubs = set()
    for u in rel:
        for pid in u["parents"] + u["children"]:
            if pid not in primary:
                stubs.add(pid)

    # richer caption: how does this foreign person connect to THIS house?
    def stub_caption(pid):
        rels = []
        for u in rel:
            if pid in u["parents"]:
                other = [p for p in u["parents"] if p != pid]
                if other and other[0] in primary:
                    rels.append(("m", f"m. {name_of(other[0])}"))
                prim_child = [c for c in u["children"] if c in primary]
                if prim_child and not (other and other[0] in primary):
                    rels.append(("par", f"parent of {name_of(prim_child[0])}"))
            if pid in u["children"]:
                prim_par = [p for p in u["parents"] if p in primary]
                if prim_par:
                    rels.append(("child", f"child of {name_of(prim_par[0])}"))
        order = {"m": 0, "child": 1, "par": 2}
        rels.sort(key=lambda r: order.get(r[0], 9))
        return rels[0][1] if rels else ""

    short = lambda t: t.split("—")[0].split("&")[0].strip()

    lines = ["flowchart TD"]
    # primary person nodes
    for pid in sorted(primary):
        lines.append(f'    {pid}["{PEOPLE[pid]["label"]}"]')
    # bridge stub nodes (foreign): name + how they connect + home house
    for pid in sorted(stubs):
        home = DYN_OF[pid]
        cap = stub_caption(pid)
        cap_line = f'<br/><i>{cap}</i>' if cap else ''
        lines.append(f'    {pid}["{name_of(pid)}{cap_line}<br/><i>&#8599; {short(TITLE[home])}</i>"]')
    # union dots
    union_ids = [u["id"] for u in rel]
    for uid in sorted(union_ids):
        lines.append(f'    {uid}(("&bull;"))')
    # edges
    for u in rel:
        for p in u["parents"]:
            lines.append(f'    {p} --> {u["id"]}')
        for c in u["children"]:
            lines.append(f'    {u["id"]} --> {c}')
    # union registry (critical: keeps dots as dots)
    if union_ids:
        lines.append("")
        lines.append(f'    classDef union fill:#a87f2e,stroke:#a87f2e,color:#a87f2e,font-size:9px')
        lines.append(f'    class {",".join(sorted(union_ids))} union')
    # bridge stub styling + click links to home house
    if stubs:
        lines.append("")
        lines.append('    classDef bridge fill:#e9e2cf,stroke:#8a7a55,stroke-width:1px,stroke-dasharray:4 3,color:#5b4a24,font-style:italic')
        lines.append(f'    class {",".join(sorted(stubs))} bridge')
        for pid in sorted(stubs):
            home = DYN_OF[pid]
            # deep-link: land on the home page, centered+highlighted on this person,
            # remembering where we came from for the breadcrumb.
            href = f'./{SLUG[home]}.html?from={key}#{pid}'
            lines.append(f'    click {pid} href "{href}" "Go to {name_of(pid)} in {TITLE[home]}"')
    # primary person fills
    lines.append("")
    for pid in sorted(primary):
        st = PEOPLE[pid].get("style")
        if st:
            lines.append(f'    style {pid} {st}')

    block = "\n".join(lines)
    return html.escape(block, quote=False), len(primary), len(stubs), len(union_ids)

# ---------- HTML shells ----------
def nav_html(active=None):
    items = ['<a href="../index.html">Overview</a>' if active else '<a href="index.html">Overview</a>']
    for k, t in DYNASTIES:
        href = f'{SLUG[k]}.html' if active else f'pages/{SLUG[k]}.html'
        cls = ' class="active"' if k == active else ''
        short = t.split("—")[0].split("&")[0].strip()
        items.append(f'<a href="{href}"{cls} style="--accent:{ACCENT[k]}">{short}</a>')
    return '<nav class="houses">' + "".join(items) + '</nav>'

def page_html(key):
    block, np, ns, nu = build_page_mermaid(key)
    houses_js = json.dumps({SLUG[k]: TITLE[k] for k, _ in DYNASTIES}, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>{TITLE[key]} &mdash; The Bloodline</title>
<link rel="stylesheet" href="../assets/style.css?v={CSS_V}">
</head>
<body class="page">
<header>
  <div class="brand"><a href="../index.html">The Bloodline</a></div>
  <a id="crumb" class="crumb" hidden href="#">&#8592;</a>
  <h1 style="--accent:{ACCENT[key]}">{TITLE[key]}</h1>
  <p class="meta">{np} of this house &middot; {ns} bridge links &middot; &#128081; monarch &middot; &#10013; bishop+ &middot; &#128519; saint</p>
  {nav_html(active=key)}
</header>
<div id="diagram-wrap">
  <div id="graphDiv">
    <pre class="mermaid">
{block}
    </pre>
  </div>
</div>
<div class="hint" id="hint">scroll or pinch to zoom &middot; drag to pan &middot; dashed nodes link to other houses</div>
<div class="controls">
  <button id="zoomIn">+</button>
  <button id="zoomOut">&minus;</button>
  <button id="zoomReset">&#8634;</button>
</div>
<script>window.BL_HOUSES = {houses_js};</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<script src="../assets/panzoom.js?v={JS_V}"></script>
</body>
</html>
"""

def index_html():
    cards = []
    for k, t in DYNASTIES:
        n = len(page_members(k))
        cards.append(f"""    <a class="house-card" href="pages/{SLUG[k]}.html" style="--accent:{ACCENT[k]}">
      <span class="swatch"></span>
      <span class="ht">{t}</span>
      <span class="hn">{n} people</span>
    </a>""")
    total = len(PEOPLE)
    # bridge summary + weighted house-to-house pair counts
    bridges = []
    pair_count = {}
    for u in UNIONS.values():
        ps = u["parents"]
        if len(ps) == 2 and DYN_OF.get(ps[0]) and DYN_OF.get(ps[1]) and DYN_OF[ps[0]] != DYN_OF[ps[1]]:
            bridges.append((name_of(ps[0]), DYN_OF[ps[0]], name_of(ps[1]), DYN_OF[ps[1]]))
            pk = tuple(sorted((DYN_OF[ps[0]], DYN_OF[ps[1]])))
            pair_count[pk] = pair_count.get(pk, 0) + 1

    # house connection map: nodes = houses, edges = marriage counts (clickable)
    short = lambda t: t.split("—")[0].split("&")[0].strip()
    mm = ["flowchart LR"]
    for k, t in DYNASTIES:
        mm.append(f'    {k}["{short(t)}<br/><small>{len(page_members(k))}</small>"]')
    for (h1, h2), n in sorted(pair_count.items(), key=lambda x: -x[1]):
        w = "===" if n >= 3 else "---"
        mm.append(f'    {h1} {w}|{n}| {h2}')
    mm.append(f'    classDef h fill:#efe6d0,stroke:#c7a24f,color:#232b46,font-weight:600')
    mm.append(f'    class {",".join(k for k,_ in DYNASTIES)} h')
    for k, _ in DYNASTIES:
        mm.append(f'    style {k} fill:{ACCENT[k]}')
        mm.append(f'    click {k} href "pages/{SLUG[k]}.html" "Open {short(TITLE[k])}"')
    housemap = html.escape("\n".join(mm), quote=False)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>The Bloodline</title>
<link rel="stylesheet" href="assets/style.css?v={CSS_V}">
</head>
<body class="landing">
<div class="hero">
  <h1>The Bloodline</h1>
  <p class="sub">One connected descent through ten royal houses of medieval and early-modern Europe</p>
  <p class="stat">{total} people &middot; {len(bridges)} cross-house marriages &middot; Carolingians &rarr; Tudors &amp; Stewarts</p>
</div>

<section class="mapwrap">
  <h2>How the houses connect</h2>
  <p class="mapsub">Each link is a marriage between two houses; thicker lines join houses that intermarried most. Click a house to open it.</p>
  <div class="housemap"><pre class="mermaid">
{housemap}
  </pre></div>
</section>

<div class="house-grid">
{chr(10).join(cards)}
</div>
<footer>
  <p>Choose a house to explore its tree. Dashed nodes inside each house link to the houses they married into.</p>
</footer>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<script>
  mermaid.initialize({{ startOnLoad: true, theme: 'base', securityLevel: 'loose',
    flowchart: {{ curve: 'basis', useMaxWidth: true, htmlLabels: true }} }});
  // Native SVG <a> from a foreignObject label doesn't reliably navigate, so
  // resolve the nearest anchor ourselves when a house node is clicked.
  document.querySelector('.housemap').addEventListener('click', function (e) {{
    var a = e.target && e.target.closest ? e.target.closest('a') : null;
    var href = a && (a.getAttribute('href') || a.getAttributeNS('http://www.w3.org/1999/xlink', 'href'));
    if (href) {{ window.location.href = href; }}
  }});
</script>
</body>
</html>
"""

# ---------- single "one crazy page": the whole tree in one diagram ----------
def build_full_mermaid():
    lines = ["flowchart TD"]
    for pid in sorted(PEOPLE):
        lines.append(f'    {pid}["{PEOPLE[pid]["label"]}"]')
    union_ids = sorted(UNIONS)
    for uid in union_ids:
        lines.append(f'    {uid}(("&bull;"))')
    for u in UNIONS.values():
        for p in u["parents"]:
            lines.append(f'    {p} --> {u["id"]}')
        for c in u["children"]:
            lines.append(f'    {u["id"]} --> {c}')
    lines.append("")
    lines.append('    classDef union fill:#a87f2e,stroke:#a87f2e,color:#a87f2e,font-size:9px')
    lines.append(f'    class {",".join(union_ids)} union')
    lines.append("")
    # keep each person's original couple fill; colour additions by their house
    for pid in sorted(PEOPLE):
        st = PEOPLE[pid].get("style")
        if not st:
            acc = ACCENT.get(DYN_OF.get(pid), "#e8e0d0")
            st = f"fill:{acc},color:#000"
        lines.append(f'    style {pid} {st}')
    return html.escape("\n".join(lines), quote=False)

def full_page_html():
    block = build_full_mermaid()
    people_js = json.dumps([{"id": pid, "n": name_of(pid)} for pid in sorted(PEOPLE)],
                           ensure_ascii=False)
    total = len(PEOPLE)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>The Bloodline &mdash; Full Tree</title>
<link rel="stylesheet" href="assets/style.css?v={CSS_V}">
</head>
<body class="page full">
<header>
  <div class="brand"><a href="index.html">The Bloodline</a> &middot; full tree</div>
  <h1>The Bloodline</h1>
  <p class="meta">{total} people, one tree &middot; &#128081; monarch &middot; &#10013; bishop+ &middot; &#128519; saint</p>
  <div class="searchbar">
    <input id="search" type="search" placeholder="Find a person (e.g. Otto, Eleanor, Bruce)&hellip;" autocomplete="off">
    <button id="searchGo">Find</button>
  </div>
</header>
<div id="diagram-wrap">
  <div id="graphDiv">
    <pre class="mermaid">
{block}
    </pre>
  </div>
</div>
<div class="hint" id="hint">scroll or pinch to zoom &middot; drag to pan &middot; search to jump to anyone</div>
<div class="controls">
  <button id="zoomIn">+</button>
  <button id="zoomOut">&minus;</button>
  <button id="zoomReset">&#8634;</button>
</div>
<script>window.BL_PEOPLE = {people_js};</script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js"></script>
<script src="assets/panzoom.js?v={JS_V}"></script>
</body>
</html>
"""

# ---------- person-centric explorer (Ancestry-style) ----------
def explorer_html():
    data = {
        "people": {pid: {"label": PEOPLE[pid]["label"], "house": DYN_OF.get(pid),
                         **({"byear": PEOPLE[pid]["byear"]} if PEOPLE[pid].get("byear") is not None else {})}
                   for pid in PEOPLE},
        "unions": [{k: v for k, v in [("parents", u["parents"]), ("children", u["children"]), ("kind", u.get("kind")), ("mistress", u.get("mistress"))] if v is not None} for u in UNIONS.values()],
        "houses": {k: {"title": t.split("—")[0].strip(), "accent": ACCENT[k]} for k, t in DYNASTIES},
        "root": "JOG",
    }
    data_js = json.dumps(data, ensure_ascii=False)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>The Bloodline &mdash; Explorer</title>
<link rel="stylesheet" href="assets/style.css?v={CSS_V}">
</head>
<body class="explorer">
<header class="ex-head">
  <div class="brand"><a href="index.html">The Bloodline</a> &middot; explorer</div>
  <div class="searchbox">
    <input id="search" type="text" placeholder="Search anyone&hellip;" autocomplete="off">
    <div id="results" class="results" hidden></div>
  </div>
  <div class="genctl">
    <span>ancestors</span>
    <button id="upLess">&minus;</button><button id="upMore">+</button>
    <span>descendants</span>
    <button id="downLess">&minus;</button><button id="downMore">+</button>
    <button id="backBtn" title="Back">&#8592;</button>
    <button id="homeBtn" title="Home">&#8962;</button>
  </div>
</header>
<div id="explore-wrap">
  <div id="stage"><svg id="links"></svg></div>
</div>
<aside id="panel" class="panel"></aside>
<div class="controls">
  <button id="zoomIn">+</button>
  <button id="zoomOut">&minus;</button>
  <button id="fitBtn">&#8634;</button>
</div>
<script>window.BL_DATA = {data_js};</script>
<script src="assets/explorer.js?v={_asset_v('explorer.js')}"></script>
</body>
</html>
"""

# ---------- whole tree on one page, explorer card design ----------
def full_tree_html():
    data = {
        "people": {pid: {"label": PEOPLE[pid]["label"], "house": DYN_OF.get(pid),
                         **({"byear": PEOPLE[pid]["byear"]} if PEOPLE[pid].get("byear") is not None else {})}
                   for pid in PEOPLE},
        "unions": [{k: v for k, v in [("parents", u["parents"]), ("children", u["children"]), ("kind", u.get("kind")), ("mistress", u.get("mistress"))] if v is not None} for u in UNIONS.values()],
        "houses": {k: {"title": t.split("—")[0].strip(), "accent": ACCENT[k]} for k, t in DYNASTIES},
        "root": "JOG",
    }
    data_js = json.dumps(data, ensure_ascii=False)
    total = len(PEOPLE)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
<title>The Bloodline &mdash; Full Tree</title>
<link rel="stylesheet" href="assets/style.css?v={CSS_V}">
</head>
<body class="explorer">
<header class="ex-head">
  <div class="brand"><a href="index.html">The Bloodline</a> &middot; full tree</div>
  <div class="searchbox">
    <input id="search" type="text" placeholder="Search {total} people&hellip;" autocomplete="off">
    <div id="results" class="results" hidden></div>
  </div>
  <div class="genctl"><span>{total} people &middot; Adam's line + the ancient king-lists</span></div>
</header>
<div id="explore-wrap">
  <div id="stage"><svg id="links"></svg></div>
</div>
<aside id="panel" class="panel" hidden></aside>
<div class="controls">
  <button id="zoomIn">+</button>
  <button id="zoomOut">&minus;</button>
  <button id="fitBtn">&#8634;</button>
</div>
<script>window.BL_DATA = {data_js};</script>
<script src="assets/fulltree.js?v={_asset_v('fulltree.js')}"></script>
</body>
</html>
"""

def main():
    (ROOT / "assets").mkdir(exist_ok=True)
    # The full connected tree IS the site now. index.html is the front door;
    # bloodline-full.html is kept as an alias so old links still resolve.
    # explorer.html stays as an optional person-centric view.
    # (The per-house split site + single-Mermaid fallback were retired 2026-07-15 —
    #  they were a workaround for Mermaid's single-SVG size ceiling, which fulltree.js removed.)
    (ROOT / "index.html").write_text(full_tree_html(), encoding="utf-8")
    (ROOT / "bloodline-full.html").write_text(full_tree_html(), encoding="utf-8")
    (ROOT / "explorer.html").write_text(explorer_html(), encoding="utf-8")
    print("index.html (full tree) + bloodline-full.html + explorer.html written")

if __name__ == "__main__":
    main()
