"""
discover.py  —  Turn your taste profile into new-music recommendations.

Reads taste_profile.json, asks Last.fm "who sounds like the artists you already
collect," throws away anyone you already own, ranks the newcomers by how many of
your artists point at them, and writes a clickable HTML page:

    crate.html

Every recommended artist gets one-click search buttons into SoundCloud,
Bandcamp, YouTube and Beatport so you can dig and actually HEAR them. A second
section watches the Bandcamp labels you buy from most.

Setup (one time):
    1. Get a free key at  last.fm/api/account/create
    2. In PowerShell:   $env:LASTFM_API_KEY = "your_key_here"
    3. python discover.py

Uses only Python's standard library — nothing to pip install.
"""

import os
import sys
import json
import html
import time
import webbrowser
import urllib.parse
import urllib.request
from collections import Counter, defaultdict

import os
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "taste_profile.json")
OUT_HTML = os.path.join(HERE, "crate.html")
LASTFM = "https://ws.audioscrobbler.com/2.0/"

# How many of your top artists to use as seeds, and how many recs to show.
SEED_COUNT = 30
MAX_RECS = 60

API_KEY = os.environ.get("LASTFM_API_KEY")


def lastfm(method, **params):
    """Call a Last.fm API method, return parsed JSON (or {} on any error)."""
    params.update(method=method, api_key=API_KEY, format="json")
    url = LASTFM + "?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.load(r)
    except Exception as e:
        print(f"  ! last.fm error for {method} {params.get('artist','')}: {e}")
        return {}


def similar_artists(name, limit=15):
    """Return [(artist_name, match_score), ...] that Last.fm thinks sound like `name`."""
    data = lastfm("artist.getsimilar", artist=name, limit=limit, autocorrect=1)
    out = []
    for a in data.get("similarartists", {}).get("artist", []):
        try:
            out.append((a["name"], float(a.get("match", 0))))
        except (KeyError, ValueError):
            pass
    return out


def search_links(artist):
    """One-click search URLs into each platform for this artist."""
    q = urllib.parse.quote(artist)
    return {
        "SoundCloud": f"https://soundcloud.com/search?q={q}",
        "Bandcamp":   f"https://bandcamp.com/search?q={q}&item_type=b",
        "YouTube":    f"https://www.youtube.com/results?search_query={q}",
        "Beatport":   f"https://www.beatport.com/search?q={q}",
    }


def build_recommendations(profile):
    """Expand your seed artists into ranked, not-yet-owned recommendations."""
    owned = {name.lower() for name, _ in profile["top_artists"]}
    # also treat the *entire* artist list as owned, not just the top seeds
    seeds = [name for name, _ in profile["top_artists"][:SEED_COUNT]]

    score = Counter()                 # candidate -> summed match across seeds
    suggested_by = defaultdict(list)  # candidate -> which of your artists pointed at it
    for i, seed in enumerate(seeds, 1):
        print(f"  [{i}/{len(seeds)}] similar to {seed} ...")
        for cand, match in similar_artists(seed):
            if cand.lower() in owned:
                continue
            score[cand] += match
            suggested_by[cand].append(seed)
        time.sleep(0.15)  # be polite to the API
    ranked = score.most_common(MAX_RECS)
    return ranked, suggested_by


def render_html(profile, ranked, suggested_by):
    e = html.escape
    rows = []
    for artist, sc in ranked:
        links = search_links(artist)
        btns = " ".join(
            f'<a href="{u}" target="_blank">{name}</a>' for name, u in links.items()
        )
        because = ", ".join(suggested_by[artist][:4])
        rows.append(
            f'<tr><td class="a">{e(artist)}</td>'
            f'<td class="b">{btns}</td>'
            f'<td class="why">like {e(because)}</td></tr>'
        )

    rec_block = "".join(rows) if rows else (
        '<tr><td class="meta">No artist recs yet — add your Last.fm key '
        '(instructions at the top of discover.py) and re-run.</td></tr>')

    # Label-watch section: each label + the releases it's showing right now.
    releases_map = profile.get("label_releases", {})
    urls = profile.get("label_bandcamp_urls", {})
    label_blocks = []
    for label, count in profile.get("top_labels", [])[:25]:
        url = urls.get(label)
        if not url:
            continue
        cards = []
        for r in releases_map.get(label, []):
            artist, title = r.get("artist", ""), r.get("title", "")
            cap = title
            if artist and artist.upper() != "VA" and artist.lower() not in title.lower():
                cap = f"{artist} — {title}"
            art = r.get("art", "")
            img = f'<img src="{art}" loading="lazy">' if art else ""
            cards.append(
                f'<a class="rel" href="{e(r.get("url", ""))}" target="_blank" '
                f'title="{e(cap)}">{img}<span>{e(cap)}</span></a>')
        feed = (f'<div class="rels">{"".join(cards)}</div>' if cards else
                '<div class="meta">run bandcamp_fresh.py to pull this label\'s releases</div>')
        label_blocks.append(
            f'<div class="label"><div class="lhead">'
            f'<span class="lname">{e(label)}</span>'
            f'<span class="meta">{count} in your crate</span>'
            f'<a href="{e(url)}" target="_blank">open ▸</a></div>{feed}</div>')

    return f"""<!doctype html><html><head><meta charset="utf-8">
<title>Crate Digger</title><style>
 body{{background:#111;color:#eee;font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:960px;padding:24px}}
 h1{{color:#7df}} h2{{color:#7df;margin-top:36px;border-bottom:1px solid #333;padding-bottom:6px}}
 table{{border-collapse:collapse;width:100%}} td{{padding:7px 8px;border-bottom:1px solid #222;vertical-align:top}}
 td.a{{font-weight:600;white-space:nowrap}} td.why{{color:#888;font-size:13px}}
 a{{color:#7df;text-decoration:none;margin-right:8px;border:1px solid #2a4;border-radius:4px;padding:1px 7px;font-size:13px}}
 a:hover{{background:#2a4;color:#000}} .meta{{color:#888}}
 .label{{margin:14px 0;padding:12px;background:#181818;border:1px solid #222;border-radius:8px}}
 .lhead{{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap;margin-bottom:10px}}
 .lname{{font-weight:700;color:#fff;font-size:16px}}
 .rels{{display:flex;flex-wrap:wrap;gap:12px}}
 .rel{{display:block;width:118px;border:none;padding:0;margin:0;color:#bcd;font-size:12px}}
 .rel img{{width:118px;height:118px;object-fit:cover;border-radius:6px;display:block;background:#222}}
 .rel span{{display:block;margin-top:5px;line-height:1.25}}
 .rel:hover{{background:none;color:#7df}}
</style></head><body>
<h1>🎧 Crate Digger</h1>
<p class="meta">{len(ranked)} new artists, expanded from your top {SEED_COUNT} —
 click a platform to dig. Generated from {profile['totals']['audio_files']} tracks.</p>
<table>{rec_block}</table>
<h2>📀 Label watch — what your labels are showing now</h2>
<p class="meta">The Bandcamp labels and artists your purchases cluster around — {len(label_blocks)} shown,
 each with its current lineup. Click a cover to dig in. Refresh anytime with bandcamp_fresh.py.</p>
{''.join(label_blocks)}
</body></html>"""


def main():
    with open(PROFILE, encoding="utf-8") as fh:
        profile = json.load(fh)
    if API_KEY:
        print(f"Expanding your top {SEED_COUNT} artists via Last.fm ...")
        ranked, suggested_by = build_recommendations(profile)
    else:
        print("No LASTFM_API_KEY set - writing the label-watch page only.")
        print("Get a free key at last.fm/api/account/create, then run:")
        print('  $env:LASTFM_API_KEY = "your_key"   (and re-run for artist recs)')
        ranked, suggested_by = [], {}
    with open(OUT_HTML, "w", encoding="utf-8") as fh:
        fh.write(render_html(profile, ranked, suggested_by))
    print(f"\nWrote {OUT_HTML}  ({len(ranked)} recommendations)")
    webbrowser.open(OUT_HTML)


if __name__ == "__main__":
    main()
