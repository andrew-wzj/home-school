"""SQLite storage. One file: data/homeschool.db.

Records are kept even when Focus (supervision) is off; Focus only silences
reminders.
"""
import datetime as dt
import json
import os
import sqlite3
import threading

from . import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
  key TEXT PRIMARY KEY,
  value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS segment_progress (
  course_id TEXT NOT NULL,
  segment_id TEXT NOT NULL,
  watched_at TEXT NOT NULL,
  PRIMARY KEY (course_id, segment_id)
);
CREATE TABLE IF NOT EXISTS sessions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id TEXT NOT NULL,
  lecture_id TEXT,
  planned_min INTEGER NOT NULL,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  actual_min REAL,
  breaks INTEGER DEFAULT 0
);
CREATE TABLE IF NOT EXISTS answers (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id TEXT NOT NULL,
  ref TEXT NOT NULL,
  question TEXT NOT NULL,
  text TEXT NOT NULL,
  verdict TEXT,
  feedback TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS mastery (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id TEXT NOT NULL,
  assignment_id TEXT NOT NULL,
  concept TEXT NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('passed','retest','pending')),
  note TEXT,
  created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS stuck (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id TEXT NOT NULL,
  ref TEXT NOT NULL,
  question TEXT NOT NULL,
  minutes REAL NOT NULL,
  description TEXT,
  created_at TEXT NOT NULL,
  resolved_at TEXT
);
CREATE TABLE IF NOT EXISTS attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  course_id TEXT NOT NULL,
  assignment_id TEXT NOT NULL,
  question TEXT NOT NULL,
  minutes REAL NOT NULL,
  outcome TEXT NOT NULL CHECK (outcome IN ('done','stuck')),
  created_at TEXT NOT NULL
);
"""

DEFAULTS = {
    "lang": "en",
    "focus": True,
    "course": "cmu-15-110-s26",
    "pace": 3,               # lectures per week (brief: 3 or 2, undecided)
    "start_date": None,      # set on first run
    "session_default": 30,   # minutes, used until there is enough history
    "break_every": 25,
    "break_len": 5,
    "stuck_minutes": 15,
}


def now():
    return dt.datetime.now().replace(microsecond=0).isoformat()


class DB:
    def __init__(self, path=None):
        path = path or os.path.join(config.DATA_DIR, "homeschool.db")
        if path != ":memory:":
            os.makedirs(os.path.dirname(path), exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.conn.executescript(SCHEMA)
            self.conn.commit()

    # --- low level -------------------------------------------------------
    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.conn.execute(sql, args).fetchall()]

    def x(self, sql, args=()):
        with self.lock:
            cur = self.conn.execute(sql, args)
            self.conn.commit()
            return cur.lastrowid

    # --- settings --------------------------------------------------------
    def settings(self):
        out = dict(DEFAULTS)
        for r in self.q("SELECT key, value FROM settings"):
            try:
                out[r["key"]] = json.loads(r["value"])
            except ValueError:
                pass
        if not out.get("start_date"):
            out["start_date"] = dt.date.today().isoformat()
            self.set_setting("start_date", out["start_date"])
        return out

    def set_setting(self, key, value):
        if key not in DEFAULTS:
            raise KeyError(key)
        self.x("INSERT INTO settings(key, value) VALUES(?, ?) "
               "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
               (key, json.dumps(value)))

    # --- progress --------------------------------------------------------
    def watched(self, course_id):
        return {r["segment_id"]: r["watched_at"] for r in self.q(
            "SELECT segment_id, watched_at FROM segment_progress WHERE course_id = ?", (course_id,))}

    def set_watched(self, course_id, segment_id, watched=True):
        if watched:
            self.x("INSERT OR IGNORE INTO segment_progress VALUES(?, ?, ?)", (course_id, segment_id, now()))
        else:
            self.x("DELETE FROM segment_progress WHERE course_id = ? AND segment_id = ?", (course_id, segment_id))

    # --- sessions --------------------------------------------------------
    def start_session(self, course_id, lecture_id, planned):
        return self.x("INSERT INTO sessions(course_id, lecture_id, planned_min, started_at) VALUES(?,?,?,?)",
                      (course_id, lecture_id, int(planned), now()))

    def end_session(self, sid, actual_min, breaks):
        self.x("UPDATE sessions SET ended_at = ?, actual_min = ?, breaks = ? WHERE id = ? AND ended_at IS NULL",
               (now(), float(actual_min), int(breaks), sid))

    def sessions(self, course_id, limit=20):
        return self.q("SELECT * FROM sessions WHERE course_id = ? AND ended_at IS NOT NULL "
                      "ORDER BY id DESC LIMIT ?", (course_id, limit))

    # --- answers ---------------------------------------------------------
    def add_answer(self, course_id, ref, question, text, verdict=None, feedback=None):
        return self.x("INSERT INTO answers(course_id, ref, question, text, verdict, feedback, created_at) "
                      "VALUES(?,?,?,?,?,?,?)", (course_id, ref, question, text, verdict, feedback, now()))

    def answers(self, course_id, ref):
        return self.q("SELECT * FROM answers WHERE course_id = ? AND ref = ? ORDER BY id DESC", (course_id, ref))

    # --- mastery ---------------------------------------------------------
    def set_mastery(self, course_id, assignment_id, concept, status, note=None):
        return self.x("INSERT INTO mastery(course_id, assignment_id, concept, status, note, created_at) "
                      "VALUES(?,?,?,?,?,?)", (course_id, assignment_id, concept, status, note, now()))

    def mastery_history(self, course_id, assignment_id=None):
        if assignment_id:
            return self.q("SELECT * FROM mastery WHERE course_id = ? AND assignment_id = ? ORDER BY id",
                          (course_id, assignment_id))
        return self.q("SELECT * FROM mastery WHERE course_id = ? ORDER BY id", (course_id,))

    def mastery_current(self, course_id, assignment_id):
        cur = {}
        for r in self.mastery_history(course_id, assignment_id):
            cur[r["concept"]] = r
        return cur

    # --- stuck points ----------------------------------------------------
    def add_stuck(self, course_id, ref, question, minutes, description=""):
        return self.x("INSERT INTO stuck(course_id, ref, question, minutes, description, created_at) "
                      "VALUES(?,?,?,?,?,?)", (course_id, ref, question, float(minutes), description, now()))

    def resolve_stuck(self, sid):
        self.x("UPDATE stuck SET resolved_at = ? WHERE id = ?", (now(), sid))

    def stuck(self, course_id, ref=None, open_only=False):
        sql = "SELECT * FROM stuck WHERE course_id = ?"
        args = [course_id]
        if ref:
            sql += " AND ref = ?"
            args.append(ref)
        if open_only:
            sql += " AND resolved_at IS NULL"
        return self.q(sql + " ORDER BY id DESC", args)

    # --- question attempts (per-question timer) --------------------------
    def add_attempt(self, course_id, assignment_id, question, minutes, outcome):
        return self.x("INSERT INTO attempts(course_id, assignment_id, question, minutes, outcome, created_at) "
                      "VALUES(?,?,?,?,?,?)", (course_id, assignment_id, question, float(minutes), outcome, now()))

    def attempts(self, course_id):
        return self.q("SELECT * FROM attempts WHERE course_id = ? ORDER BY id", (course_id,))
