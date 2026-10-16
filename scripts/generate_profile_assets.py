#!/usr/bin/env python3
"""
Generates the live, self-hosted SVG cards used by the profile README.

  assets/generated/stats.svg       GitHub player stats + streaks
  assets/generated/languages.svg   top languages by code size
  assets/generated/activity.svg    contributions per week (last 12 months)
  assets/generated/leetcode.svg    LeetCode activity heatmap (graph only, no username/rank/numbers)
  assets/generated/repo-<name>.svg mission cards for featured repositories

Runs in GitHub Actions (see .github/workflows/profile-assets.yml). Standard library only.

Usage:
  python scripts/generate_profile_assets.py              # fetch real data
  python scripts/generate_profile_assets.py --placeholder  # write "syncing" placeholders
  python scripts/generate_profile_assets.py --demo         # synthetic data, for local previews only
"""
import html
import json
import os
import random
import sys
import textwrap
import urllib.request
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.environ.get("OUT_DIR", os.path.join(ROOT, "assets", "generated"))
USER = os.environ.get("GH_USERNAME", "sankalpdevtester")
LC_USER = os.environ.get("LEETCODE_USERNAME", "")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

# Featured repositories shown as "mission" cards (order = mission number).
REPOS = [
    "aether-db",
    "architectural-visualizer",
    "aegis-codefusion-2k26",
    "code-vault-pro",
    "devops-pulse",
    "forge-chain",
]

T = "Impact,'Arial Black','Haettenschweiler','Arial Narrow Bold',sans-serif"
M = "'Courier New',ui-monospace,SFMono-Regular,Consolas,monospace"
U = "'Segoe UI',system-ui,-apple-system,Roboto,Arial,sans-serif"
REDUCE = "@media (prefers-reduced-motion: reduce){*{animation:none!important}}"


def esc(s):
    return html.escape(str(s), quote=True)


def fmt(n):
    return f"{int(n):,}"


# ----------------------------------------------------------------------------
# Shared SVG frame
# ----------------------------------------------------------------------------
def frame(w, h, label, body, css=""):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" aria-label="{esc(label)}">
<title>{esc(label)}</title>
<defs>
<linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#0b0e1a"/><stop offset="1" stop-color="#1c1038"/></linearGradient>
<linearGradient id="swp" x1="0" x2="1"><stop offset="0" stop-color="#22d3ee" stop-opacity="0"/><stop offset=".5" stop-color="#22d3ee"/><stop offset="1" stop-color="#22d3ee" stop-opacity="0"/></linearGradient>
<linearGradient id="barg" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#8b5cf6"/><stop offset=".55" stop-color="#ff2e88"/><stop offset="1" stop-color="#ffc83d"/></linearGradient>
<clipPath id="cp"><rect width="{w}" height="{h}" rx="14"/></clipPath>
</defs>
<style>
.lbl{{font-family:{M};font-size:12px;letter-spacing:2px;fill:#9aa3d6}}
.ttl{{font-family:{M};font-weight:700;font-size:12px;letter-spacing:3px;fill:#ff7a1a}}
.val{{font-family:{T};font-size:18px;letter-spacing:1px;fill:#fff}}
.big{{font-family:{T};font-size:30px;letter-spacing:1px;fill:#ffc83d}}
.unit{{font-family:{M};font-size:10px;letter-spacing:2px;fill:#8f98c9}}
.sub{{font-family:{M};font-size:10px;letter-spacing:2px;fill:#5b6498}}
.nm{{font-family:{T};font-size:23px;letter-spacing:1.5px;fill:#fff}}
.ds{{font-family:{U};font-size:13px;fill:#aab3e6}}
.in{{animation:in .6s ease-out both}}@keyframes in{{from{{opacity:0;transform:translateX(-12px)}}to{{opacity:1;transform:none}}}}
.dot{{animation:dd 1.4s steps(1) infinite}}@keyframes dd{{0%{{opacity:1}}50%{{opacity:.15}}}}
.sw{{animation:sw 5s linear infinite}}@keyframes sw{{from{{transform:translateX(-240px)}}to{{transform:translateX(1000px)}}}}
.bar{{transform-box:fill-box;transform-origin:left center;animation:gx 1s ease-out both}}@keyframes gx{{from{{transform:scaleX(0)}}to{{transform:scaleX(1)}}}}
.vb{{transform-box:fill-box;transform-origin:center bottom;animation:gy 1s ease-out both}}@keyframes gy{{from{{transform:scaleY(0)}}to{{transform:scaleY(1)}}}}
.col{{animation:cl .7s ease-out both}}@keyframes cl{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:none}}}}
.fire{{transform-box:fill-box;transform-origin:center bottom;animation:fr .5s ease-in-out infinite alternate}}@keyframes fr{{from{{transform:scale(.9,.8)}}to{{transform:scale(1.05,1.15)}}}}
.ld{{animation:ld 2.2s ease-in-out infinite}}@keyframes ld{{0%{{transform:translateX(-120px)}}100%{{transform:translateX(420px)}}}}
{css}
{REDUCE}
</style>
<g clip-path="url(#cp)">
<rect width="{w}" height="{h}" fill="url(#bg)"/>
{body}
<rect class="sw" x="0" y="{h - 3}" width="240" height="3" fill="url(#swp)"/>
</g>
<rect x=".5" y=".5" width="{w - 1}" height="{h - 1}" rx="14" fill="none" stroke="#2a2f55"/>
</svg>'''


def title_strip(text, w, right=""):
    return (f'<circle class="dot" cx="26" cy="27" r="4" fill="#ff7a1a"/>'
            f'<text class="ttl" x="40" y="31">{esc(text)}</text>'
            f'<text class="sub" x="{w - 22}" y="31" text-anchor="end">{esc(right)}</text>'
            f'<path d="M22 44H{w - 22}" stroke="#2a2f55"/>')


def loading(label, w, h):
    body = (title_strip(label, w, "SYNCING") +
            f'<text class="lbl" x="{w // 2}" y="{h // 2 + 4}" text-anchor="middle">LOADING PLAYER DATA...</text>'
            f'<rect x="{w // 2 - 120}" y="{h // 2 + 20}" width="240" height="4" rx="2" fill="#1a1f3d"/>'
            f'<g clip-path="url(#cp)"><rect class="ld" x="{w // 2 - 120}" y="{h // 2 + 20}" width="80" height="4" rx="2" fill="#22d3ee"/></g>')
    return frame(w, h, label, body)


# ----------------------------------------------------------------------------
# Cards
# ----------------------------------------------------------------------------
def render_stats(d):
    w, h = 440, 240
    rows = [("STARS EARNED", d["stars"]), ("COMMITS · 12 MO", d["commits"]), ("PULL REQUESTS", d["prs"]),
            ("ISSUES OPENED", d["issues"]), ("REPOSITORIES", d["repos"]), ("FOLLOWERS", d["followers"])]
    body = title_strip("PLAYER STATS", w, "GITHUB")
    for i, (k, v) in enumerate(rows):
        y = 72 + i * 28
        body += (f'<g class="in" style="animation-delay:{i * .07:.2f}s">'
                 f'<text class="lbl" x="24" y="{y}">{k}</text><text class="val" x="238" y="{y + 1}" text-anchor="end">{fmt(v)}</text>'
                 f'<path d="M24 {y + 9}H238" stroke="#1f2547"/></g>')
    boxes = [("CURRENT STREAK", d["streak"], "DAYS", True), ("LONGEST STREAK", d["longest"], "DAYS", False),
             ("CONTRIBUTIONS", d["total"], "12 MO", False)]
    for i, (k, v, unit, flame) in enumerate(boxes):
        y = 56 + i * 61
        fl = (f'<path class="fire" d="M391 {y + 44}c-7-5-8-12-3-19 1 4 4 5 5 3 1-5-1-8-3-10 7 2 12 9 9 17-1 4-4 7-8 9z" fill="#ff7a1a"/>'
              if flame else "")
        body += (f'<g class="in" style="animation-delay:{.3 + i * .12:.2f}s">'
                 f'<rect x="260" y="{y}" width="158" height="54" rx="9" fill="#ffffff" fill-opacity=".04" stroke="#2f3566"/>'
                 f'<text class="unit" x="272" y="{y + 18}">{k}</text>'
                 f'<text class="big" x="272" y="{y + 45}">{fmt(v)}</text>'
                 f'<text class="unit" x="{272 + 17 * len(fmt(v)) + 6}" y="{y + 45}">{unit}</text>{fl}</g>')
    return frame(w, h, "GitHub player stats", body)


def render_langs(langs):
    w, h = 440, 240
    body = title_strip("TOP LANGUAGES", w, "BY CODE SIZE")
    top = max([p for _, _, p in langs] or [1])
    for i, (name, color, pct) in enumerate(langs[:6]):
        y = 72 + i * 28
        bw = max(6, 170 * pct / top)
        body += (f'<g class="in" style="animation-delay:{i * .07:.2f}s">'
                 f'<circle cx="30" cy="{y - 4}" r="5" fill="{color}"/>'
                 f'<text class="lbl" x="44" y="{y}" style="fill:#e8ecff">{esc(name)}</text>'
                 f'<rect x="170" y="{y - 10}" width="170" height="10" rx="5" fill="#1a1f3d"/>'
                 f'<rect class="bar" style="animation-delay:{.2 + i * .1:.1f}s" x="170" y="{y - 10}" width="{bw:.1f}" height="10" rx="5" fill="{color}"/>'
                 f'<text class="val" style="font-size:15px" x="416" y="{y + 1}" text-anchor="end">{pct:.1f}%</text></g>')
    return frame(w, h, "Top languages", body)


def render_activity(weeks, total):
    w, h = 900, 200
    body = title_strip("CONTRIBUTIONS", w, f"{fmt(total)} IN THE LAST 12 MONTHS")
    n = max(len(weeks), 1)
    pitch = (w - 56) / n
    bw = pitch - 4
    top = max([t for _, t in weeks] or [1]) or 1
    chart_h, base = 100, 168
    for i, (_, t) in enumerate(weeks):
        bh = max(3, chart_h * t / top)
        body += (f'<rect class="vb" style="animation-delay:{i * .02:.2f}s" x="{28 + i * pitch:.1f}" y="{base - bh:.1f}" '
                 f'width="{bw:.1f}" height="{bh:.1f}" rx="2.5" fill="url(#barg)"/>')
    last = -9
    for i, (d0, _) in enumerate(weeks):
        if i == 0 or d0.month != weeks[i - 1][0].month:
            if i - last >= 4:
                body += f'<text class="sub" x="{28 + i * pitch:.1f}" y="{base + 18}">{d0.strftime("%b").upper()}</text>'
                last = i
    body += f'<path d="M28 {base + 3}H{w - 28}" stroke="#2a2f55"/>'
    return frame(w, h, "Contribution activity, last 12 months", body)


LEVELS = ["#151a36", "#4c2a85", "#8b3fb8", "#e0338a", "#ff7a1a", "#ffc83d"]


def level(c):
    return 0 if c <= 0 else 1 if c == 1 else 2 if c <= 3 else 3 if c <= 6 else 4 if c <= 10 else 5


def render_leetcode(cal):
    """cal: {date: count} or None for the empty/syncing grid. No username, rank or totals are drawn."""
    w, h = 900, 186
    today = datetime.now(timezone.utc).date()
    start = today - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)  # back to Sunday
    ncols = (today - start).days // 7 + 1
    x0, y0, pitch, size = 28, 34, 16, 13
    body = ""
    last = -9
    for c in range(ncols):
        d0 = start + timedelta(days=c * 7)
        if c == 0 or d0.month != (start + timedelta(days=(c - 1) * 7)).month:
            if c - last >= 3:
                body += f'<text class="sub" x="{x0 + c * pitch}" y="22">{d0.strftime("%b").upper()}</text>'
                last = c
        cells = ""
        for r in range(7):
            day = start + timedelta(days=c * 7 + r)
            if day > today:
                continue
            lv = level((cal or {}).get(day, 0))
            cells += f'<rect x="{x0 + c * pitch}" y="{y0 + r * pitch}" width="{size}" height="{size}" rx="3" fill="{LEVELS[lv]}"/>'
        body += f'<g class="col" style="animation-delay:{c * .012:.3f}s">{cells}</g>'
    ly = y0 + 7 * pitch + 14
    lx = w - 28 - 5 * 18 - 90
    body += f'<text class="sub" x="{lx}" y="{ly + 10}">LESS</text>'
    for i in range(1, 6):
        body += f'<rect x="{lx + 38 + (i - 1) * 18}" y="{ly}" width="13" height="13" rx="3" fill="{LEVELS[i]}"/>'
    body += f'<text class="sub" x="{lx + 38 + 5 * 18 + 4}" y="{ly + 10}">MORE</text>'
    if cal is None:
        body += f'<text class="sub" x="28" y="{ly + 10}">SYNCING...</text>'
    return frame(w, h, "LeetCode activity heatmap", body)


def star_icon(cx, cy, r):
    import math
    pts = []
    for i in range(10):
        a = -math.pi / 2 + i * math.pi / 5
        rr = r if i % 2 == 0 else r * 0.45
        pts.append(f"{cx + rr * math.cos(a):.1f},{cy + rr * math.sin(a):.1f}")
    return f'<polygon points="{" ".join(pts)}" fill="#ffc83d"/>'


def fork_icon(x, y):
    return (f'<g fill="none" stroke="#9aa3d6" stroke-width="1.6"><circle cx="{x + 2}" cy="{y + 2}" r="2"/><circle cx="{x + 10}" cy="{y + 2}" r="2"/>'
            f'<circle cx="{x + 6}" cy="{y + 13}" r="2"/><path d="M{x + 2} {y + 4}V{y + 7}Q{x + 2} {y + 8} {x + 6} {y + 8}Q{x + 10} {y + 8} {x + 10} {y + 4}M{x + 6} {y + 8}V{y + 11}"/></g>')



def render_repo(i, r):
    w, h = 436, 152
    name = r.get("name", "")
    desc = (r.get("description") or "").strip() or "No briefing yet. Open the repository to see the details."
    lines = textwrap.wrap(desc, 52)
    if len(lines) > 3:
        lines = lines[:3]
        lines[-1] = lines[-1].rstrip(" .,;:") + "..."
    lang = r.get("primaryLanguage") or {}
    body = (f'<text class="ttl" x="22" y="28">MISSION {i + 1:02d}</text>'
            f'<text class="sub" x="{w - 22}" y="28" text-anchor="end">OPEN REPO</text>'
            f'<text class="nm" x="22" y="58">{esc(name)}</text>')
    for k, ln in enumerate(lines):
        body += f'<text class="ds" x="22" y="{80 + k * 17}">{esc(ln)}</text>'
    meta = ""
    x = 22
    my = h - 22
    if lang.get("name"):
        meta += f'<circle cx="{x + 5}" cy="{my - 4}" r="5" fill="{lang.get("color") or "#cccccc"}"/><text class="lbl" x="{x + 16}" y="{my}" style="fill:#e8ecff">{esc(lang["name"])}</text>'
        x += 34 + 8 * len(lang["name"])
    meta += star_icon(x + 6, my - 4, 7) + f'<text class="lbl" x="{x + 18}" y="{my}">{r.get("stargazerCount", 0)}</text>'
    x += 18 + 10 * len(str(r.get("stargazerCount", 0))) + 22
    meta += fork_icon(x, my - 11) + f'<text class="lbl" x="{x + 16}" y="{my}">{r.get("forkCount", 0)}</text>'
    return frame(w, h, f"Mission {i + 1}: {name}", body + meta)


# ----------------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------------
def http_json(url, payload, headers):
    req = urllib.request.Request(url, data=json.dumps(payload).encode(), headers=headers)
    with urllib.request.urlopen(req, timeout=40) as resp:
        return json.loads(resp.read().decode())


def gh_graphql(query, variables):
    out = http_json("https://api.github.com/graphql", {"query": query, "variables": variables},
                    {"Authorization": f"bearer {TOKEN}", "Content-Type": "application/json", "User-Agent": "profile-assets"})
    if out.get("errors") and not out.get("data"):
        raise RuntimeError(out["errors"])
    return out["data"]


def fetch_github():
    aliases = "".join(
        f'r{i}: repository(owner:$login, name:"{n}"){{name description stargazerCount forkCount primaryLanguage{{name color}}}}\n'
        for i, n in enumerate(REPOS))
    q = """
query($login:String!){
  user(login:$login){
    followers{totalCount}
    allRepos: repositories(ownerAffiliations:OWNER){totalCount}
    repositories(ownerAffiliations:OWNER,isFork:false,first:100,orderBy:{field:STARGAZERS,direction:DESC}){
      nodes{stargazerCount languages(first:8,orderBy:{field:SIZE,direction:DESC}){edges{size node{name color}}}}
    }
    contributionsCollection{
      totalCommitContributions totalIssueContributions totalPullRequestContributions
      contributionCalendar{totalContributions weeks{contributionDays{date contributionCount}}}
    }
  }
  """ + aliases + "}"
    data = gh_graphql(q, {"login": USER})
    u = data["user"]
    cc = u["contributionsCollection"]
    days, weeks = [], []
    for wk in cc["contributionCalendar"]["weeks"]:
        wd = wk["contributionDays"]
        if not wd:
            continue
        for dd in wd:
            days.append((datetime.strptime(dd["date"], "%Y-%m-%d").date(), dd["contributionCount"]))
        weeks.append((datetime.strptime(wd[0]["date"], "%Y-%m-%d").date(), sum(x["contributionCount"] for x in wd)))
    streak = longest = run = 0
    for _, c in days:
        run = run + 1 if c > 0 else 0
        longest = max(longest, run)
    for _, c in reversed(days):  # current streak, today may still be empty
        if c > 0:
            streak += 1
        elif streak or _ != days[-1][0]:
            break
    sizes, colors = {}, {}
    for n in u["repositories"]["nodes"]:
        for e in n["languages"]["edges"]:
            sizes[e["node"]["name"]] = sizes.get(e["node"]["name"], 0) + e["size"]
            colors[e["node"]["name"]] = e["node"]["color"] or "#cccccc"
    tot = sum(sizes.values()) or 1
    langs = [(k, colors[k], 100.0 * v / tot) for k, v in sorted(sizes.items(), key=lambda kv: -kv[1])]
    stats = dict(stars=sum(n["stargazerCount"] for n in u["repositories"]["nodes"]), commits=cc["totalCommitContributions"],
                 prs=cc["totalPullRequestContributions"], issues=cc["totalIssueContributions"], repos=u["allRepos"]["totalCount"],
                 followers=u["followers"]["totalCount"], streak=streak, longest=longest,
                 total=cc["contributionCalendar"]["totalContributions"])
    repos = [data.get(f"r{i}") or {"name": n} for i, n in enumerate(REPOS)]
    return stats, langs, weeks, repos


def fetch_leetcode():
    q = "query userProfileCalendar($username:String!){matchedUser(username:$username){userCalendar{submissionCalendar}}}"
    out = http_json("https://leetcode.com/graphql", {"query": q, "variables": {"username": LC_USER}},
                    {"Content-Type": "application/json", "Referer": "https://leetcode.com",
                     "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"})
    raw = json.loads(out["data"]["matchedUser"]["userCalendar"]["submissionCalendar"])
    return {datetime.fromtimestamp(int(ts), timezone.utc).date(): int(c) for ts, c in raw.items()}


def demo():
    rnd = random.Random(3)
    today = datetime.now(timezone.utc).date()
    stats = dict(stars=17, commits=412, prs=38, issues=9, repos=42, followers=1, streak=6, longest=21, total=1034)
    langs = [("Python", "#3572A5", 38.2), ("TypeScript", "#3178c6", 27.5), ("Go", "#00ADD8", 14.1),
             ("JavaScript", "#f1e05a", 9.8), ("Rust", "#dea584", 6.0), ("Java", "#b07219", 4.4)]
    start = today - timedelta(days=364)
    start -= timedelta(days=(start.weekday() + 1) % 7)
    weeks = [(start + timedelta(days=7 * i), rnd.randint(0, 40)) for i in range(53)]
    cal = {today - timedelta(days=i): rnd.choice([0, 0, 0, 1, 2, 3, 5, 8, 12]) for i in range(365)}
    repos = [{"name": n, "description": "A distributed key-value database built from scratch with Raft consensus, write-ahead logging, and horizontal sharding.",
              "stargazerCount": 4, "forkCount": 0, "primaryLanguage": {"name": "Go", "color": "#00ADD8"}} for n in REPOS]
    return stats, langs, weeks, cal, repos


def write(name, content):
    os.makedirs(OUT, exist_ok=True)
    path = os.path.join(OUT, name)
    if os.path.exists(path) and open(path, encoding="utf-8").read() == content:
        return
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def write_all(stats, langs, weeks, cal, repos):
    if stats is not None:
        write("stats.svg", render_stats(stats))
        write("languages.svg", render_langs(langs))
        write("activity.svg", render_activity(weeks, stats["total"]))
        for i, r in enumerate(repos):
            write(f"repo-{REPOS[i]}.svg", render_repo(i, r))
    if cal is not None:
        write("leetcode.svg", render_leetcode(cal))


def main():
    args = sys.argv[1:]
    if "--placeholder" in args:
        write("stats.svg", loading("PLAYER STATS", 440, 240))
        write("languages.svg", loading("TOP LANGUAGES", 440, 240))
        write("activity.svg", loading("CONTRIBUTIONS", 900, 200))
        write("leetcode.svg", render_leetcode(None))
        for i, n in enumerate(REPOS):
            write(f"repo-{n}.svg", render_repo(i, {"name": n, "description": "Syncing mission briefing..."}))
        return 0
    if "--demo" in args:
        s, l, w, c, r = demo()
        write_all(s, l, w, c, r)
        return 0
    stats = langs = weeks = repos = cal = None
    try:
        stats, langs, weeks, repos = fetch_github()
    except Exception as e:  # keep the previous files if GitHub is unreachable
        print(f"::warning::GitHub data was not refreshed: {e}")
    if LC_USER:
        try:
            cal = fetch_leetcode()
        except Exception as e:
            print(f"::warning::LeetCode data was not refreshed: {e}")
    write_all(stats, langs, weeks, cal, repos)
    return 0


if __name__ == "__main__":
    sys.exit(main())
