"""
bandcamp_fresh.py  —  Pull each label's current releases off Bandcamp.

For every Bandcamp label in your taste profile, this grabs the label's release
grid (the same one you see on their page) and saves the top few releases back
into taste_profile.json under "label_releases". discover.py then shows them
under each label, so your label-watch list becomes a living feed instead of
just a link.

Note: Bandcamp gives us the label's *front-page order*, which is newest-first
for most labels but can have pinned/featured releases up top (e.g. Duploc pins
its compilations). So treat this as "what the label is showing right now,"
not a strict by-date sort. Re-run any time to refresh.

Stdlib only. Reads nothing but public pages; writes only taste_profile.json.
"""

import re
import json
import html
import sys
import time
import urllib.request

import os
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "taste_profile.json")
RELEASES_PER_LABEL = 8
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

GRID_RE = re.compile(r'data-client-items="(.*?)"', re.S)


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.read().decode("utf-8", "replace")


def latest_releases(label_url, n=RELEASES_PER_LABEL):
    """Return [{artist, title, url, art}, ...] from a label's /music grid."""
    base = label_url.rstrip("/")
    body = fetch(base + "/music")
    m = GRID_RE.search(body)
    if not m:
        return []
    items = json.loads(html.unescape(m.group(1)))   # entity-decode -> JSON
    out = []
    for it in items[:n]:
        page = it.get("page_url", "")
        url = page if page.startswith("http") else base + page
        url = html.unescape(url)
        art = it.get("art_id")
        out.append({
            "artist": it.get("artist", "").strip(),
            "title": it.get("title", "").strip(),
            "url": url,
            "art": f"https://f4.bcbits.com/img/a{art}_16.jpg" if art else "",
            "id": it.get("id"),            # numeric album/track id -> needed for the embed player
            "type": it.get("type", "album"),
        })
    return out


def main():
    with open(PROFILE, encoding="utf-8") as fh:
        profile = json.load(fh)

    label_urls = profile.get("label_bandcamp_urls", {})
    if not label_urls:
        print("No Bandcamp labels in the profile — run profile_library.py first.")
        return

    releases = {}
    for slug, url in label_urls.items():
        try:
            rel = latest_releases(url)
            releases[slug] = rel
            print(f"  {slug:<22} {len(rel)} releases  ({url})")
        except Exception as e:
            print(f"  {slug:<22} ! {e}")
        time.sleep(0.4)  # be polite

    if not releases:
        # every label failed (network down?) — keep the last good list rather than saving nothing
        sys.exit("No label could be reached; keeping the previous releases.")
    # a label that failed this time keeps its previous releases instead of vanishing from the deck
    for slug, rel in profile.get("label_releases", {}).items():
        releases.setdefault(slug, rel)
    profile["label_releases"] = releases
    with open(PROFILE, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, ensure_ascii=False)
    total = sum(len(v) for v in releases.values())
    print(f"\nSaved {total} releases across {len(releases)} labels to taste_profile.json")


if __name__ == "__main__":
    main()
