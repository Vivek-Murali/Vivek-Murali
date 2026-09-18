#!/usr/bin/env python3
"""Render the terminal-style SVG cards used by the profile README.

Run:  python3 assets/cards.py

Everything the cards display lives in DATA below - edit it and re-run to refresh
the profile. Data-mark colours come from SERIES, a categorical palette validated
for the dark card surface (lightness band, chroma, CVD separation, contrast).
"""
import base64
import io
import json
import os
from xml.sax.saxutils import escape as esc

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets")
MONO = "'JetBrains Mono', ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
FONT_DIR = os.path.join(OUT, "fonts")          # vendored, so CI needs no system font
FONT_SRC = {"400": FONT_DIR + "/JetBrainsMono-Regular.ttf",
            "700": FONT_DIR + "/JetBrainsMono-Bold.ttf"}
GLYPHS = set()          # every character the cards actually draw

# ----------------------------------------------------------------- palette --
C = {
    "card":   "#14171c",
    "head":   "#1b1f26",
    "line":   "#262b33",
    "fg":     "#c6cdd6",
    "bright": "#e8eef5",
    "dim":    "#7d8794",
    "faint":  "#5a6370",
    "teal":   "#6ee7d7",
    "violet": "#b39dff",
    "green":  "#7ee787",
    "gold":   "#e3b341",
    "track":  "#252b34",
}
DOTS = ("#e0685d", "#e3ad4a", "#63b95a")
# Validated dark-surface categorical steps, fixed order (never cycled).
SERIES = ["#3987e5", "#d95926", "#199e70", "#c98500",
          "#d55181", "#008300", "#9085e9", "#e66767"]

# -------------------------------------------------------------------- data --
DATA = {
    "id": [("Now", "Data Scientist · AI @ Leo CybSec"),
           ("Before", "Ivoyant Systems · 73 Strings"),
           ("Exp", "7 years making messy data behave"),
           ("Loc", "Peterborough, UK"),
           ("Site", "vivekmurali.info")],
    "stack": [("AI", "LangGraph, GraphRAG, Neo4j, LLM evals"),
              ("Data", "Kafka, Apache Beam, Airflow, Snowflake"),
              ("Cloud", "GCP, Azure, Docker, Kubernetes"),
              ("Lang", "Python, SQL, TypeScript")],
    "highlights": ["Google Data Engineer · Azure DS + DE certified",
                   "PRINCE2 Project Manager",
                   "Building HawkSight, AniGraph, EchoFinance"],
    "building": [
        {"name": "HawkSight", "hue": "teal", "sub": "AI-powered cricket analytics",
         "body": ["YOLO11 ball and player tracking,", "mapped onto a 22-yard pitch grid."],
         "tags": ["YOLO11", "OpenCV", "Streamlit"], "pct": 0.55},
        {"name": "AniGraph", "hue": "violet", "sub": "Multimodal anime knowledge-graph RAG",
         "body": ["Maps the anime production world into", "a graph for multi-hop questions."],
         "tags": ["GraphRAG", "Neo4j", "LLMs"], "pct": 0.4},
        {"name": "EchoFinance", "hue": "green", "sub": "Explainable financial sentiment",
         "body": ["Fuses transcript text and audio for", "fine-grained, auditable sentiment."],
         "tags": ["Multimodal", "XAI", "NLP"], "pct": 0.3},
    ],
    "repos": [
        {"name": "healthcare-cohort-agent", "tags": [],
         "body": ["An end-to-end Healthcare AI pipeline that transforms",
                  "unstructured clinical notes into a Knowledge Graph."],
         "lang": "Python", "dot": "#3987e5", "stars": 0, "forks": 1, "when": "updated 7mo ago"},
        {"name": "Buyer-s-playground", "tags": [],
         "body": ["Implementation of Blockchain with forecasting of",
                  "price in the field of Agriculture and fishery."],
         "lang": "Python", "dot": "#3987e5", "stars": 12, "forks": 2, "when": "updated Dec 2022"},
        {"name": "Spark-Refresher-Projects", "tags": ["#kafka", "#pyspark"],
         "body": ["A collection of Spark projects and exercises",
                  "aimed at refreshing your fundamentals."],
         "lang": "Jupyter Notebook", "dot": "#d95926", "stars": 2, "forks": 0, "when": "updated Aug 2023"},
        {"name": "StreamingPipeline", "tags": [],
         "body": ["Implementation of Kafka pipeline to process and",
                  "validate scrapping information."],
         "lang": "Shell", "dot": "#199e70", "stars": 1, "forks": 0, "when": "updated Jan 2023"},
        {"name": "Scrappers", "tags": ["#nodejs", "#python", "#scrapping"],
         "body": ["Implementation of various scrapping frameworks on",
                  "real time websites (public data extraction only)."],
         "lang": "Python", "dot": "#3987e5", "stars": 6, "forks": 0, "when": "updated Sep 2023"},
        {"name": "CarCrashAnalysis", "tags": ["#data-engineering", "#etl"],
         "body": ["BCG GAMMA case study: car crash analytics with",
                  "PySpark DataFrames and ETL."],
         "lang": "Jupyter Notebook", "dot": "#d95926", "stars": 2, "forks": 0, "when": "updated Jan 2023"},
    ],
    "langs": [("Python", 71.7), ("HTML", 7.5), ("TypeScript", 5.6), ("JSON", 3.4),
              ("JavaScript", 2.0), ("Bash", 1.3), ("YAML", 1.3), ("Markdown", 1.2)],
    "repo_langs": [("Python", 11), ("Jupyter", 6), ("Shell", 3),
                   ("Rust", 2), ("JavaScript", 2), ("Makefile", 1)],
}
# One entity keeps one hue across both charts (Python and JavaScript appear in both).
LANG_HUE = {n: SERIES[i] for i, (n, _) in enumerate(DATA["langs"])}
REPO_HUE = {n: LANG_HUE.get(n, SERIES[i]) for i, (n, _) in enumerate(DATA["repo_langs"])}


# --------------------------------------------------------------- live data --
def load_live():
    """assets/data.json, refreshed daily by the profile-cards workflow.

    Absent (or stale) it simply falls back to DATA, so the cards always render.
    """
    path = os.path.join(OUT, "data.json")
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (ValueError, OSError):
        return {}


LIVE = load_live()


def stat_rows():
    """Build the stats table from live data where it exists."""
    tot = LIVE.get("totals") or {}
    con = LIVE.get("contributions") or {}
    usr = LIVE.get("user") or {}
    wak = LIVE.get("waka") or {}
    if not tot:
        return []          # nothing invented: the workflow supplies these
    rows = [("Public repos", str(tot["public_repos"]),
             "%d original" % tot["original"] if tot.get("original") else ""),
            ("Stars earned", str(tot["stars"]), "own repos"),
            ("Forks", str(tot["forks"]), "")]
    if usr.get("followers") is not None:
        rows.append(("Followers", str(usr["followers"]), ""))
    if con.get("calendar_total") is not None:
        rows.append(("Contributions", str(con["calendar_total"]), "past year"))
    if LIVE.get("commits") is not None:
        rows.append(("Your commits", str(LIVE["commits"]), "bots excluded"))
    if con.get("streak") is not None:
        rows.append(("Streak", "%dd" % con["streak"], "longest %dd" % con.get("longest", 0)))
    if wak.get("total"):
        rows.append(("Coding time", wak["total"].replace(" mins", "m").replace(" hrs", "h"),
                     "WakaTime"))
    if usr.get("years"):
        rows.append(("On GitHub", "%d yrs" % usr["years"], "since %s" % usr.get("since", "")))
    return rows


# ---------------------------------------------------------------- helpers --
def t(x, y, s, fill=None, size=13, weight=None, anchor=None, opacity=None):
    GLYPHS.update(s)
    a = ['x="%s" y="%s"' % (x, y), 'fill="%s"' % (fill or C["fg"]), 'font-size="%s"' % size]
    if weight:
        a.append('font-weight="%s"' % weight)
    if anchor:
        a.append('text-anchor="%s"' % anchor)
    if opacity:
        a.append('opacity="%s"' % opacity)
    return "<text %s>%s</text>" % (" ".join(a), esc(s))


def rect(x, y, w, h, fill, rx=0, stroke=None, sw=1):
    s = ' stroke="%s" stroke-width="%s"' % (stroke, sw) if stroke else ""
    return '<rect x="%s" y="%s" width="%s" height="%s" rx="%s" fill="%s"%s/>' % (x, y, w, h, rx, fill, s)


def window(x, y, w, h, title, r=8, head=30):
    """Terminal chrome: rounded card, header strip, three dots, centred title."""
    p = [rect(x, y, w, h, C["card"], r, C["line"]),
         '<path d="M%s %sh%sv%sH%sz" fill="%s"/>' % (x + r, y + 0.5, w - 2 * r, head, x + r, C["head"]),
         '<path d="M%s %sa%s %s 0 0 1 %s-%s h%s a%s %s 0 0 1 %s %s v%s h-%s z" fill="%s"/>'
         % (x + 0.5, y + r, r, r, r, r, w - 2 * r, r, r, r, r, head - r, w - 1, C["head"]),
         '<line x1="%s" y1="%s" x2="%s" y2="%s" stroke="%s"/>' % (x, y + head, x + w, y + head, C["line"])]
    for i, col in enumerate(DOTS):
        p.append('<circle cx="%s" cy="%s" r="4" fill="%s"/>' % (x + 16 + i * 13, y + head / 2, col))
    p.append(t(x + w / 2, y + head / 2 + 4, title, C["dim"], 12, anchor="middle"))
    return "".join(p)


def chip(x, y, label, fg, bg, size=11):
    w = len(label) * size * 0.62 + 14
    return (rect(x, y, w, 18, bg, 9) + t(x + w / 2, y + 12.5, label, fg, size, anchor="middle")), w


def bar(x, y, w, h, pct, fill, track=None):
    p = rect(x, y, w, h, track or C["track"], h / 2)
    if pct > 0:
        p += rect(x, y, max(h, w * pct), h, fill, h / 2)
    return p


def font_face():
    """Subset JetBrains Mono to the glyphs in use and inline it as WOFF2.

    The cards render through GitHub's image proxy, where an SVG cannot fetch
    anything external - so the font travels inside the file or not at all.
    Subsetting keeps that payload to a few KB per weight.
    """
    from fontTools import subset
    from fontTools.ttLib import TTFont
    text = "".join(sorted(GLYPHS)) + " "
    out = []
    for weight, path in FONT_SRC.items():
        f = TTFont(path)
        opt = subset.Options(layout_features=["*"], notdef_outline=True, desubroutinize=True)
        sub = subset.Subsetter(options=opt)
        sub.populate(text=text)
        sub.subset(f)
        f.flavor = "woff2"
        buf = io.BytesIO()
        f.save(buf)
        b64 = base64.b64encode(buf.getvalue()).decode()
        out.append("@font-face{font-family:'JetBrains Mono';font-style:normal;"
                   "font-weight:%s;src:url(data:font/woff2;base64,%s) format('woff2')}" % (weight, b64))
    return "<defs><style>%s</style></defs>" % "".join(out)


def svg(w, h, body, face=""):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="%s" height="%s" viewBox="0 0 %s %s" '
            'font-family="%s">%s%s</svg>' % (w, h, w, h, MONO, face, body))


CARDS = []


def write(name, w, h, body):
    CARDS.append((name, w, h, body))
    return name


def star(x, y, fill, s=5):
    pts = []
    import math
    for i in range(10):
        r = s if i % 2 == 0 else s * 0.45
        a = -math.pi / 2 + i * math.pi / 5
        pts.append("%.2f,%.2f" % (x + r * math.cos(a), y + r * math.sin(a)))
    return '<polygon points="%s" fill="%s"/>' % (" ".join(pts), fill)


def fork(x, y, fill):
    return ('<g stroke="%s" stroke-width="1.3" fill="none">'
            '<circle cx="%s" cy="%s" r="1.8"/><circle cx="%s" cy="%s" r="1.8"/>'
            '<circle cx="%s" cy="%s" r="1.8"/>'
            '<path d="M%s %sv2.5a2.5 2.5 0 0 0 2.5 2.5h0a2.5 2.5 0 0 1 2.5 2.5"/>'
            '<path d="M%s %sv2.5a2.5 2.5 0 0 1-2.5 2.5"/></g>'
            % (fill, x, y - 4, x + 7, y - 4, x + 3.5, y + 5, x, y - 2, x + 7, y - 2))


# ------------------------------------------------------------ 1. neofetch --
def card_neofetch():
    W, H = 560, 404
    p = [window(0.5, 0.5, W - 1, H - 1, "vivek@github: ~$ neofetch")]
    y = 62
    p.append(t(22, y, "vivek", C["bright"], 14, "bold"))
    p.append(t(22 + 5 * 8.7, y, "@github", C["teal"], 14, "bold"))
    p.append('<line x1="22" y1="%s" x2="%s" y2="%s" stroke="%s"/>' % (y + 10, W - 22, y + 10, C["line"]))
    y += 30
    for k, v in DATA["id"]:
        p.append(t(22, y, k, C["dim"], 12.5))
        p.append(t(132, y, v, C["fg"], 12.5))
        y += 20
    for title, rows in (("Stack", DATA["stack"]),):
        y += 12
        p.append(t(22, y, "— " + title, C["teal"], 12.5, "bold"))
        y += 20
        for k, v in rows:
            p.append(t(22, y, k, C["dim"], 12.5))
            p.append(t(132, y, v, C["fg"], 12.5))
            y += 20
    y += 12
    p.append(t(22, y, "— Highlights", C["teal"], 12.5, "bold"))
    y += 20
    for h in DATA["highlights"]:
        p.append('<circle cx="26" cy="%s" r="2" fill="%s"/>' % (y - 4, C["faint"]))
        p.append(t(36, y, h, C["fg"], 12.5))
        y += 20
    return write("neofetch.svg", W, H, "".join(p))


# -------------------------------------------------------- 2. now building --
def card_building():
    W, H = 900, 196
    p = [window(0.5, 0.5, W - 1, H - 1, "vivek@github: ~/projects $ ls --status in-progress")]
    colw = (W - 48) / 3.0
    for i, pr in enumerate(DATA["building"]):
        x = 24 + i * colw
        hue = C[pr["hue"]]
        if i:
            p.append('<line x1="%s" y1="56" x2="%s" y2="%s" stroke="%s"/>' % (x - 12, x - 12, H - 22, C["line"]))
        p.append(t(x, 72, pr["name"], hue, 14, "bold"))
        p.append(t(x, 90, pr["sub"], C["dim"], 11.5))
        for j, line in enumerate(pr["body"]):
            p.append(t(x, 114 + j * 16, line, C["fg"], 12))
        cx = x
        for tag in pr["tags"]:
            g, w = chip(cx, 150, tag, C["dim"], C["head"])
            p.append(g)
            cx += w + 6
        p.append(bar(x, 178, colw - 90, 3, pr["pct"], hue))
        p.append(t(x + colw - 24, 181, "IN PROGRESS", C["faint"], 9.5, anchor="end"))
    return write("now-building.svg", W, H, "".join(p))


# ----------------------------------------------------- 3. featured repos --
def card_repos():
    W = 900
    cw, ch, gap = (W - 20) / 2.0, 132, 20
    rows = (len(DATA["repos"]) + 1) // 2
    H = rows * ch + (rows - 1) * gap
    p = []
    idx = LIVE.get("repo_index") or {}
    for i, r in enumerate(DATA["repos"]):
        live = idx.get(r["name"])
        if live:                      # keep the hand-written blurb, refresh the numbers
            r = dict(r, stars=live["stars"], forks=live["forks"],
                     lang=live["lang"] or r["lang"],
                     when="updated " + live["pushed"])
        x = (i % 2) * (cw + 20) + 0.5
        y = (i // 2) * (ch + gap) + 0.5
        p.append(window(x, y, cw - 1, ch - 1, "vivek@github: ~$ cd " + r["name"], 8, 28))
        p.append(t(x + 18, y + 52, "~/", C["dim"], 13.5))
        p.append(t(x + 18 + 2 * 8.4, y + 52, r["name"], C["bright"], 13.5, "bold"))
        tx = x + cw - 18
        for tag in reversed(r["tags"]):
            p.append(t(tx, y + 52, tag, C["violet"], 10.5, anchor="end"))
            tx -= len(tag) * 6.5 + 8
        for j, line in enumerate(r["body"]):
            p.append(t(x + 18, y + 76 + j * 16, line, C["fg"], 11.5))
        fy = y + ch - 18
        p.append('<circle cx="%s" cy="%s" r="4" fill="%s"/>' % (x + 22, fy - 4, r["dot"]))
        p.append(t(x + 32, fy, r["lang"], C["dim"], 11))
        sx = x + 32 + len(r["lang"]) * 6.6 + 14
        p.append(star(sx, fy - 4, C["faint"]))
        p.append(t(sx + 9, fy, str(r["stars"]), C["dim"], 11))
        fx = sx + 9 + len(str(r["stars"])) * 6.6 + 12
        p.append(fork(fx, fy - 4, C["faint"]))
        p.append(t(fx + 12, fy, str(r["forks"]), C["dim"], 11))
        p.append(t(x + cw - 18, fy, r["when"], C["faint"], 10.5, anchor="end"))
    return write("featured.svg", W, H, "".join(p))


# ------------------------------------------------------------- 4. gh stats --
def card_stats():
    W, H = 440, 372
    p = [window(0.5, 0.5, W - 1, H - 1, "vivek@github: ~$ gh stats")]
    p.append(t(22, 58, "vivek", C["bright"], 13.5, "bold"))
    p.append(t(22 + 5 * 8.4, 58, "@github", C["teal"], 13.5, "bold"))
    y = 88
    for k, v, note in stat_rows():
        p.append(t(22, y, k, C["dim"], 12))
        p.append(t(168, y, v, C["bright"], 12, "bold"))
        if note:
            p.append(t(168 + len(v) * 7.6 + 10, y, note, C["faint"], 10.5))
        y += 22
    import math
    con = LIVE.get("contributions") or {}
    if con.get("tracked_days"):
        pct = int(round(100.0 * con["active_days"] / con["tracked_days"]))
        sub = "%d of %d" % (con["active_days"], con["tracked_days"])
    else:
        pct = sub = None
    if pct is None:                 # no calendar yet - draw no ring at all
        p.append(t(22, y + 24, "contribution calendar: awaiting first workflow run",
                   C["faint"], 10))
        if LIVE.get("generated_at"):
            p.append(t(22, H - 16, "updated %s \u00b7 GitHub API" % LIVE["generated_at"],
                       C["faint"], 9.5))
        return write("stats.svg", W, H, "".join(p))
    cx, cy, r = W - 74, y + 44, 34
    circ = 2 * math.pi * r
    p.append('<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="7"/>'
             % (cx, cy, r, C["track"]))
    p.append('<circle cx="%s" cy="%s" r="%s" fill="none" stroke="%s" stroke-width="7" '
             'stroke-linecap="round" stroke-dasharray="%.2f %.2f" transform="rotate(-90 %s %s)"/>'
             % (cx, cy, r, C["teal"], circ * pct / 100.0, circ, cx, cy))
    p.append(t(cx, cy + 7, "%d%%" % pct, C["bright"], 19, "bold", "middle"))
    p.append(t(cx, cy + r + 20, "active days", C["dim"], 10.5, anchor="middle"))
    p.append(t(cx, cy + r + 36, sub, C["faint"], 10, anchor="middle"))
    if LIVE.get("generated_at"):
        p.append(t(22, H - 16, "updated %s \u00b7 GitHub API" % LIVE["generated_at"], C["faint"], 9.5))
    return write("stats.svg", W, H, "".join(p))


# ------------------------------------------------------------ 5. languages --
def card_langs():
    W, H = 440, 372
    waka = LIVE.get("waka") or {}
    langs = [(n, v) for n, v in (waka.get("langs") or DATA["langs"])][:8]
    hue = {n: SERIES[i] for i, (n, _) in enumerate(langs)}
    p = [window(0.5, 0.5, W - 1, H - 1, "vivek@github: ~$ wakatime --languages")]
    p.append(t(22, 58, "\u2014 time coded", C["teal"], 12.5, "bold"))
    since = (" \u00b7 since " + waka["from"][-4:]) if waka.get("from") else ""
    p.append(t(22 + 13 * 7.5, 58, "(WakaTime%s)" % since, C["faint"], 10))
    x, y, bw, bh = 22, 70, W - 44, 10
    total = sum(v for _, v in langs) or 1
    p.append(rect(x, y, bw, bh, C["track"], bh / 2))
    cx, segs = x, []
    for name, v in langs:
        w = bw * v / total
        segs.append((cx, max(2.0, w - 2), hue[name]))
        cx += w
    for i, (sx, sw, col) in enumerate(segs):
        p.append(rect(sx, y, sw, bh, col, bh / 2 if i in (0, len(segs) - 1) else 0))
    y = 104
    half = (len(langs) + 1) // 2
    for i, (name, v) in enumerate(langs):
        col_x = 22 if i < half else 240
        row_y = y + (i % half) * 20
        p.append('<circle cx="%s" cy="%s" r="4" fill="%s"/>' % (col_x + 4, row_y - 4, hue[name]))
        p.append(t(col_x + 15, row_y, name[:12], C["fg"], 11.5))
        p.append(t(col_x + 168, row_y, "%.1f%%" % v, C["dim"], 11.5, anchor="end"))

    y = 196
    projects = LIVE.get("projects") or []
    p.append(t(22, y, "\u2014 projects", C["teal"], 12.5, "bold"))
    p.append(t(22 + 10 * 7.5, y, "(commits, past year \u00b7 bots excluded)", C["faint"], 9.5))
    y += 22
    if projects:
        top = max(pr["commits"] for pr in projects)
        for pr in projects[:4]:
            p.append(t(22, y, pr["name"][:26], C["fg"], 11))
            p.append(bar(232, y - 8, 150, 6, pr["commits"] / float(top), C["teal"]))
            p.append(t(W - 22, y, str(pr["commits"]), C["dim"], 11, anchor="end"))
            y += 20
    else:
        p.append(t(22, y, "populated by the daily workflow", C["faint"], 10.5))

    y = 300
    p.append(t(22, y, "\u2014 repos by language", C["teal"], 12.5, "bold"))
    y += 22
    rl = [(n, c) for n, c in (LIVE.get("repo_langs") or DATA["repo_langs"])][:6]
    rhue = {n: hue.get(n, SERIES[i]) for i, (n, _) in enumerate(rl)}
    cx, cy2 = 22, y
    for name, n in rl:
        short = name.replace("Jupyter Notebook", "Jupyter")
        label = "%s %d" % (short, n)
        w = len(label) * 11 * 0.62 + 26
        if cx + w > W - 22:
            cx, cy2 = 22, cy2 + 26
        p.append(rect(cx, cy2 - 13, w, 20, C["head"], 10))
        p.append('<circle cx="%s" cy="%s" r="3.5" fill="%s"/>' % (cx + 11, cy2 - 3, rhue[name]))
        p.append(t(cx + 20, cy2 + 1, short, C["fg"], 11))
        p.append(t(cx + 20 + len(short) * 6.6 + 5, cy2 + 1, str(n), C["faint"], 11))
        cx += w + 7
    return write("languages.svg", W, H, "".join(p))


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    for fn in (card_neofetch, card_building, card_repos, card_stats, card_langs):
        fn()
    face = font_face()
    print("%d glyphs subset, font payload %.1f KB/card" % (len(GLYPHS), len(face) / 1024.0))
    for name, w, h, body in CARDS:
        with open(os.path.join(OUT, name), "w") as f:
            f.write(svg(w, h, body, face))
        print("%-20s %6d bytes" % (name, os.path.getsize(os.path.join(OUT, name))))
