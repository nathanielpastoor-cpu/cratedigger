# 🎧 CrateDigger

A personal music-discovery tool — "Tinder for crate-digging" — tuned to No Marks'
lane (deep/experimental bass: dubstep, halftime, drum & bass, wonky) with side
rooms for psych-rock, lofi/synthwave, and Latin.

It learns what your music library is, then pulls **new** tracks from places that
fit it — new releases on labels you buy from, brand-new artists similar to the
ones you collect, per-genre radio, and SoundCloud free downloads / deep cuts —
and lets you swipe through them, save the keepers to a buy-list, and listen in
the card.

---

## Quick start

- **Use it:** open **`swipe.html`** in your browser. That's the whole app.
- **Get fresh music:** run **`python refresh.py`** — it re-pulls everything and
  rebuilds `swipe.html` (then opens it). Do this whenever you want new stuff.
- **Re-scan your library** (only if your `N:\Music` collection changed):
  `python refresh.py --full`.

---

## The app (`swipe.html`)

One track per card, art + in-card player.

- **Move:** the **‹ ›** arrows on the artwork (or **← →**). Back actually goes
  back — you can revisit something you skipped.
- **Save:** **♥** (or **↑**). It saves the track to your buy-list and *keeps
  playing* — tap **♥** again to un-save.
- **Pass:** **✕** (or **↓**). Trains the ranker away from it and moves on.
- **Own it:** **💿** (or **O**). For a track you already have — it counts toward
  your taste (so the ranker finds better-suited tracks) but stays *off* the buy-list.
- **Genre dropdown** (top): **✨ Surprise me** = your personalized deck
  (labels + similar-artist discoveries, learned ranking). Or pick a genre for a
  streaming radio of it, or **🔊 SoundCloud · Free DLs / Deep cuts**.
- **Buy-list:** the **♥ count** (top-right) opens your saved tracks, each with a
  buy/download link, plus **⬇ Export** to a clickable file.
- **⚙ Settings:** *Auto-play radio* (Surprise-me streams hands-free),
  *Auto-advance after like*, and *Reset*.
- **Mood lighting:** each track samples its cover's average color and tints the
  whole page + glows the card to match — so every new track shifts the room.
- It remembers your likes, what you've seen, and what it's learned (in the
  browser), so you can close it and pick up later.

The ranker keeps a like/dislike tally per **label** and **artist**; tracks score
higher when their label/artist have been liked, with a little randomness so it
keeps exploring instead of tunnelling.

---

## How it finds music

The official APIs for the obvious platforms are mostly closed (SoundCloud's is
gated, Bandcamp killed its public one, Spotify cut recommendations for new apps),
so CrateDigger uses the open/practical routes:

| Source | Used for |
| --- | --- |
| **Bandcamp** (label `/music` pages) | new releases on the 178 labels you buy from — *buyable* |
| **MusicBrainz → ListenBrainz** | the recommendation brain — similar artists, ID-matched so it can't confuse a name (no grindcore "Repulsion") |
| **Audius** (open API) | streaming playback for new-artist discoveries + per-genre radio decks |
| **SoundCloud** (public web `client_id`) | free downloads + low-play "deep cuts" |

---

## Scripts

Run individually, or all at once with `refresh.py`.

| Script | What it does |
| --- | --- |
| `profile_library.py` | Scans `N:\Music\01 - Music Library`, reads tags/filenames, writes your taste profile (top artists, labels, genres, BPM, keys) to `taste_profile.json`. Run when the library changes. |
| `bandcamp_fresh.py` | Pulls recent releases from each Bandcamp label in your profile. |
| `recommend.py` | Finds NEW artists beyond your labels (MusicBrainz → ListenBrainz → resolve on Bandcamp/Audius). |
| `genres.py` | Builds a streaming deck per genre from Audius. |
| `soundcloud.py` | Builds SoundCloud free-DL and deep-cut decks. |
| `build_swipe.py` | Merges everything into `swipe.html` (the app). |
| `refresh.py` | Runs the whole pipeline in order. |
| `discover.py` | Original approach: Last.fm similar-artists → `crate.html`, a clickable list + Bandcamp label-watch. Superseded by the swipe app but still works (needs a Last.fm key — see below). |

**Data:** everything lives in `taste_profile.json` (local, yours). Outputs are
`swipe.html` (the app) and `crate.html` (the older list).

---

## Setup

- **Python 3.12+** (already installed).
- One dependency: `pip install mutagen` (for reading audio tags in
  `profile_library.py`). Everything else is Python standard library.
- **`discover.py` only:** needs a free Last.fm API key, already saved to your
  `LASTFM_API_KEY` environment variable. Get one at
  <https://www.last.fm/api/account/create> if it ever needs replacing.

---

## Honest caveats

- **SoundCloud access** uses the public `client_id` shipped in their website's
  JavaScript (the same method yt-dlp uses). It's a gray area against their API
  terms — personal use, public data only. That key **rotates**, so if a
  SoundCloud deck ever comes back empty, just re-run `soundcloud.py` (or
  `refresh.py`) and it grabs a fresh one.
- **Streaming vs buying:** Bandcamp cards are buyable in-card. Audius (genre +
  some discovery) and SoundCloud cards are for *listening* — each still drops a
  buy/download link into your buy-list.
- **Free DLs ≠ obscure:** the Free DLs deck filters on the free-download flag, so
  some are popular. The truly-unheard stuff is in **Deep cuts** (low play count).
- Genre/SoundCloud decks are baked in at build time, so refresh to get new ones.

---

## Hosting (auto-refreshing site)

The site is one static page (`index.html`), rebuilt and redeployed on a schedule
by GitHub Actions (`.github/workflows/refresh.yml`) → GitHub Pages.

- The workflow runs the discovery pipeline (bandcamp → recommend → genres →
  soundcloud → build) daily and on manual trigger, then deploys the fresh page.
  No secrets/keys needed — every source is keyless from the runner.
- `profile_library.py` is **not** run in CI (it reads your local `N:\` library).
  When your library changes, re-run it locally and commit the new
  `taste_profile.json`.

**Deploy:** push this repo to GitHub → **Settings → Pages → Source: GitHub
Actions** → **Actions tab → Refresh CrateDigger → Run workflow**. Live at
`https://<user>.github.io/<repo>/`.
