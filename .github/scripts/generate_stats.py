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
import urllib.error
import urllib.request

OWNER = os.environ.get("PROFILE_OWNER", "ItzJoris03")
TOKEN = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
OUT_DIR = os.environ.get("OUT_DIR", "output/stats")
API_BASE = "https://api.github.com"
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

    for name, theme in THEMES.items():
        with open(os.path.join(OUT_DIR, f"stats-{name}.svg"), "w") as fh:
            fh.write(stats_svg(stats, theme))
        with open(os.path.join(OUT_DIR, f"langs-{name}.svg"), "w") as fh:
            fh.write(langs_svg(top_pcts, theme))

    print(json.dumps({"stats": stats, "top_languages": [(n, round(p, 1)) for n, p in top_pcts]}, indent=2))


if __name__ == "__main__":
    main()
