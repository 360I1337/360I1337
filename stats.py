"""Рисует dist/stats.svg в стиле шапки: цифры активности + топ языков.
Токен (classic, repo) из env METRICS_TOKEN — нужен, чтобы учитывались приватные репо.
Наружу уходят только суммы и названия языков, имена репозиториев не выводятся."""
import datetime, json, os, sys, urllib.request

QUERY = """{ viewer {
  contributionsCollection { contributionCalendar { totalContributions
    weeks { contributionDays { contributionCount date } } } }
  repositories(first: 100, ownerAffiliations: OWNER, isFork: false) { totalCount
    nodes { languages(first: 10) { edges { size node { name color } } } } } } }"""


def fetch(token):
    req = urllib.request.Request("https://api.github.com/graphql", json.dumps({"query": QUERY}).encode(),
                                 {"Authorization": f"bearer {token}", "User-Agent": "stats"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    if "errors" in data:
        sys.exit(data["errors"])
    return data["data"]["viewer"]


def streaks(days, today):
    """days: [(date, count)] по возрастанию. Текущий стрик не рвётся, если сегодня ещё не коммитил."""
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


def render(v, today):
    cal = v["contributionsCollection"]["contributionCalendar"]
    days = [(d["date"], d["contributionCount"]) for w in cal["weeks"] for d in w["contributionDays"]]
    cur, best = streaks(days, today)

    langs = {}
    for r in v["repositories"]["nodes"]:
        for e in r["languages"]["edges"]:
            name = e["node"]["name"]
            size, _ = langs.get(name, (0, None))
            langs[name] = (size + e["size"], e["node"]["color"] or "#8b80c9")
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

    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 300" width="1200" height="300">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0" stop-color="#0b0a18"/><stop offset=".55" stop-color="#15113a"/><stop offset="1" stop-color="#0d1117"/>
    </linearGradient>
    <linearGradient id="title" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#ffffff"/><stop offset="1" stop-color="#a78bfa"/>
    </linearGradient>
    <radialGradient id="glow"><stop offset="0" stop-color="#7c3aed" stop-opacity=".45"/><stop offset="1" stop-color="#7c3aed" stop-opacity="0"/></radialGradient>
    <pattern id="grid" width="40" height="40" patternUnits="userSpaceOnUse"><path d="M40 0H0V40" fill="none" stroke="#ffffff" stroke-opacity=".05"/></pattern>
    <clipPath id="frame"><rect width="1200" height="300" rx="18"/></clipPath>
    <clipPath id="bar"><rect x="{bx}" y="92" width="{bw}" height="12" rx="6"/></clipPath>
  </defs>
  <style>
    text {{ font-family: 'JetBrains Mono', 'Fira Code', Consolas, 'Courier New', monospace; }}
    .num {{ font-size: 52px; font-weight: 700; fill: url(#title); }}
    .lbl {{ font-size: 18px; fill: #8b80c9; }}
    .h {{ font-size: 22px; font-weight: 700; fill: #c4b5fd; }}
    .lang {{ font-size: 19px; fill: #c4b5fd; }}
    .pct {{ font-size: 17px; fill: #8b80c9; }}
  </style>
  <g clip-path="url(#frame)">
    <rect width="1200" height="300" fill="url(#bg)"/>
    <rect width="1200" height="300" fill="url(#grid)"/>
    <ellipse cx="300" cy="150" rx="380" ry="170" fill="url(#glow)"/>
    <rect x="580" y="40" width="1" height="220" fill="#ffffff" opacity=".08"/>
    {"".join(numbers)}
    <text class="h" x="{bx}" y="64">Languages</text>
    <g clip-path="url(#bar)">{"".join(bars)}</g>
    {"".join(legend)}
    <rect y="296" width="1200" height="4" fill="#7c3aed" opacity=".6"/>
  </g>
</svg>
"""


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "test":
        d = [("2026-09-0%d" % i, n) for i, n in enumerate([1, 1, 0, 1, 1, 1, 0], 1)]
        assert streaks(d, "2026-09-07") == (3, 3)          # сегодня 0 — стрик не рвётся
        assert streaks(d, "2026-09-08") == (0, 3)          # вчера 0 — стрик кончился
        assert streaks(d[:6], "2026-09-06") == (3, 3)
        print("ok")
        sys.exit()
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=3))).date().isoformat()
    os.makedirs("dist", exist_ok=True)
    open("dist/stats.svg", "w", encoding="utf-8").write(render(fetch(os.environ["METRICS_TOKEN"]), today))
