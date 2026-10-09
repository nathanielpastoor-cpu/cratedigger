"""
recommend.py  —  Find NEW artists beyond your own labels, with playable tracks.

Pipeline (all verified live before this was written):
  1. Take your top *real* artists as seeds (junk comp/label names filtered out).
  2. MusicBrainz: resolve each seed name -> a MusicBrainz ID (MBID).
  3. ListenBrainz: MBID -> up to 100 similar artists. MBID keying means
     "Repulsion" can't be confused with the grindcore band.
  4. Rank by SEED CONSENSUS (how many of your seeds point at an artist), so it
     stays in your lane instead of drifting to whatever has the most listeners.
  5. For each new name, get playable tracks two ways:
       - Bandcamp (preferred): resolve the artist via the search API, pull their
         latest releases -> in-card embed player, and you can BUY them.
       - Audius: exact-artist track match -> native streaming (catches artists
         not on Bandcamp).
  6. Save them into taste_profile.json under "discovered" for the swipe deck.

Stdlib only. Polite rate limits (MusicBrainz wants <=1 req/sec).
"""

import re
import sys
import json
import time
import urllib.parse
import urllib.request
from collections import defaultdict

from bandcamp_fresh import latest_releases   # reuse the label /music grid parser

# Windows console is cp1252; track/artist names (and our ♪ marker) are unicode.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import os
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "taste_profile.json")
UA = "CrateDigger/1.0 (+https://github.com/nathanielpastoor-cpu/cratedigger)"
BROWSER_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
              "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")
BC_SEARCH = "https://bandcamp.com/api/bcsearch_public_api/1/autocomplete_elastic"

MAX_SEEDS = 18
MAX_CANDIDATES = 90      # how many similar names to try to resolve
BC_CAP = 50              # Bandcamp discovery cards (buyable, embedded)
AU_CAP = 45              # Audius discovery cards (streamable -> auto-playable)
MAX_PER_ARTIST = 2       # Bandcamp releases per discovered artist (keep variety)
LB_ALG = ("session_based_days_7500_session_300_contribution_3_"
          "threshold_10_limit_100_filter_True_skip_30")

# Compilation / label names my filename parser logged as "artists" — not real.
JUNK = {"repulsion", "all-lo", "billegal beats", "sub.terranean", "background noise",
        "various artists", "v. a.", "va", "thing", "the mines", "nesstrak"}


def norm(s):
    return re.sub(r"\s+", " ", (s or "").lower().replace("_", " ")).strip()


def fetch(url, data=None, headers=None):
    h = {"User-Agent": UA}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, data=data, headers=h)
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def mb_resolve(name):
    """Artist name -> top MusicBrainz MBID (or None)."""
    q = urllib.parse.quote(f'artist:"{name}"')
    try:
        data = json.loads(fetch(f"https://musicbrainz.org/ws/2/artist/?query={q}&fmt=json&limit=1"))
        arts = data.get("artists", [])
        return arts[0]["id"] if arts else None
    except Exception as e:
        print(f"    ! MB {name}: {e}")
        return None


def lb_similar(mbid):
    """MBID -> [(name, score), ...] similar artists from ListenBrainz."""
    body = json.dumps([{"artist_mbids": [mbid], "algorithm": LB_ALG}]).encode()
    try:
        data = json.loads(fetch("https://labs.api.listenbrainz.org/similar-artists/json",
                                data=body, headers={"Content-Type": "application/json"}))
        return [(a["name"], a.get("score", 0)) for a in data if a.get("name")]
    except Exception as e:
        print(f"    ! LB {mbid}: {e}")
        return []


def bc_search_artist(name):
    """Resolve an artist name -> their Bandcamp page URL (exact artist match, not a label)."""
    body = json.dumps({"search_text": name, "search_filter": "b",
                       "full_page": False, "fan_id": None}).encode()
    try:
        data = json.loads(fetch(BC_SEARCH, data=body,
                                headers={"Content-Type": "application/json", "User-Agent": BROWSER_UA}))
    except Exception:
        return None
    target = norm(name)
    for r in data.get("auto", {}).get("results", []):
        if r.get("type") == "b" and not r.get("is_label") and norm(r.get("name", "")) == target:
            return r.get("item_url_root") or r.get("url")
    return None


def bandcamp_discoveries(name):
    """Up to MAX_PER_ARTIST of an artist's Bandcamp releases, as discovery cards."""
    url = bc_search_artist(name)
    if not url:
        return []
    out = []
    try:
        for rel in latest_releases(url, MAX_PER_ARTIST):
            if not rel.get("id"):
                continue
            out.append({
                "artist": rel.get("artist") or name, "title": rel.get("title", ""),
                "url": rel.get("url", ""), "buy": rel.get("url", ""),
                "art": rel.get("art", ""), "id": rel.get("id"),
                "type": rel.get("type", "album"),
                "label": "", "source": "bandcamp", "kind": "discovery",
            })
    except Exception:
        pass
    return out


def audius_host():
    return json.loads(fetch("https://api.audius.co"))["data"][0]


def audius_track(host, artist):
    """Find a streamable Audius track whose uploader IS this artist (exact)."""
    q = urllib.parse.quote(artist)
    try:
        tracks = json.loads(fetch(f"{host}/v1/tracks/search?query={q}&app_name=CrateDigger")).get("data", [])
    except Exception:
        return None
    target = norm(artist)
    for t in tracks:
        u = t.get("user", {})
        if not t.get("is_streamable"):
            continue
        if target == norm(u.get("name", "")) or target == norm(u.get("handle", "")):
            art = t.get("artwork") or {}
            return {
                "id": t["id"], "title": t.get("title", ""),
                "artist": u.get("name", artist),
                "art": art.get("480x480") or art.get("150x150") or "",
                "stream": f"{host}/v1/tracks/{t['id']}/stream?app_name=CrateDigger",
                "url": "https://audius.co/" + u.get("handle", ""),
                "buy": "https://bandcamp.com/search?q=" + urllib.parse.quote(f"{artist} {t.get('title','')}"),
                "source": "audius", "kind": "discovery", "label": "",
            }
    return None


def main():
    with open(PROFILE, encoding="utf-8") as fh:
        profile = json.load(fh)

    owned = {norm(n) for n, _ in profile.get("top_artists", [])}
    seeds = []
    for name, _ in profile.get("top_artists", []):
        if norm(name) in JUNK:
            continue
        seeds.append(name)
        if len(seeds) >= MAX_SEEDS:
            break
    seed_set = {norm(s) for s in seeds}
    print(f"Seeds ({len(seeds)}): {', '.join(seeds)}\n")

    # MusicBrainz + ListenBrainz: build a pool, scored by seed CONSENSUS.
    weight = defaultdict(float)
    votes = defaultdict(int)
    for i, seed in enumerate(seeds, 1):
        mbid = mb_resolve(seed.replace("_", " "))
        time.sleep(1.1)                       # MusicBrainz politeness
        if not mbid:
            print(f"  [{i}/{len(seeds)}] {seed}: no MBID")
            continue
        sims = lb_similar(mbid)               # already ranked best-first
        n = len(sims) or 1
        new = 0
        for rank, (name, _score) in enumerate(sims):
            if norm(name) in owned or norm(name) in seed_set:
                continue
            weight[name] += 1.0 - rank / n
            votes[name] += 1
            new += 1
        print(f"  [{i}/{len(seeds)}] {seed}: {len(sims)} similar, {new} new")
        time.sleep(0.3)

    order = sorted(weight, key=lambda nm: (votes[nm], weight[nm]), reverse=True)
    ranked = order[:MAX_CANDIDATES]
    multi = sum(1 for nm in weight if votes[nm] >= 2)
    print(f"\n{len(weight)} candidates ({multi} backed by 2+ seeds); "
          f"resolving up to {BC_CAP} Bandcamp + {AU_CAP} Audius ...")

    host = audius_host()
    discovered, seen_ids = [], set()
    bc_hits = au_hits = 0
    for name in ranked:
        if bc_hits >= BC_CAP and au_hits >= AU_CAP:
            break
        added = []
        if bc_hits < BC_CAP:                        # Bandcamp (buyable, embedded)
            for rel in bandcamp_discoveries(name):
                if rel["id"] in seen_ids:
                    continue
                seen_ids.add(rel["id"]); discovered.append(rel); added.append("bandcamp"); bc_hits += 1
        if au_hits < AU_CAP:                         # Audius (streamable -> auto-playable)
            tr = audius_track(host, name)
            if tr and tr["id"] not in seen_ids:
                seen_ids.add(tr["id"]); discovered.append(tr); added.append("audius"); au_hits += 1
        if added:
            print(f"  ♪ {name}  ->  {', '.join(added)}")
        time.sleep(0.3)

    if not discovered:
        sys.exit("Found no new artists (sources unreachable?); keeping the previous discoveries.")
    profile["discovered"] = discovered
    with open(PROFILE, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(discovered)} playable discoveries "
          f"({bc_hits} Bandcamp, {au_hits} Audius) to taste_profile.json")


if __name__ == "__main__":
    main()
