"""Renders dist/*.svg cards (totals, languages, contribution calendar) in the header style.
Needs a classic token with repo scope in METRICS_TOKEN so private repos are counted.
Only totals and language names are published, never repository names."""
import datetime, json, os, sys, urllib.request

QUERY = """{ viewer {
  contributionsCollection { contributionCalendar { totalContributions
    weeks { contributionDays { contributionCount date } } } }
  repositories(first: 100, ownerAffiliations: OWNER, isFork: false) { totalCount
    nodes { languages(first: 10) { edges { size node { name color } } } } } } }"""

MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()
SHADES = ["#1b1733", "#3b2a7a", "#5b3fc4", "#8b5cf6", "#c4b5fd"]


def fetch(token):
    req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": QUERY}).encode(),
                                 {"Authorization": f"bearer {token}", "User-Agent": "stats"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data:
        sys.exit(data["errors"])
    return data["data"]["viewer"]


def streaks(days, today):
    """days: [(date, count)] ascending. A day with no commits yet does not break the current streak."""
    best = run = 0
    for _, n in days:
        run = run + 1 if n else 0
        best = max(best, run)
    cur = 0
    for d, n in reversed(days):
        if n:
            cur += 1
        elif d != today:
            break
    return cur, best


def levels(counts):
    """0 for an empty day, 1..4 quartiles among non-empty ones, the way GitHub shades them."""
    nz = sorted(n for n in counts if n)
    if not nz:
        return lambda n: 0
    q = [nz[len(nz) * k // 4] for k in (1, 2, 3)]
    return lambda n: 0 if not n else 1 + sum(n > t for t in q)


def frame(h, body, style, width=1200, glow_cx=300):
    w = width
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b0a18"/><stop offset=".55" stop-color="#15113a"/><stop offset="1" stop-color="#0d1117"/>
    </linearGradient>
    <linearGradient id="title" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#a78bfa"/>
    </linearGradient>
    <radialGradient id="glow"><stop offset="0" stop-color="#7c3aed" stop-opacity=".45"/><stop offset="1" stop-color="#7c3aed" stop-opacity="0"/></radialGradient>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#ffffff" stroke-opacity=".05"/></pattern>
    <clipPath id="frame"><rect width="{w}" height="{h}" rx="18"/></clipPath>
  </defs>
  <style>
    text {{ font-family: 'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace; }}
    .glow {{ animation: drift 12s ease-in-out infinite alternate both; }}
    @keyframes drift {{ from {{ transform: translate(0, 0); }} to {{ transform: translate({w // 2}px, 0); }} }}
{style}
  </style>
  <g clip-path="url(#frame)">
    <rect width="{w}" height="{h}" fill="url(#bg)"/>
    <rect width="{w}" height="{h}" fill="url(#grid)"/>
    <ellipse class="glow" cx="{glow_cx}" cy="{h // 2}" rx="380" ry="{h * 0.6:.0f}" fill="url(#glow)"/>
{body}
    <rect y="{h - 4}" width="{w}" height="4" fill="#7c3aed" opacity=".6"/>
  </g>
</svg>
"""


def language_sizes(v):
    langs = {}
    for r in v["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            size, _ = langs.get(name, (0, None))
            langs[name] = (size + e["size"], e["node"]["color"] or "#8b80c9")
    return langs


def render_stats(v, days, today):
    cal = v["contributionsCollection"]["contributionCalendar"]
    cur, best = streaks(days, today)

    langs = language_sizes(v)
    total = sum(s for s, _ in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]

    nums = [(cal["totalContributions"], "contributions / year"), (cur, "current streak"),
            (best, "longest streak"), (v["repositories"]["totalCount"], "repositories")]
    numbers, bars, legend = [], [], []
    for i, (n, label) in enumerate(nums):
        x, y = 48 + (i % 2) * 250, 110 + (i // 2) * 110
        numbers.append(f'<text class="num" x="{x}" y="{y}">{n}</text><text class="lbl" x="{x}" y="{y + 30}">{label}</text>')

    bx, bw = 620, 532
    x = bx
    for name, (size, color) in top:
        w = bw * size / total
        bars.append(f'<rect x="{x:.1f}" y="92" width="{max(w, 2):.1f}" height="12" fill="{color}"/>')
        x += w
    for i, (name, (size, color)) in enumerate(top):
        lx, ly = bx + (i % 2) * 270, 150 + (i // 2) * 42
        legend.append(f'<circle cx="{lx + 7}" cy="{ly - 6}" r="7" fill="{color}"/>'
                      f'<text class="lang" x="{lx + 24}" y="{ly}">{name}</text>'
                      f'<text class="pct" x="{lx + 250}" y="{ly}" text-anchor="end">{100 * size / total:.1f}%</text>')

    body = f"""    <clipPath id="bar"><rect x="{bx}" y="92" width="{bw}" height="12" rx="6"/></clipPath>
    <rect x="580" y="40" width="1" height="220" fill="#ffffff" opacity=".08"/>
    {"".join(numbers)}
    <text class="h" x="{bx}" y="64">Languages</text>
    <g clip-path="url(#bar)">{"".join(bars)}</g>
    {"".join(legend)}"""
    style = """    .num { font-size: 52px; font-weight: 700; fill: url(#title); }
    .lbl { font-size: 18px; fill: #8b80c9; }
    .h { font-size: 22px; font-weight: 700; fill: #c4b5fd; }
    .lang { font-size: 19px; fill: #c4b5fd; }
    .pct { font-size: 17px; fill: #8b80c9; }"""
    return frame(300, body, style)


def render_stats_mobile(v, days, today):
    """Same card for narrow screens: numbers in two rows, languages underneath."""
    cal = v["contributionsCollection"]["contributionCalendar"]
    cur, best = streaks(days, today)
    langs = language_sizes(v)
    total = sum(s for s, _ in langs.values()) or 1
    top = sorted(langs.items(), key=lambda kv: -kv[1][0])[:6]

    nums = [(cal["totalContributions"], "contributions / year"), (cur, "current streak"),
            (best, "longest streak"), (v["repositories"]["totalCount"], "repositories")]
    parts = []
    for i, (n, label) in enumerate(nums):
        x, y = 32 + (i % 2) * 290, 100 + (i // 2) * 110
        parts.append(f'<text class="num" x="{x}" y="{y}">{n}</text><text class="lbl" x="{x}" y="{y + 28}">{label}</text>')

    bx, bw, by = 32, 536, 312
    parts.append(f'<text class="h" x="{bx}" y="292">Languages</text>')
    x = bx
    bars = []
    for name, (size, color) in top:
        w = bw * size / total
        bars.append(f'<rect x="{x:.1f}" y="{by}" width="{max(w, 2):.1f}" height="14" fill="{color}"/>')
        x += w
    parts.append(f'<clipPath id="bar"><rect x="{bx}" y="{by}" width="{bw}" height="14" rx="7"/></clipPath>'
                 f'<g clip-path="url(#bar)">{"".join(bars)}</g>')
    for i, (name, (size, color)) in enumerate(top):
        lx, ly = bx + (i % 2) * 290, 380 + (i // 2) * 46
        parts.append(f'<circle cx="{lx + 8}" cy="{ly - 7}" r="8" fill="{color}"/>'
                     f'<text class="lang" x="{lx + 28}" y="{ly}">{name}</text>'
                     f'<text class="pct" x="{lx + 260}" y="{ly}" text-anchor="end">{100 * size / total:.1f}%</text>')

    style = """    .num { font-size: 54px; font-weight: 700; fill: url(#title); }
    .lbl { font-size: 20px; fill: #8b80c9; }
    .h { font-size: 24px; font-weight: 700; fill: #c4b5fd; }
    .lang { font-size: 22px; fill: #c4b5fd; }
    .pct { font-size: 20px; fill: #8b80c9; }"""
    return frame(512, "    " + "".join(parts), style, width=600, glow_cx=150)


def render_calendar(v, days):
    weeks = v["contributionsCollection"]["contributionCalendar"]["weeks"]
    lvl = levels(n for _, n in days)
    x0, y0, pitch, cell = 48, 74, 1104 / len(weeks), 16
    cols, months, prev = [], [], None
    for i, w in enumerate(weeks):
        x = x0 + i * pitch
        m = int(w["contributionDays"][0]["date"][5:7])
        if m != prev and i < len(weeks) - 2:
            if not months or x - months[-1][0] > 60:
                months.append((x, MONTHS[m - 1]))
            prev = m
        rects = "".join(
            f'<rect x="{x:.1f}" y="{y0 + datetime.date.fromisoformat(d["date"]).isoweekday() % 7 * pitch:.1f}" '
            f'width="{cell}" height="{cell}" rx="4" fill="{SHADES[lvl(d["contributionCount"])]}"/>'
            for d in w["contributionDays"])
        cols.append(f'<g class="w" style="animation-delay:{i * 0.015:.3f}s">{rects}</g>')

    total = v["contributionsCollection"]["contributionCalendar"]["totalContributions"]
    lx = 1152 - 5 * 24 - 52
    body = "\n".join([
        *(f'    <text class="m" x="{x:.1f}" y="58">{name}</text>' for x, name in months),
        *("    " + c for c in cols),
        f'    <text class="lbl" x="48" y="262">{total} contributions in the last year</text>',
        f'    <text class="lbl" x="{lx - 12}" y="262" text-anchor="end">Less</text>',
        *(f'    <rect x="{lx + k * 24}" y="248" width="16" height="16" rx="4" fill="{c}"/>' for k, c in enumerate(SHADES)),
        f'    <text class="lbl" x="{lx + 5 * 24 + 4}" y="262">More</text>',
    ])
    style = """    .m { font-size: 16px; fill: #8b80c9; }
    .lbl { font-size: 16px; fill: #8b80c9; }
    .w { animation: in .5s ease-out both; }
    @keyframes in { from { opacity: 0; } to { opacity: 1; } }"""
    return frame(290, body, style, glow_cx=250)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        d = [("2026-09-0%d" % i, n) for i, n in enumerate([1, 1, 0, 1, 1, 1, 0], 1)]
        assert streaks(d, "2026-09-07") == (3, 3)          # nothing today yet: streak holds
        assert streaks(d, "2026-09-08") == (0, 3)          # nothing yesterday: streak is over
        assert streaks(d[:6], "2026-09-06") == (3, 3)
        f = levels([0, 1, 2, 3, 4, 5, 6, 7, 8])
        assert [f(n) for n in (0, 1, 4, 6, 8)] == [0, 1, 2, 3, 4]
        assert levels([0, 0])(0) == 0
        print("ok")
        sys.exit()
    v = fetch(os.environ["METRICS_TOKEN"])
    days = [(d["date"], d["contributionCount"])
            for w in v["contributionsCollection"]["contributionCalendar"]["weeks"] for d in w["contributionDays"]]
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date().isoformat()
    os.makedirs("dist", exist_ok=True)
    open("dist/stats.svg", "w", encoding="utf-8").write(render_stats(v, days, today))
    open("dist/stats-mobile.svg", "w", encoding="utf-8").write(render_stats_mobile(v, days, today))
    open("dist/calendar.svg", "w", encoding="utf-8").write(render_calendar(v, days))
