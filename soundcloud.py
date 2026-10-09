"""
soundcloud.py  —  Build two SoundCloud decks for the dropdown:
  * "🔊 Free DLs"  — tracks with a working free download (downloadable flag)
  * "🔊 Deep cuts" — low-play-count tracks ("no one else has")

How it gets access: SoundCloud's official API is gated, so this grabs the public
`client_id` the website ships in its JS (same trick yt-dlp uses) and calls the
internal search endpoint. Gray area re: their API ToS, personal use only; the
client_id rotates, so this re-grabs it every run. Playback in the app uses
SoundCloud's credential-free embed widget.

Strategy (learned from probing): generic terms return mainstream noise, so query
genre/STYLE terms in his lane; add "free download" to surface free DLs; filter by
play count for obscurity; cap duration to favor tracks over hour-long mixes.

Stdlib only.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "taste_profile.json")
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/124.0 Safari/537.36")

# His lane — bass / dubstep / dnb / halftime / wonky styles.
TERMS = ["deep dubstep", "halftime", "drum and bass", "neurofunk", "wonky bass",
         "future garage", "140 bass", "liquid drum and bass", "dub techno", "jungle",
         "experimental bass", "halftime dnb"]
MAX_PER_DECK = 70
DEEP_MAX_PLAYS = 3000          # "no one else has"
DEEP_MIN_PLAYS = 25            # avoid total dead air
MAX_DURATION_MS = 12 * 60_000  # favor tracks, not hour-long mixes


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def get_client_id():
    html = fetch("https://soundcloud.com/")
    for src in reversed(re.findall(r'<script[^>]+src="(https://[^"]+\.js)"', html)):
        try:
            m = re.search(r'client_id\s*[:=]\s*"([0-9A-Za-z]{20,})"', fetch(src))
            if m:
                return m.group(1)
        except Exception:
            pass
    return None


def search(cid, q, limit=40):
    url = ("https://api-v2.soundcloud.com/search/tracks?q=" + urllib.parse.quote(q)
           + "&client_id=" + cid + "&limit=" + str(limit))
    try:
        return json.loads(fetch(url)).get("collection", [])
    except Exception as e:
        print(f"   ! '{q}': {e}")
        return []


def art_of(t):
    a = t.get("artwork_url") or ((t.get("user") or {}).get("avatar_url"))
    return a.replace("-large", "-t500x500") if a else ""


def card(t, mode):
    free = bool(t.get("downloadable") and t.get("has_downloads_left"))
    return {
        "artist": (t.get("user") or {}).get("username", ""),
        "title": t.get("title", ""),
        "id": "sc" + str(t.get("id")),           # prefix so ids never collide with other sources
        "type": "track", "source": "soundcloud", "kind": "soundcloud",
        "label": mode, "free": free, "plays": t.get("playback_count") or 0,
        "art": art_of(t),
        "url": t.get("permalink_url", ""), "buy": t.get("permalink_url", ""),
    }


def main():
    cid = get_client_id()
    if not cid:
        print("FAILED to get client_id"); return
    print("client_id ok\n")

    free_deck, deep_deck = [], []
    seen_free, seen_deep = set(), set()
    for term in TERMS:
        # free DLs
        for t in search(cid, term + " free download"):
            if not (t.get("downloadable") and t.get("has_downloads_left")):
                continue
            if (t.get("full_duration") or t.get("duration") or 0) > MAX_DURATION_MS:
                continue
            if t["id"] in seen_free:
                continue
            seen_free.add(t["id"]); free_deck.append(card(t, "Free DL"))
        # deep cuts
        for t in search(cid, term):
            plays = t.get("playback_count") or 0
            if not (DEEP_MIN_PLAYS <= plays < DEEP_MAX_PLAYS):
                continue
            if (t.get("full_duration") or t.get("duration") or 0) > MAX_DURATION_MS:
                continue
            if t["id"] in seen_deep:
                continue
            seen_deep.add(t["id"]); deep_deck.append(card(t, "Deep cut"))
        print(f"  {term:24} free:{len(free_deck):>3}  deep:{len(deep_deck):>3}")
        time.sleep(0.3)

    # sort: free by most-recent-feel (leave order), deep by fewest plays first
    deep_deck.sort(key=lambda c: c["plays"])
    free_deck = free_deck[:MAX_PER_DECK]
    deep_deck = deep_deck[:MAX_PER_DECK]

    if not free_deck and not deep_deck:
        sys.exit("SoundCloud returned nothing; keeping the previous decks.")
    with open(PROFILE, encoding="utf-8") as fh:
        profile = json.load(fh)
    profile["soundcloud"] = {
        "🔊 SoundCloud · Free DLs": free_deck,
        "🔊 SoundCloud · Deep cuts": deep_deck,
    }
    with open(PROFILE, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, ensure_ascii=False)
    print(f"\nSaved {len(free_deck)} free DLs + {len(deep_deck)} deep cuts to taste_profile.json")


if __name__ == "__main__":
    main()
