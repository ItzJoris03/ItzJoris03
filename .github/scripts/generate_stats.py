#!/usr/bin/env python3
"""Generate GitHub profile stats SVGs from the GitHub API.

Writes output/stats/{stats,langs}-{dark,light}.svg. Designed to run in a
scheduled GitHub Action (reads GITHUB_TOKEN) or locally (reads GH_TOKEN).

Standard library only. Language icons are inlined from devicon at
generation time; if the CDN is unreachable the card falls back to a
colored dot so generation never hard-fails on a missing icon.
"""

import json
import os
import re
import sys
from datetime import datetime
import urllib.error
import urllib.request

OWNER = os.environ.get("PROFILE_OWNER", "ItzJoris03")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
GRAPHQL_TOKEN = os.environ.get("GH_PAT") or os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT_DIR = os.environ.get("OUT_DIR", "output/stats")
API_BASE = "https://api.github.com"
GRAPHQL_URL = "https://api.github.com/graphql"
CARD_W = 400
CARD_H = 200

THEMES = {
    "dark": {
        "accent": "#58a6ff",
        "primary": "#f0f6fc",
        "secondary": "#c9d1d9",
        "num": "#e6edf3",
        "border": "rgba(255,255,255,0.16)",
        "bar_bg": "rgba(255,255,255,0.10)",
    },
    "light": {
        "accent": "#0969da",
        "primary": "#1f2328",
        "secondary": "#57606a",
        "num": "#24292f",
        "border": "rgba(0,0,0,0.16)",
        "bar_bg": "rgba(0,0,0,0.09)",
        "icon_fill": "#24292f",
    },
}

# devicon icon slugs per language (colored variants)
DEVICON = {
    "Rust": "rust",
    "Shell": "bash",
    "TypeScript": "typescript",
    "JavaScript": "javascript",
    "HTML": "html5",
    "CSS": "css3",
    "Python": "python",
    "Java": "java",
    "C#": "csharp",
    "Go": "go",
    "C": "c",
    "C++": "cplusplus",
    "Kotlin": "kotlin",
    "Swift": "swift",
    "Vue": "vuejs",
    "Svelte": "svelte",
}
DEVICON_URL = "https://raw.githubusercontent.com/devicons/devicon/master/icons/{slug}/{file}.svg"

LANG_COLORS = {
    "Rust": "#dea584",
    "Shell": "#89e051",
    "TypeScript": "#3178c6",
    "JavaScript": "#f1e05a",
    "HTML": "#e34c26",
    "CSS": "#563d7c",
    "Python": "#3572a5",
    "Java": "#b07219",
    "C#": "#178600",
    "Go": "#00add8",
    "C": "#555555",
    "C++": "#f34b7d",
    "Swift": "#f05138",
    "Kotlin": "#a97bff",
    "Vue": "#41b883",
    "Svelte": "#ff3e00",
}
FALLBACK_COLORS = [
    "#58a6ff", "#f0883e", "#a371f7", "#3fb950", "#e3b341",
    "#db61a2", "#8250df", "#1f883d", "#d29922", "#bc4c00",
]

_icon_cache = {}


def esc(value):
    return str(value).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def api_get(path):
    req = urllib.request.Request(f"{API_BASE}{path}")
    if TOKEN:
        req.add_header("Authorization", f"Bearer {TOKEN}")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("User-Agent", "profile-stats-generator")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.load(resp)


def lang_color(name):
    return LANG_COLORS.get(name) or FALLBACK_COLORS[hash(name) % len(FALLBACK_COLORS)]


def fetch_icon(slug):
    """Return the inner SVG markup for a devicon icon, or None."""
    if slug in _icon_cache:
        return _icon_cache[slug]
    icon = None
    for file in (f"{slug}-plain", f"{slug}-original"):
        try:
            req = urllib.request.Request(DEVICON_URL.format(slug=slug, file=file))
            req.add_header("User-Agent", "profile-stats-generator")
            with urllib.request.urlopen(req, timeout=15) as resp:
                raw = resp.read().decode("utf-8", "replace")
            match = re.search(r"<svg[^>]*>(.*?)</svg>", raw, re.S)
            if match:
                icon = match.group(1).strip()
                break
        except urllib.error.HTTPError as exc:
            if exc.code != 404:
                print(f"warning: devicon fetch failed for {slug}/{file}: {exc}", file=sys.stderr)
        except Exception as exc:
            print(f"warning: devicon fetch failed for {slug}/{file}: {exc}", file=sys.stderr)
    if icon is None:
        return None
    # Plain variants are monochrome: strip fill attributes so the
    # icon can be recolored via a wrapping group's fill.
    icon = re.sub(r'\s(fill|stroke)="[^"]*"', "", icon)
    # Make every id/url(#id) unique so multiple icons can coexist
    icon = re.sub(r'id="([^"]+)"', lambda m: f'id="dev-{slug}-{m.group(1)}"', icon)
    icon = re.sub(r"url\(#([^)]+)\)", lambda m: f"url(#dev-{slug}-{m.group(1)})", icon)
    _icon_cache[slug] = icon
    return icon


def embed_icon(x, y, size, name, color):
    """Embed a devicon icon (scaled to `size`, recolored) or a colored dot fallback."""
    slug = DEVICON.get(name)
    if slug:
        inner = fetch_icon(slug)
        if inner:
            scale = size / 128.0
            return (
                f'<g transform="translate({x}, {y}) scale({scale:.4f})" '
                f'fill="{color}">{inner}</g>'
            )
    # Fallback: colored dot in the language color
    r = size / 2.0
    return (
        f'<circle cx="{x + r}" cy="{y + r}" r="{r - 1}" '
        f'fill="{lang_color(name)}"/>'
    )


def card_frame(title, t, body):
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CARD_W}" height="{CARD_H}" '
        f'viewBox="0 0 {CARD_W} {CARD_H}" role="img" aria-label="{esc(title)}">',
        f'<rect x="1" y="1" width="{CARD_W - 2}" height="{CARD_H - 2}" rx="10" '
        f'fill="none" stroke="{t["border"]}" stroke-width="1.2"/>',
        # accent dot + title
        f'<circle cx="20" cy="25" r="4.5" fill="{t["accent"]}"/>',
        f'<text x="34" y="30" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
        f'font-size="15" font-weight="700" fill="{t["primary"]}">{esc(title)}</text>',
        f'<line x1="20" y1="46" x2="{CARD_W - 20}" y2="46" '
        f'stroke="{t["border"]}" stroke-width="1"/>',
    ]
    parts.extend(body)
    parts.append("</svg>\n")
    return "".join(parts)


def stats_svg(stats, t):
    body = []
    left = [
        ("Public repos", stats["public_repos"]),
        ("Stars", stats["stars"]),
        ("Forks", stats["forks"]),
    ]
    right = [
        ("Followers", stats["followers"]),
        ("Following", stats["following"]),
        ("Joined", stats["joined"]),
    ]
    y = 78
    for label, value in left:
        body.append(
            f'<text x="28" y="{y}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
            f'font-size="13" fill="{t["secondary"]}">{esc(label)}</text>'
        )
        body.append(
            f'<text x="182" y="{y}" text-anchor="end" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'font-size="13" font-weight="600" fill="{t["num"]}">{value}</text>'
        )
        y += 38
    y = 78
    for label, value in right:
        body.append(
            f'<text x="212" y="{y}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
            f'font-size="13" fill="{t["secondary"]}">{esc(label)}</text>'
        )
        body.append(
            f'<text x="372" y="{y}" text-anchor="end" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'font-size="13" font-weight="600" fill="{t["num"]}">{value}</text>'
        )
        y += 38
    return card_frame("GitHub Stats", t, body)


def langs_svg(langs, t):
    body = []
    if not langs:
        body.append(
            f'<text x="28" y="110" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
            f'font-size="13" fill="{t["secondary"]}">No public language data</text>'
        )
        return card_frame("Top Languages", t, body)
    y = 92
    for i, (name, pct) in enumerate(langs):
        icon_color = t.get("icon_fill") or lang_color(name)
        body.append(embed_icon(24, y - 4, 28, name, icon_color))
        body.append(
            f'<text x="66" y="{y + 16}" font-family="Segoe UI, Helvetica, Arial, sans-serif" '
            f'font-size="14" font-weight="600" fill="{t["primary"]}">{esc(name)}</text>'
        )
        bar_w = max(4.0, (pct / 100.0) * 230.0)
        body.append(
            f'<rect x="66" y="{y + 26}" width="230" height="8" rx="4" fill="{t["bar_bg"]}"/>'
        )
        body.append(
            f'<rect x="66" y="{y + 26}" width="{bar_w:.1f}" height="8" rx="4" '
            f'fill="{lang_color(name)}"/>'
        )
        body.append(
            f'<text x="372" y="{y + 16}" text-anchor="end" '
            f'font-family="ui-monospace, SFMono-Regular, Menlo, monospace" '
            f'font-size="14" font-weight="600" fill="{t["num"]}">{pct:.1f}%</text>'
        )
        y += 56
    return card_frame("Top Languages", t, body)


def graphql_query(query, variables=None):
    """Run a GraphQL query against the GitHub API."""
    req = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": query, "variables": variables or {}}).encode("utf-8"),
    )
    if GRAPHQL_TOKEN:
        req.add_header("Authorization", f"Bearer {GRAPHQL_TOKEN}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "profile-stats-generator")
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = json.load(resp)
    if payload.get("errors"):
        raise RuntimeError(payload["errors"])
    return payload["data"]


CONTRIBUTIONS_QUERY = """
query($login: String!) {
  user(login: $login) {
    contributionsCollection {
      contributionCalendar {
        weeks {
          contributionDays {
            date
            contributionCount
          }
        }
      }
    }
  }
}
"""


def compute_streaks(days):
    """Return current/longest streak, their date ranges, and total contributions."""
    days = sorted(days, key=lambda d: d["date"])
    counts = [d["contributionCount"] for d in days]
    total = sum(counts)

    # Current streak walks backwards from the last day; a zero on the very
    # last day is treated as "today, not over yet" and skipped.
    cur = 0
    idx = len(counts) - 1
    if counts and counts[idx] == 0:
        idx -= 1
    cur_end = idx
    while idx >= 0 and counts[idx] > 0:
        cur += 1
        idx -= 1
    cur_start = idx + 1

    # Longest streak: track the best consecutive run.
    longest = 0
    run = 0
    run_start = 0
    best_start = 0
    best_end = 0
    for i, c in enumerate(counts):
        if c > 0:
            if run == 0:
                run_start = i
            run += 1
            if run > longest:
                longest = run
                best_start = run_start
                best_end = i
        else:
            run = 0

    return {
        "current": cur,
        "current_start": days[cur_start]["date"] if cur else "",
        "current_end": days[cur_end]["date"] if cur else "",
        "longest": longest,
        "longest_start": days[best_start]["date"] if longest else "",
        "longest_end": days[best_end]["date"] if longest else "",
        "total": total,
    }


def fmt_date(iso, with_year=False):
    dt = datetime.strptime(iso, "%Y-%m-%d")
    return dt.strftime("%b %d, %Y") if with_year else dt.strftime("%b %d")


def streak_svg(streak, t):
    """Reproduce the github-readme-streak-stats 'transparent' theme look."""
    # The original theme is theme-agnostic (works on light and dark), so both
    # variants render identical content.
    W, H = 495, 195
    blue = "#006AFF"
    blue_dark = "#0579C3"
    grey = "#417E87"
    border = "#E4E2E2"
    font = "'Segoe UI', Ubuntu, sans-serif"

    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" '
        f'width="{W}px" height="{H}px" direction="ltr" role="img" aria-label="GitHub streak">',
        "<style>"
        "@keyframes fadein{0%{opacity:0}100%{opacity:1}}"
        "@keyframes currstreak{0%{font-size:3px;opacity:.2}80%{font-size:34px;opacity:1}100%{font-size:28px;opacity:1}}"
        "</style>",
        f"<defs><mask id='mask_out_ring_behind_fire'>"
        f"<rect width='{W}' height='{H}' fill='white'/>"
        f"<ellipse cx='247.5' cy='32' rx='13' ry='18' fill='black'/>"
        "</mask></defs>",
        f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="10" '
        f'fill="none" stroke="{border}"/>',
        f'<line x1="165" y1="28" x2="165" y2="170" stroke="{border}"/>',
        f'<line x1="330" y1="28" x2="330" y2="170" stroke="{border}"/>',
    ]

    def text(cx, y, size, weight, fill, content, anim="fadein", delay=0.6):
        style = f"opacity:0;animation:{anim} 0.5s linear forwards {delay}s" if anim != "currstreak" else f"animation:{anim} 0.6s linear forwards"
        return (
            f'<text x="{cx}" y="{y}" text-anchor="middle" fill="{fill}" '
            f'font-family="{font}" font-weight="{weight}" font-size="{size}px" '
            f'style="{style}">{content}</text>'
        )

    # Column 1: Total Contributions
    body.append(text(82.5, 80, 28, 700, blue, streak["total"]))
    body.append(text(82.5, 116, 14, 400, blue, "Total Contributions", delay=0.7))
    body.append(text(82.5, 146, 12, 400, grey, f"{streak['since']} - Present", delay=0.8))

    # Column 2: Current Streak — fire, ring, number, label, range
    flame = (
        "M 1.5 0.67 C 1.5 0.67 2.24 3.32 2.24 5.47 C 2.24 7.53 0.89 9.2 -1.17 9.2 "
        "C -3.23 9.2 -4.79 7.53 -4.79 5.47 L -4.76 5.11 C -6.78 7.51 -8 10.62 -8 13.99 "
        "C -8 18.41 -4.42 22 0 22 C 4.42 22 8 18.41 8 13.99 C 8 8.6 5.41 3.79 1.5 0.67 Z "
        "M -0.29 19 C -2.07 19 -3.51 17.6 -3.51 15.86 C -3.51 14.24 -2.46 13.1 -0.7 12.74 "
        "C 1.07 12.38 2.9 11.53 3.92 10.16 C 4.31 11.45 4.51 12.81 4.51 14.2 "
        "C 4.51 16.85 2.36 19 -0.29 19 Z"
    )
    body.append(
        f'<g transform="translate(247.5, 19.5)" style="opacity:0;animation:fadein 0.5s linear forwards 0.6s">'
        f'<path d="{flame}" fill="{blue}"/></g>'
    )
    body.append(
        f'<g mask="url(#mask_out_ring_behind_fire)">'
        f'<circle cx="247.5" cy="71" r="40" fill="none" stroke="{blue}" stroke-width="5" '
        f'style="opacity:0;animation:fadein 0.5s linear forwards 0.4s"/></g>'
    )
    body.append(text(247.5, 80, 28, 700, blue_dark, streak["current"], anim="currstreak"))
    body.append(text(247.5, 140, 14, 700, blue_dark, "Current Streak", delay=0.9))
    body.append(
        text(247.5, 166, 12, 400, grey,
             f"{fmt_date(streak['current_start'])} - {fmt_date(streak['current_end'])}" if streak["current"] else "No streak yet",
             delay=0.9)
    )

    # Column 3: Longest Streak
    body.append(text(412.5, 80, 28, 700, blue, streak["longest"], delay=1.2))
    body.append(text(412.5, 116, 14, 400, blue, "Longest Streak", delay=1.3))
    body.append(
        text(412.5, 146, 12, 400, grey,
             f"{fmt_date(streak['longest_start'], True)} - {fmt_date(streak['longest_end'], True)}" if streak["longest"] else "No contributions yet",
             delay=1.4)
    )

    body.append("</svg>\n")
    return "".join(body)


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    user = api_get(f"/users/{OWNER}")
    repos = api_get(f"/users/{OWNER}/repos?per_page=100&sort=updated")

    stars = sum(r["stargazers_count"] for r in repos)
    forks = sum(r["forks_count"] for r in repos)

    langs = {}
    for r in repos:
        if r.get("fork"):
            continue
        try:
            data = api_get(f"/repos/{OWNER}/{r['name']}/languages")
        except Exception as exc:
            print(f"warning: languages failed for {r['name']}: {exc}", file=sys.stderr)
            continue
        for lang, size in data.items():
            langs[lang] = langs.get(lang, 0) + size

    total = sum(langs.values())
    top = sorted(langs.items(), key=lambda kv: -kv[1])[:5]
    top_pcts = [(name, size / total * 100) for name, size in top] if total else []

    stats = {
        "public_repos": user["public_repos"],
        "stars": stars,
        "forks": forks,
        "followers": user["followers"],
        "following": user["following"],
        "joined": user.get("created_at", "")[:4],
    }

    streak = None
    try:
        data = graphql_query(CONTRIBUTIONS_QUERY, {"login": OWNER})
        days = []
        for week in data["user"]["contributionsCollection"]["contributionCalendar"]["weeks"]:
            days.extend(week["contributionDays"])
        streak = compute_streaks(days)
        streak["since"] = datetime.strptime(user["created_at"][:10], "%Y-%m-%d").strftime("%b %d, %Y")
    except Exception as exc:
        print(f"warning: streak computation failed: {exc}", file=sys.stderr)

    for name, theme in THEMES.items():
        with open(os.path.join(OUT_DIR, f"stats-{name}.svg"), "w") as fh:
            fh.write(stats_svg(stats, theme))
        with open(os.path.join(OUT_DIR, f"langs-{name}.svg"), "w") as fh:
            fh.write(langs_svg(top_pcts, theme))
        if streak is not None:
            with open(os.path.join(OUT_DIR, f"streak-{name}.svg"), "w") as fh:
                fh.write(streak_svg(streak, theme))

    summary = {"stats": stats, "top_languages": [(n, round(p, 1)) for n, p in top_pcts]}
    if streak is not None:
        summary["streak"] = streak
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
