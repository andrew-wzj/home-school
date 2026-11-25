"""Course loading, the personal schedule, and "what do I do today".

Everything here is deterministic and documented, because the brief leaves
the real algorithms open. Each heuristic is a placeholder that is easy to
replace once there is data:

* Schedule: lectures land on fixed weekdays at `pace` lectures per week,
  starting from the user's start date. Assignment due dates sit a fixed
  number of days after their last lecture (same gap as the original course).
* Suggested session length: the default (30 min, unverified) until there are
  3 finished sessions; then the median of the last 5, rounded to 5 minutes and
  clamped to 20-90.
* Today's plan: the next unwatched segments that fit in that length.
"""
import datetime as dt
import json
import math
import os
from urllib.parse import urljoin

from . import config

WEEKDAYS = {1: [0], 2: [0, 3], 3: [0, 2, 4], 4: [0, 1, 3, 4], 5: [0, 1, 2, 3, 4]}
PREP_MIN = 5
QUIZ_MIN = 5
WATCH_FACTOR = 1.2   # pausing, rewinding, taking notes


def load_course(course_id):
    path = os.path.join(config.COURSES_DIR, course_id, "course.json")
    with open(path, encoding="utf-8") as f:
        course = json.load(f)
    site = course.get("site", "")

    def absolute(u):
        return u if (not u or u.startswith("http")) else urljoin(site, u)

    for lec in course["lectures"]:
        lec["slides"] = absolute(lec.get("slides"))
        if lec.get("code"):
            lec["code"] = absolute(lec["code"])
    for a in course["assignments"]:
        for m in a["materials"]:
            m["url"] = absolute(m["url"])
    return course


def list_courses():
    out = []
    for name in sorted(os.listdir(config.COURSES_DIR)):
        if os.path.exists(os.path.join(config.COURSES_DIR, name, "course.json")):
            out.append(name)
    return out


def lecture_map(course):
    return {l["id"]: l for l in course["lectures"]}


def module_of(course, lecture_id):
    for m in course["modules"]:
        if lecture_id in m["lectures"]:
            return m
    return None


def seg_minutes(seg):
    if seg.get("start") is None or seg.get("end") is None:
        return seg.get("read_minutes", 15)
    return max(1, int(math.ceil((seg["end"] - seg["start"]) / 60.0 * WATCH_FACTOR)))


# --- schedule -------------------------------------------------------------

def schedule(course, start_date, pace):
    """Map lecture id -> planned date (dt.date)."""
    days = WEEKDAYS.get(int(pace), WEEKDAYS[3])
    d = start_date if isinstance(start_date, dt.date) else dt.date.fromisoformat(start_date)
    out = {}
    for lec in course["lectures"]:
        while d.weekday() not in days:
            d += dt.timedelta(days=1)
        out[lec["id"]] = d
        d += dt.timedelta(days=1)
    return out


def due_dates(course, sched):
    out = {}
    for a in course["assignments"]:
        rule = a["due_after"]
        out[a["id"]] = sched[rule["lecture"]] + dt.timedelta(days=rule["days"])
    return out


# --- session length -------------------------------------------------------

def suggested_minutes(sessions, default):
    usable = [s["actual_min"] for s in sessions if s.get("actual_min") and s["actual_min"] >= 5][:5]
    if len(usable) < 3:
        return int(default), "default"
    usable.sort()
    mid = len(usable) // 2
    med = usable[mid] if len(usable) % 2 else (usable[mid - 1] + usable[mid]) / 2.0
    return int(min(90, max(20, 5 * round(med / 5.0)))), "history"


# --- today ----------------------------------------------------------------

def answer_target(course, lecture):
    """Which question the answer box in this lecture is for."""
    if lecture.get("question"):
        return {"ref": lecture["id"], "kind": "lecture", "text": lecture["question"]}
    mod = module_of(course, lecture["id"])
    if mod and mod.get("answer_after") == lecture["id"]:
        return {"ref": mod["id"], "kind": "module", "text": mod["question"]}
    return {"ref": lecture["id"] + "-recall", "kind": "recall", "text": {
        "en": "Without looking: explain the main ideas of what you just watched, in your own words.",
        "zh": "不看笔记：用自己的话讲清楚刚才这部分的主要内容。"}}


def next_lecture(course, watched):
    for lec in course["lectures"]:
        if any(s["id"] not in watched for s in lec["segments"]):
            return lec
    return None


def today_plan(course, watched, minutes):
    lec = next_lecture(course, watched)
    if not lec:
        return None
    todo = [s for s in lec["segments"] if s["id"] not in watched]
    budget = max(5, minutes - PREP_MIN - QUIZ_MIN)
    chosen, used = [], 0
    for s in todo:
        m = seg_minutes(s)
        if chosen and used + m > budget:
            break
        chosen.append(s)
        used += m
    pages = ", ".join(s["pages"] for s in chosen if s.get("pages") and s["pages"] != "all") or "all"
    return {
        "lecture": lec["id"],
        "segments": [s["id"] for s in chosen],
        "finishes_lecture": len(chosen) == len(todo),
        "pages": pages,
        "steps": {"prep": PREP_MIN, "watch": used, "quiz": QUIZ_MIN},
        "total": PREP_MIN + used + QUIZ_MIN,
        "has_video": bool(lec.get("video")),
    }


def week_progress(course, sched, watched, today=None):
    today = today or dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    sunday = monday + dt.timedelta(days=6)
    planned = [l for l in course["lectures"] if monday <= sched[l["id"]] <= sunday]
    done = [l for l in planned if all(s["id"] in watched for s in l["segments"])]
    return {"done": len(done), "planned": len(planned)}


def progress_notes(attempts, mastery, lang="en"):
    """Concrete, data-backed progress notes. Never generic praise.

    Returns at most one note, or none when nothing real improved.
    """
    def day(iso):
        d = dt.date.fromisoformat(iso[:10])
        return d.strftime("%b %-d") if lang == "en" else "%d月%d日" % (d.month, d.day)

    # 1) Same question, faster than the first try, and finished this time.
    by_q = {}
    for a in attempts:
        by_q.setdefault((a["assignment_id"], a["question"]), []).append(a)
    best = None
    for (aid, q), rows in by_q.items():
        first, last = rows[0], rows[-1]
        if len(rows) >= 2 and last["outcome"] == "done" and last["minutes"] < first["minutes"] * 0.85:
            gain = first["minutes"] - last["minutes"]
            if not best or gain > best[0]:
                best = (gain, aid, q, first, last)
    if best:
        _, aid, q, first, last = best
        if lang == "en":
            return "%s · %s: %d min on %s, %d min on %s." % (
                aid.upper(), q, round(first["minutes"]), day(first["created_at"]),
                round(last["minutes"]), day(last["created_at"]))
        return "%s · %s：%s 用了 %d 分钟，%s 只用 %d 分钟。" % (
            aid.upper(), q, day(first["created_at"]), round(first["minutes"]),
            day(last["created_at"]), round(last["minutes"]))

    # 2) A concept that failed earlier and has now passed.
    hist = {}
    for m in mastery:
        hist.setdefault((m["assignment_id"], m["concept"]), []).append(m)
    for (aid, concept), rows in hist.items():
        if rows[-1]["status"] == "passed":
            fails = [r for r in rows[:-1] if r["status"] == "retest"]
            if fails:
                if lang == "en":
                    return "%s: retest on %s, passed on %s." % (
                        concept, day(fails[0]["created_at"]), day(rows[-1]["created_at"]))
                return "%s：%s 没过，%s 通过。" % (
                    concept, day(fails[0]["created_at"]), day(rows[-1]["created_at"]))
    return None
