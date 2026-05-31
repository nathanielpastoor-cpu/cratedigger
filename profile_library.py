"""
profile_library.py  —  Build a "taste profile" from your music library.

It walks every audio file, pulls the artist/label/genre/BPM/key out of the
ID3 tags where they exist, and falls back to parsing the filename where they
don't (most of your WAVs). Then it ranks everything and writes two things:

  taste_profile.json  -> machine-readable, fed into the discovery stage next
  (prints a human summary to the screen)

Re-run it any time your library grows. Nothing here touches your files; it
only reads them.
"""

import os
import re
import sys
import json
from collections import Counter

import mutagen
from mutagen.id3 import ID3
from mutagen.mp4 import MP4Tags

# Print unicode (track titles in other scripts/languages) without crashing the
# Windows console.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = r"N:\Music\01 - Music Library"
HERE = os.path.dirname(os.path.abspath(__file__))
OUT_JSON = os.path.join(HERE, "taste_profile.json")

AUDIO_EXTS = {".wav", ".aiff", ".aif", ".mp3", ".m4a", ".flac"}
# Folders to ignore: your own productions and utility files aren't "taste."
SKIP_DIR_MARKERS = ("\\No Marks\\", "\\Test Tones\\")

# Strings that mean "this isn't a real artist name."
NOT_AN_ARTIST = {
    "various artists", "various", "va", "v.a.", "unknown", "unknown artist",
    "", "compilation",
}
BANDCAMP_RE = re.compile(r"https?://([\w-]+)\.bandcamp\.com", re.I)
BEATPORT_ID_RE = re.compile(r"^\d{6,}_")          # e.g. 12463973_Title_Original_Mix
COLLAB_SPLIT_RE = re.compile(r"\s*(?:,|&| x | vs\.? )\s*", re.I)


def clean_artist(name):
    """Normalise an artist string and split obvious collaborations into a list."""
    if not name:
        return []
    name = name.strip().strip("-").strip()
    if name.lower() in NOT_AN_ARTIST:
        return []
    parts = [p.strip() for p in COLLAB_SPLIT_RE.split(name) if p.strip()]
    # Drop "feat. X" tails from each piece.
    out = []
    for p in parts:
        p = re.split(r"\s+(?:feat\.?|ft\.?|featuring|w/|with)\s+", p, flags=re.I)[0].strip()
        if p and p.lower() not in NOT_AN_ARTIST:
            out.append(p)
    return out


def first_text(tags, key):
    """Pull a single string out of an ID3 frame (or return None)."""
    frame = tags.get(key)
    if frame is None:
        return None
    try:
        return str(frame.text[0]).strip()
    except Exception:
        return str(frame).strip()


def parse_filename(stem):
    """Best-effort artist/title from a filename when there are no tags."""
    if BEATPORT_ID_RE.match(stem):
        return None, stem  # Beatport download: artist not in the name
    parts = [p.strip() for p in stem.split(" - ") if p.strip()]
    if len(parts) >= 2:
        return parts[0], parts[-1]   # first token = artist, last = title-ish
    return None, stem               # single token: no reliable artist


def read_tags(path):
    """Return dict(artist, genre, album, label, bpm, key, year, bandcamp) or {}."""
    try:
        f = mutagen.File(path)
    except Exception:
        f = None
    if f is None or f.tags is None:
        return {}

    info = {}
    tags = f.tags
    if isinstance(tags, ID3):
        info["artist"] = first_text(tags, "TPE1")
        info["genre"] = first_text(tags, "TCON")
        info["album"] = first_text(tags, "TALB")
        info["label"] = first_text(tags, "TPE2")     # album-artist often = label
        info["bpm"] = first_text(tags, "TBPM")
        info["key"] = first_text(tags, "TKEY")
        info["year"] = first_text(tags, "TDRC")
        # The Bandcamp source URL lives in a COMM (comment) frame.
        for k, v in tags.items():
            if k.startswith("COMM"):
                m = BANDCAMP_RE.search(str(v))
                if m:
                    info["bandcamp"] = m.group(0)
                    info["label_slug"] = m.group(1)
                    break
    elif isinstance(tags, MP4Tags):
        info["artist"] = (tags.get("\xa9ART") or tags.get("aART") or [None])[0]
        info["genre"] = (tags.get("\xa9gen") or [None])[0]
        info["album"] = (tags.get("\xa9alb") or [None])[0]
        info["label"] = (tags.get("aART") or [None])[0]
    else:  # FLAC / Vorbis comments use lowercase keys
        def vc(key):
            val = tags.get(key)
            return val[0] if val else None
        info["artist"] = vc("artist")
        info["genre"] = vc("genre")
        info["album"] = vc("album")
        info["label"] = vc("albumartist") or vc("label")
    return {k: v for k, v in info.items() if v}


def main():
    artists = Counter()
    genres = Counter()
    keys = Counter()
    years = Counter()
    bpms = Counter()
    labels = Counter()           # label name -> count
    label_urls = {}              # label slug -> bandcamp url
    compilations_seen = 0

    total = tagged = filename_parsed = no_artist = 0

    for dirpath, _, files in os.walk(ROOT):
        if any(m in dirpath + "\\" for m in SKIP_DIR_MARKERS):
            continue
        for fn in files:
            ext = os.path.splitext(fn)[1].lower()
            if ext not in AUDIO_EXTS:
                continue
            total += 1
            path = os.path.join(dirpath, fn)
            stem = os.path.splitext(fn)[0]

            info = read_tags(path)
            artist_raw = info.get("artist")
            source = "tag"
            if not artist_raw:
                artist_raw, _ = parse_filename(stem)
                source = "filename"

            if artist_raw:
                names = clean_artist(artist_raw)
                if names:
                    if source == "tag":
                        tagged += 1
                    else:
                        filename_parsed += 1
                    for n in names:
                        artists[n] += 1
                else:
                    no_artist += 1
                    compilations_seen += 1
            else:
                no_artist += 1

            if info.get("genre"):
                genres[info["genre"].strip()] += 1
            if info.get("key"):
                keys[info["key"].strip()] += 1
            if info.get("year"):
                years[info["year"][:4]] += 1
            if info.get("label"):
                labels[info["label"].strip()] += 1
            if info.get("label_slug"):
                label_urls[info["label_slug"]] = info["bandcamp"]
                labels[info["label_slug"]] += 1
            if info.get("bpm"):
                try:
                    bpms[int(round(float(info["bpm"])))] += 1
                except ValueError:
                    pass

    # ---- coarse BPM buckets (genre fingerprints for a DJ) ----
    buckets = Counter()
    for bpm, c in bpms.items():
        lo = (bpm // 10) * 10
        buckets[f"{lo}-{lo+9}"] += c

    profile = {
        "root": ROOT,
        "totals": {
            "audio_files": total,
            "artist_from_tag": tagged,
            "artist_from_filename": filename_parsed,
            "no_artist_found": no_artist,
        },
        "top_artists": artists.most_common(60),
        "top_labels": labels.most_common(40),
        "label_bandcamp_urls": label_urls,
        "top_genres": genres.most_common(30),
        "bpm_buckets": sorted(buckets.items()),
        "top_keys": keys.most_common(24),
        "years": sorted(years.items()),
    }
    with open(OUT_JSON, "w", encoding="utf-8") as fh:
        json.dump(profile, fh, indent=2, ensure_ascii=False)

    # ---------- human-readable summary ----------
    def show(title, pairs, n):
        print(f"\n## {title}")
        for name, c in pairs[:n]:
            print(f"  {c:>4}  {name}")

    print("=" * 60)
    print("TASTE PROFILE  —", ROOT)
    print("=" * 60)
    t = profile["totals"]
    print(f"Audio files scanned : {t['audio_files']}")
    print(f"  artist from tag    : {t['artist_from_tag']}")
    print(f"  artist from name   : {t['artist_from_filename']}")
    print(f"  no artist found    : {t['no_artist_found']}")
    show("TOP ARTISTS", profile["top_artists"], 35)
    show("TOP LABELS (your best discovery vector)", profile["top_labels"], 25)
    show("TOP GENRES (from tags)", profile["top_genres"], 20)
    print("\n## BPM SPREAD")
    for rng, c in profile["bpm_buckets"]:
        print(f"  {c:>4}  {rng} bpm")
    show("KEYS", profile["top_keys"], 24)
    print(f"\nWrote {OUT_JSON}")


if __name__ == "__main__":
    main()
