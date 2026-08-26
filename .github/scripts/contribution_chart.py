#!/usr/bin/env python3
"""Render a daily contribution bar chart to SVG.

Date on x, count on y. Reads GitHub's contribution calendar, which is the
only daily-resolution source that includes private activity.
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

QUERY = """
query($login:String!, $from:DateTime!, $to:DateTime!) {
  user(login:$login) {
    contributionsCollection(from:$from, to:$to) {
      contributionCalendar {
        totalContributions
        weeks { contributionDays { date contributionCount } }
      }
    }
  }
}
"""

W, H = 1000, 260
ML, MR, MT, MB = 44, 16, 34, 30
SURFACE, BAR, GRID = "#0d1117", "#3b82f6", "#1e293b"
INK, MUTED = "#94a3b8", "#64748b"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def fetch(login, token):
    to = datetime.now(timezone.utc)
    frm = to - timedelta(days=364)
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {
            "login": login,
            "from": frm.isoformat(),
            "to": to.isoformat(),
        }}).encode(),
        headers={"Authorization": "bearer " + token,
                 "Content-Type": "application/json",
                 "User-Agent": login},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        payload = json.load(r)
    if "errors" in payload:
        sys.exit("GraphQL error: " + json.dumps(payload["errors"]))
    cal = payload["data"]["user"]["contributionsCollection"]["contributionCalendar"]
    days = [d for wk in cal["weeks"] for d in wk["contributionDays"]]
    days.sort(key=lambda d: d["date"])
    return days, cal["totalContributions"]


def nice_ceiling(v):
    """Round the axis top up to something a person would choose."""
    if v <= 5:
        return 5
    for step in (10, 20, 25, 50, 100, 200, 250, 500, 1000):
        if v <= step:
            return step
    return int(-(-v // 1000) * 1000)


def esc(s):
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render(days, total):
    plot_w, plot_h = W - ML - MR, H - MT - MB
    n = len(days)
    peak = max((d["contributionCount"] for d in days), default=0)
    top = nice_ceiling(peak)
    slot = plot_w / n
    bw = max(1.4, slot - 0.6)
    base = MT + plot_h

    out = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" role="img" '
        f'aria-label="Contributions per day over the last year. '
        f'{total} total, peak {peak} in one day.">',
        f'<rect width="{W}" height="{H}" fill="{SURFACE}"/>',
        f'<text x="{ML}" y="20" fill="{INK}" font-family="system-ui,-apple-system,'
        f'Segoe UI,sans-serif" font-size="13" font-weight="600">Contributions per day</text>',
        f'<text x="{W - MR}" y="20" fill="{MUTED}" font-family="system-ui,-apple-system,'
        f'Segoe UI,sans-serif" font-size="12" text-anchor="end">'
        f'{total:,} in the last year &#183; peak {peak}</text>',
    ]

    # Recessive gridlines, labelled at the ends only.
    for frac in (0, 0.5, 1):
        y = base - frac * plot_h
        out.append(f'<line x1="{ML}" y1="{y:.1f}" x2="{W - MR}" y2="{y:.1f}" '
                   f'stroke="{GRID}" stroke-width="1"/>')
        out.append(f'<text x="{ML - 8}" y="{y + 4:.1f}" fill="{MUTED}" '
                   f'font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
                   f'font-size="11" text-anchor="end">{int(top * frac)}</text>')

    # Bars.
    for i, d in enumerate(days):
        c = d["contributionCount"]
        if not c:
            continue
        h = max(1.5, c / top * plot_h)
        x = ML + i * slot
        out.append(f'<rect x="{x:.2f}" y="{base - h:.2f}" width="{bw:.2f}" '
                   f'height="{h:.2f}" fill="{BAR}" rx="0.7"><title>'
                   f'{esc(d["date"])}: {c}</title></rect>')

    # One label per month, at its first day. The window opens mid-month, so
    # keep a minimum gap or that first stub collides with the next label.
    seen, last_x = set(), None
    for i, d in enumerate(days):
        mo = d["date"][:7]
        if mo in seen:
            continue
        seen.add(mo)
        x = ML + i * slot
        if last_x is not None and x - last_x < 30:
            continue
        last_x = x
        out.append(f'<text x="{x:.1f}" y="{base + 18:.0f}" fill="{MUTED}" '
                   f'font-family="system-ui,-apple-system,Segoe UI,sans-serif" '
                   f'font-size="10">{MONTHS[int(d["date"][5:7]) - 1]}</text>')

    out.append("</svg>")
    return "\n".join(out)


def main():
    login, dest = sys.argv[1], sys.argv[2]
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        sys.exit("GITHUB_TOKEN is required")
    days, total = fetch(login, token)
    if not days:
        sys.exit("no contribution days returned")
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
    with open(dest, "w", encoding="utf-8") as fh:
        fh.write(render(days, total))
    peak = max(d["contributionCount"] for d in days)
    active = sum(1 for d in days if d["contributionCount"])
    print(f"{dest}: {len(days)} days, {active} active, {total} contributions, peak {peak}")


if __name__ == "__main__":
    main()
