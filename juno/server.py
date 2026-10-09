r"""
juno/server.py  —  CrateDigger on Juno: serve the site AND refresh it daily, in one process.

Replaces the GitHub Actions + GitHub Pages setup. Runs inside the `cratedigger` TrueNAS app
(see juno/compose.yaml). Python standard library only, so the stock python image needs nothing.

    /app    this repo, read-only (copied to Juno by juno/ship-juno.ps1)
    /data   the app's own folder on Juno, writable:
              site/index.html       what visitors get
              taste_profile.json    the profile the fetchers update (seeded from /app on first run)
              status.json           when the last refresh ran and how each step went
              work/                 scratch copy of the scripts for each run

The refresh runs once a day at REFRESH_AT (local time, TZ from the container), and once at start-up
when the page on disk is older than a day. Each fetcher may fail without stopping the run (a flaky
source just keeps its previous data), exactly like the old workflow; only build_swipe.py must work,
and the live page is swapped only when it does.

Endpoints: /  (the site)   /healthz  (200 "ok")   /status.json  (last refresh report)
"""
import datetime as dt
import http.server
import json
import os
import shutil
import subprocess
import sys
import threading
import time

APP = os.environ.get("APP_DIR", "/app")
DATA = os.environ.get("DATA_DIR", "/data")
PORT = int(os.environ.get("PORT", "8080"))
REFRESH_AT = os.environ.get("REFRESH_AT", "04:00")          # HH:MM, local time
STEP_TIMEOUT = int(os.environ.get("STEP_TIMEOUT", "1800"))   # seconds per script

SITE = os.path.join(DATA, "site")
WORK = os.path.join(DATA, "work")
PROFILE = os.path.join(DATA, "taste_profile.json")
STATUS = os.path.join(DATA, "status.json")
FETCHERS = ["bandcamp_fresh.py", "recommend.py", "genres.py", "soundcloud.py"]

lock = threading.Lock()                                       # one refresh at a time


def log(msg):
    print(f"[{dt.datetime.now():%Y-%m-%d %H:%M:%S}] {msg}", flush=True)


def write_atomic(path, data):
    tmp = path + ".tmp"
    with open(tmp, "wb") as fh:
        fh.write(data)
    os.replace(tmp, path)


def refresh():
    """One full pipeline run. Returns the status dict it saved."""
    with lock:
        started = time.time()
        log("refresh: starting")
        os.makedirs(SITE, exist_ok=True)
        if not os.path.exists(PROFILE):
            shutil.copyfile(os.path.join(APP, "taste_profile.json"), PROFILE)

        # Fresh scratch copy: the scripts write next to themselves, and /app is read-only.
        shutil.rmtree(WORK, ignore_errors=True)
        os.makedirs(WORK)
        for name in os.listdir(APP):
            if name.endswith(".py"):
                shutil.copyfile(os.path.join(APP, name), os.path.join(WORK, name))
        shutil.copyfile(PROFILE, os.path.join(WORK, "taste_profile.json"))

        env = {**os.environ, "CI": "1", "PYTHONIOENCODING": "utf-8"}   # CI=1: no browser
        steps = []
        for script in FETCHERS + ["build_swipe.py"]:
            t0 = time.time()
            try:
                rc = subprocess.run([sys.executable, script], cwd=WORK, env=env,
                                    timeout=STEP_TIMEOUT).returncode
            except subprocess.TimeoutExpired:
                rc = "timeout"
            steps.append({"step": script, "ok": rc == 0, "exit": rc, "seconds": round(time.time() - t0)})
            log(f"refresh: {script} -> {rc}")

        built = steps[-1]["ok"] and os.path.exists(os.path.join(WORK, "index.html"))
        if built:
            with open(os.path.join(WORK, "index.html"), "rb") as fh:
                write_atomic(os.path.join(SITE, "index.html"), fh.read())
            # keep what the fetchers found, so a source that fails tomorrow keeps today's data
            with open(os.path.join(WORK, "taste_profile.json"), "rb") as fh:
                write_atomic(PROFILE, fh.read())
        status = {
            "finished": dt.datetime.now().isoformat(timespec="seconds"),
            "seconds": round(time.time() - started),
            "published": built,
            "fresh": built and any(s["ok"] for s in steps[:-1]),   # false = rebuilt from old data only
            "steps": steps,
        }
        write_atomic(STATUS, json.dumps(status, indent=2).encode())
        log(f"refresh: done, published={built}")
        return status


def seconds_until_next_run(now=None):
    now = now or dt.datetime.now()
    hh, mm = (int(x) for x in REFRESH_AT.split(":"))
    nxt = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if nxt <= now:
        nxt += dt.timedelta(days=1)
    return (nxt - now).total_seconds()


def page_age_hours():
    try:
        return (time.time() - os.path.getmtime(os.path.join(SITE, "index.html"))) / 3600
    except OSError:
        return None


def scheduler():
    age = page_age_hours()
    if age is None or age > 24:
        if age is None:   # first start: show the committed page right away while the first refresh runs
            os.makedirs(SITE, exist_ok=True)
            shutil.copyfile(os.path.join(APP, "index.html"), os.path.join(SITE, "index.html"))
        safe_refresh()
    while True:
        time.sleep(seconds_until_next_run())
        safe_refresh()


def safe_refresh():
    try:
        refresh()
    except Exception as e:                                    # never let the schedule die
        log(f"refresh: crashed: {e!r}")


class Handler(http.server.BaseHTTPRequestHandler):
    server_version = "CrateDigger"

    def _send(self, code, body, ctype, cache="no-cache"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/healthz":
            return self._send(200, b"ok", "text/plain")
        if path == "/status.json":
            try:
                with open(STATUS, "rb") as fh:
                    return self._send(200, fh.read(), "application/json")
            except OSError:
                return self._send(200, b'{"finished": null}', "application/json")
        if path in ("/", "/index.html"):
            try:
                with open(os.path.join(SITE, "index.html"), "rb") as fh:
                    return self._send(200, fh.read(), "text/html; charset=utf-8")
            except OSError:
                return self._send(503, b"CrateDigger is building its first page. Try again in a few minutes.",
                                  "text/plain")
        self._send(404, b"not found", "text/plain")

    do_HEAD = do_GET

    def log_message(self, fmt, *args):                        # quiet: health checks every 30 s
        pass


def main():
    if "--once" in sys.argv:                                  # manual run: python server.py --once
        sys.exit(0 if refresh()["published"] else 1)
    threading.Thread(target=scheduler, daemon=True).start()
    log(f"serving on :{PORT}, daily refresh at {REFRESH_AT}")
    http.server.ThreadingHTTPServer(("0.0.0.0", PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
