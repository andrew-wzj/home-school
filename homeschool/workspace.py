"""Local homework folders, test runs, and the calendar export.

workspace/ is in .gitignore: the course forbids publishing solutions, so
nothing the user writes here should ever reach the repository.
"""
import datetime as dt
import os
import re
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse

from . import config

SAFE = re.compile(r"^[A-Za-z0-9._-]+$")


def folder(course_id, assignment_id):
    return os.path.join(config.WORKSPACE_DIR, course_id, assignment_id)


def files(course_id, assignment_id):
    d = folder(course_id, assignment_id)
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d) if not f.startswith(".") and os.path.isfile(os.path.join(d, f)))


def download(course, assignment):
    """Fetch materials from the course site. Existing files are never overwritten."""
    d = folder(course["id"], assignment["id"])
    os.makedirs(d, exist_ok=True)
    site = urlparse(course["site"]).netloc
    saved, skipped = [], []
    for m in assignment["materials"]:
        name = m["label"]
        if not SAFE.match(name) or urlparse(m["url"]).netloc != site:
            skipped.append(name)
            continue
        path = os.path.join(d, name)
        if os.path.exists(path):
            skipped.append(name)
            continue
        req = urllib.request.Request(m["url"], headers={"user-agent": "home-school/0.1"})
        with urllib.request.urlopen(req, timeout=60) as r:
            data = r.read()
        with open(path, "wb") as f:
            f.write(data)
        saved.append(name)
    return {"saved": saved, "skipped": skipped, "folder": d}


def run_tests(course_id, assignment_id, timeout=60):
    d = folder(course_id, assignment_id)
    tests = [f for f in files(course_id, assignment_id) if f.startswith("test_") and f.endswith(".py")]
    if not tests:
        return {"ran": False, "tests": []}
    try:
        p = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", d, "-p", "test_*.py", "-v"],
                           cwd=d, capture_output=True, text=True, timeout=timeout)
        out = (p.stdout + p.stderr)[-20000:]
        ok = p.returncode == 0
    except subprocess.TimeoutExpired:
        out, ok = "Timed out after %ds (infinite loop or waiting for input()?)" % timeout, False
    m = re.search(r"Ran (\d+) tests?", out)
    fails = re.search(r"FAILED \((.*?)\)", out)
    return {"ran": True, "ok": ok, "tests": tests, "count": int(m.group(1)) if m else 0,
            "summary": fails.group(1) if fails else ("OK" if ok else ""), "output": out}


def _ics_text(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def calendar(course, sched, dues, lang="en"):
    """An .ics file: one all-day event per lecture, one 23:59 event per due date."""
    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    title = course["title"]["zh" if lang == "zh" else "en"]
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//home-school//EN",
             "X-WR-CALNAME:" + _ics_text("%s %s" % (course["code"], title))]
    for lec in course["lectures"]:
        d = sched[lec["id"]]
        lines += ["BEGIN:VEVENT", "UID:%s-%s@home-school" % (course["id"], lec["id"]), "DTSTAMP:" + stamp,
                  "DTSTART;VALUE=DATE:" + d.strftime("%Y%m%d"),
                  "DTEND;VALUE=DATE:" + (d + dt.timedelta(days=1)).strftime("%Y%m%d"),
                  "SUMMARY:" + _ics_text("%s %s · %s" % (course["code"], lec["id"], lec["title"]["zh" if lang == "zh" else "en"])),
                  "END:VEVENT"]
    for a in course["assignments"]:
        d = dues[a["id"]]
        lines += ["BEGIN:VEVENT", "UID:%s-%s-due@home-school" % (course["id"], a["id"]), "DTSTAMP:" + stamp,
                  "DTSTART:" + d.strftime("%Y%m%d") + "T235900",
                  "DTEND:" + (d + dt.timedelta(days=1)).strftime("%Y%m%d") + "T000000",
                  "SUMMARY:" + _ics_text(("%s %s 截止" if lang == "zh" else "%s %s due") % (course["code"], a["name"])),
                  "BEGIN:VALARM", "TRIGGER:-P1D", "ACTION:DISPLAY", "DESCRIPTION:" + _ics_text(a["name"]), "END:VALARM",
                  "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"
