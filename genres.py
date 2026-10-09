"""
genres.py  —  Build per-genre decks (from Audius) for the genre dropdown.

Your library's genres mapped to Audius genres; for each, pull trending streamable
tracks. Saved to taste_profile.json under "genre_decks" = {label: [tracks]}.
The dropdown in swipe.html switches the deck to the chosen genre; "Surprise me"
uses your personalized label+discovery deck instead.

Stdlib only.
"""
import json
import sys
import time
import urllib.parse
import urllib.request

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
import os
HERE = os.path.dirname(os.path.abspath(__file__))
PROFILE = os.path.join(HERE, "taste_profile.json")
UA = "CrateDigger/1.0 (+https://github.com/nathanielpastoor-cpu/cratedigger)"
PER_GENRE = 50

# (label shown in the dropdown  ->  Audius genre to query) — drawn from his library genres
GENRE_MAP = [
    ("Dubstep", "Dubstep"),
    ("Drum & Bass", "Drum & Bass"),
    ("Free Form Bass", "Future Bass"),
    ("Bass / Experimental", "Experimental"),
    ("Glitch Hop", "Glitch Hop"),
    ("Lo-Fi", "Lo-Fi"),
    ("Electronic", "Electronic"),
    ("Ambient", "Ambient"),
    ("Cumbia / Latin", "Latin"),
    ("Alternative Rock", "Rock"),
]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=25) as r:
        return r.read().decode("utf-8", "replace")


def main():
    host = json.loads(get("https://api.audius.co"))["data"][0]
    decks = {}
    for label, genre in GENRE_MAP:
        url = (f"{host}/v1/tracks/trending?genre=" + urllib.parse.quote(genre)
               + "&app_name=CrateDigger")
        try:
            tracks = json.loads(get(url)).get("data", [])
        except Exception as e:
            print(f"  ! {label}: {e}"); continue
        deck = []
        for t in tracks:
            if not t.get("is_streamable"):
                continue
            u = t.get("user", {})
            art = t.get("artwork") or {}
            deck.append({
                "artist": u.get("name", ""), "title": t.get("title", ""),
                "art": art.get("480x480") or art.get("150x150") or "",
                "id": t["id"], "type": "track", "source": "audius", "kind": "genre",
                "label": label,
                "stream": f"{host}/v1/tracks/{t['id']}/stream?app_name=CrateDigger",
                "url": "https://audius.co/" + u.get("handle", ""),
                "buy": "https://bandcamp.com/search?q=" + urllib.parse.quote(f"{u.get('name','')} {t.get('title','')}"),
            })
            if len(deck) >= PER_GENRE:
                break
        if deck:
            decks[label] = deck
        print(f"  {label:22} ({genre}): {len(deck)}")
        time.sleep(0.2)

    if not decks:
        sys.exit("Audius returned no genre decks; keeping the previous ones.")
    with open(PROFILE, encoding="utf-8") as fh:
        profile = json.load(fh)
    profile["genre_decks"] = decks
    with open(PROFILE, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, ensure_ascii=False)
    print(f"\nSaved {sum(len(v) for v in decks.values())} tracks across "
          f"{len(decks)} genres to taste_profile.json")


if __name__ == "__main__":
    main()
