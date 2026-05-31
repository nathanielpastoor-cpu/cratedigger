r"""
refresh.py  —  Re-pull everything and rebuild the swipe app in ONE command.

    python refresh.py            # refresh music + rebuild  (the usual)
    python refresh.py --full     # also rescan your N:\ library first (slow)

Runs the pipeline in order, stopping if any step fails:

    bandcamp_fresh.py   new releases from your Bandcamp labels
    recommend.py        new artists (MusicBrainz -> ListenBrainz -> Bandcamp/Audius)
    genres.py           per-genre decks from Audius
    soundcloud.py       SoundCloud free-DL + deep-cut decks
    build_swipe.py      writes swipe.html and opens it

profile_library.py is only needed when your library itself changes (it rescans
~3000 files), so it runs only with --full.
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

STEPS = ["bandcamp_fresh.py", "recommend.py", "genres.py", "soundcloud.py", "build_swipe.py"]
if "--full" in sys.argv:
    STEPS.insert(0, "profile_library.py")


def run(script):
    print(f"\n{'=' * 64}\n  ▶  {script}\n{'=' * 64}", flush=True)
    # force UTF-8 in the child so unicode track titles never crash its console
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    result = subprocess.run([sys.executable, os.path.join(HERE, script)], env=env)
    if result.returncode != 0:
        sys.exit(f"\n!! {script} failed (exit {result.returncode}) — stopping the pipeline.")


def main():
    print(f"CrateDigger refresh — {len(STEPS)} steps")
    for s in STEPS:
        run(s)
    print(f"\n{'=' * 64}\n  ✅  Done. swipe.html rebuilt"
          f"{' (and your library re-scanned)' if '--full' in sys.argv else ''}.\n{'=' * 64}")


if __name__ == "__main__":
    main()
