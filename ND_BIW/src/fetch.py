"""Download helper: saves each file exactly as received and records where and when it came from.

Files that do not change after release (a Census vintage, a closed QCEW year) go to data/raw and are
downloaded once. Files that change often (monthly BFS, quarterly taxable sales, BEA) go to data/live
and are refreshed after `max_age_days`. If a download fails, the last copy is kept and used.

Automatic updates (src/update.py) set BIW_RECHECK=1: every file in data/live is then checked with the publisher on
each run, with a conditional request (ETag / If-Modified-Since), so an unchanged file costs one small request and a
new release is downloaded the same day. The publisher's file date (Last-Modified) is kept as the release date.
"""
import email.utils
import hashlib
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
import requests
from config import OUT, USER_AGENT

LOG = OUT / "downloads.json"
VINTAGES = OUT / "vintages.json"


def recheck():
    """True during an automatic update: re-check every changing file with its publisher."""
    return os.environ.get("BIW_RECHECK") == "1"


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def http_date(value):
    """'Thu, 12 Nov 2026 15:00:32 GMT' -> ISO date-time in UTC (None if missing or unreadable)."""
    try:
        return email.utils.parsedate_to_datetime(value).astimezone(timezone.utc).isoformat(timespec="seconds")
    except (TypeError, ValueError, IndexError):
        return None


def read_log():
    try:
        return json.loads(LOG.read_text()) if LOG.exists() else {}
    except ValueError:
        return {}


def _log(path, url, status, headers=None, sha=None, changed=False):
    log = read_log()
    rec = log.get(str(path.name), {})
    rec.update({"url": url, "status": status, "checked": now_iso()})
    if headers is not None:
        lm = http_date(headers.get("Last-Modified"))
        if lm:
            rec["last_modified"] = lm
        if headers.get("ETag"):
            rec["etag"] = headers["ETag"]
    if sha:
        rec["sha256"] = sha
    if status == "downloaded":
        rec["downloaded"] = rec["checked"]
    if changed:                                   # new content: the publisher's file date, else the day it was found
        rec["released"] = rec.get("last_modified") or rec["checked"]
        rec["released_basis"] = "publisher file date" if rec.get("last_modified") else "first found"
    log[str(path.name)] = rec
    LOG.write_text(json.dumps(log, indent=1, sort_keys=True))


def _sha(b):
    return hashlib.sha256(b).hexdigest()


def get(url, path: Path, max_age_days=None, timeout=300, check=None):
    """Return a local copy of `url` at `path`.

    max_age_days=None: download only if missing (fixed releases). A number: refresh when older, and on every
    automatic update (conditional request: unchanged files are not downloaded again).
    check(bytes) -> bool guards against error pages saved as data.
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    fresh = max_age_days is None or time.time() - path.stat().st_mtime < max_age_days * 86400 if path.exists() else False
    if path.exists() and fresh and not (recheck() and max_age_days is not None):
        return path
    headers = {"User-Agent": USER_AGENT}
    prev = read_log().get(path.name, {}) if path.exists() else {}
    if prev.get("etag"):
        headers["If-None-Match"] = prev["etag"]
    if prev.get("last_modified"):
        headers["If-Modified-Since"] = email.utils.format_datetime(datetime.fromisoformat(prev["last_modified"]),
                                                                   usegmt=True)
    try:
        r = requests.get(url, headers=headers, timeout=timeout)
        if r.status_code == 304 and path.exists():
            os.utime(path)                        # still current: restart the age clock
            _log(path, url, "unchanged", r.headers)
            return path
        r.raise_for_status()
        if check is not None and not check(r.content):
            raise ValueError("unexpected content (not the data file)")
        sha = _sha(r.content)
        if path.exists() and sha == (prev.get("sha256") or _sha(path.read_bytes())):
            os.utime(path)
            _log(path, url, "unchanged", r.headers, sha)
            return path
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_bytes(r.content)
        tmp.replace(path)
        _log(path, url, "downloaded", r.headers, sha, changed=True)
    except Exception as e:
        if not path.exists():
            _log(path, url, f"failed: {str(e)[:120]}")
            raise
        print(f"    download failed ({str(e)[:80]}); using last copy of {path.name}")
        _log(path, url, "failed, kept last copy")
    return path


def exists(url, timeout=60):
    """True when the publisher has a file at `url` (HEAD request, redirects followed)."""
    try:
        r = requests.head(url, headers={"User-Agent": USER_AGENT}, timeout=timeout, allow_redirects=True)
        return r.status_code == 200
    except requests.RequestException:
        return False


def vintage(name, known, url_of, ahead=2, max_age_days=1):
    """Newest yearly release available: `known` (the year the code was last checked with) or a later year whose file
    the publisher has put up. Probed at most once a day; the answer is kept in outputs/vintages.json. A new year is
    used automatically; if its layout changed, the step fails, the last good tables are kept and the checks say so."""
    try:
        cache = json.loads(VINTAGES.read_text()) if VINTAGES.exists() else {}
    except ValueError:
        cache = {}
    rec = cache.get(name, {})
    age = (datetime.now(timezone.utc) - datetime.fromisoformat(rec["checked"])).days if rec.get("checked") else 1e9
    if rec.get("year", 0) >= known and age < max_age_days and not recheck():
        return rec["year"]
    year = max(known, rec.get("year", known))
    for y in range(year + 1, year + ahead + 1):
        if exists(url_of(y)):
            year = y
    if year != rec.get("year"):
        print(f"    {name}: newest release is {year}" + (f" (code was set for {known})" if year > known else ""))
    cache[name] = {"year": year, "checked": now_iso(), "known": known}
    VINTAGES.write_text(json.dumps(cache, indent=1, sort_keys=True))
    return year


def is_zip(b):
    return b[:2] == b"PK"


def is_csv(b):
    return not b.lstrip()[:15].lower().startswith((b"<html", b"<!doctype"))
