"""Local web server: static files from web/ plus a small JSON API.

Listens on 127.0.0.1 only. Because some endpoints run local tests and hold an
API key, every request must carry a localhost Host header (blocks DNS
rebinding) and every POST must carry the X-Home-School header, which a
cross-site page cannot set without a CORS preflight that we never grant.
"""
import datetime as dt
import json
import mimetypes
import os
import posixpath
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import ai, config, planner, prompts, workspace
from .db import DB


class App:
    def __init__(self, db=None):
        self.db = db or DB()

    # --- helpers ---------------------------------------------------------
    def course(self):
        return planner.load_course(self.db.settings()["course"])

    def _sched(self, course, s):
        sched = planner.schedule(course, s["start_date"], s["pace"])
        return sched, planner.due_dates(course, sched)

    def state(self):
        s = self.db.settings()
        course = self.course()
        for lec in course["lectures"]:
            lec["target"] = planner.answer_target(course, lec)
        cid = course["id"]
        watched = self.db.watched(cid)
        sched, dues = self._sched(course, s)
        minutes, basis = planner.suggested_minutes(self.db.sessions(cid), s["session_default"])
        today = dt.date.today()

        due = []
        for a in course["assignments"]:
            cur = self.db.mastery_current(cid, a["id"])
            passed = sum(1 for c in a["concepts"] if cur.get(c["en"], {}).get("status") == "passed")
            due.append({"id": a["id"], "name": a["name"], "date": dues[a["id"]].isoformat(),
                        "days": (dues[a["id"]] - today).days,
                        "done": passed == len(a["concepts"])})
        due.sort(key=lambda d: d["date"])

        open_stuck = self.db.stuck(cid, open_only=True)
        return {
            "settings": s,
            "ai": config.public_config(),
            "course": course,
            "watched": watched,
            "schedule": {k: v.isoformat() for k, v in sched.items()},
            "due": due,
            "suggested": {"minutes": minutes, "basis": basis},
            "today": planner.today_plan(course, watched, minutes),
            "week": planner.week_progress(course, sched, watched, today),
            "last_stuck": open_stuck[0] if open_stuck else None,
            "note": planner.progress_notes(self.db.attempts(cid), self.db.mastery_history(cid), s["lang"]),
            "date": today.isoformat(),
        }

    def assignment(self, aid):
        s = self.db.settings()
        course = self.course()
        a = next((x for x in course["assignments"] if x["id"] == aid), None)
        if not a:
            raise LookupError(aid)
        cid = course["id"]
        _, dues = self._sched(course, s)
        stuck = self.db.stuck(cid, ref=aid)
        open_items = ["%s (%d min)" % (x["question"], round(x["minutes"])) for x in stuck if not x["resolved_at"]]
        folder = workspace.folder(cid, aid)
        return {
            "assignment": a,
            "due": dues[aid].isoformat(),
            "days": (dues[aid] - dt.date.today()).days,
            "mastery": self.db.mastery_current(cid, aid),
            "stuck": stuck,
            "attempts": [x for x in self.db.attempts(cid) if x["assignment_id"] == aid][-10:],
            "folder": folder,
            "files": workspace.files(cid, aid),
            "prompt": {lang: prompts.homework_prompt(course, a, lang, folder, open_items) for lang in ("en", "zh")},
        }

    def evaluate(self, body):
        s = self.db.settings()
        course = self.course()
        lang = s["lang"]
        ref, question, text = body["ref"], body["question"], body.get("text", "").strip()
        if not text:
            raise ValueError("Answer is empty.")
        points = body.get("points") or []
        name = "CMU %s %s" % (course["code"], course["title"]["en"])
        if not ai.configured():
            self.db.add_answer(course["id"], ref, question, text)
            return {"sent": False, "copy": prompts.grader_copy_prompt(name, question, points, text, lang)}
        system, user = prompts.grader(name, question, points, text, lang)
        reply = ai.ask(system, user)
        verdict = prompts.parse_verdict(reply)
        self.db.add_answer(course["id"], ref, question, text, verdict, reply)
        return {"sent": True, "verdict": verdict, "feedback": reply}

    # --- routing ---------------------------------------------------------
    def get(self, path, query):
        cid = self.db.settings()["course"]
        if path == "/api/state":
            return self.state()
        m = re.match(r"^/api/assignment/([\w-]+)$", path)
        if m:
            return self.assignment(m.group(1))
        if path == "/api/answers":
            return self.db.answers(cid, query.get("ref", [""])[0])
        raise LookupError(path)

    def post(self, path, b):
        db = self.db
        cid = db.settings()["course"]
        if path == "/api/settings":
            for k, v in b.items():
                db.set_setting(k, v)
            return {"ok": True}
        if path == "/api/config":
            cfg = config.load_config()
            provider = b.get("provider") or cfg.get("provider")
            if provider not in config.PROVIDERS:
                raise ValueError("Unknown provider.")
            if provider != cfg.get("provider"):
                cfg["model"] = ""
            cfg["provider"] = provider
            if b.get("api_key"):
                cfg["api_key"] = b["api_key"].strip()
            if b.get("clear_key"):
                cfg.pop("api_key", None)
            if "model" in b:
                cfg["model"] = b["model"].strip()
            config.save_config(cfg)
            return config.public_config()
        if path == "/api/segment":
            db.set_watched(cid, b["segment_id"], bool(b.get("watched", True)))
            return {"ok": True}
        if path == "/api/session/start":
            return {"id": db.start_session(cid, b.get("lecture_id"), b.get("planned", 30))}
        if path == "/api/session/end":
            db.end_session(int(b["id"]), b.get("actual_min", 0), b.get("breaks", 0))
            return {"ok": True}
        if path == "/api/answer":
            return self.evaluate(b)
        if path == "/api/stuck":
            return {"id": db.add_stuck(cid, b["ref"], b["question"], b.get("minutes", 0), b.get("description", ""))}
        if path == "/api/stuck/resolve":
            db.resolve_stuck(int(b["id"]))
            return {"ok": True}
        if path == "/api/attempt":
            return {"id": db.add_attempt(cid, b["assignment_id"], b["question"], b["minutes"], b["outcome"])}
        if path == "/api/mastery":
            if b["status"] not in ("passed", "retest", "pending"):
                raise ValueError("Bad status.")
            return {"id": db.set_mastery(cid, b["assignment_id"], b["concept"], b["status"], b.get("note"))}
        m = re.match(r"^/api/assignment/([\w-]+)/(download|test)$", path)
        if m:
            course = self.course()
            a = next((x for x in course["assignments"] if x["id"] == m.group(1)), None)
            if not a:
                raise LookupError(m.group(1))
            if m.group(2) == "download":
                return workspace.download(course, a)
            return workspace.run_tests(cid, a["id"])
        raise LookupError(path)

    def calendar(self):
        s = self.db.settings()
        course = self.course()
        sched, dues = self._sched(course, s)
        return workspace.calendar(course, sched, dues, s["lang"])


def make_handler(app, port):
    allowed_hosts = {"127.0.0.1:%d" % port, "localhost:%d" % port}

    class Handler(BaseHTTPRequestHandler):
        server_version = "HomeSchool/0.1"

        def log_message(self, fmt, *args):
            if os.environ.get("HOMESCHOOL_LOG"):
                BaseHTTPRequestHandler.log_message(self, fmt, *args)

        def _send(self, code, body, ctype="application/json; charset=utf-8", extra=None):
            data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(data)

        def _host_ok(self):
            if self.headers.get("Host") not in allowed_hosts:
                self._send(403, {"error": "Forbidden host"})
                return False
            return True

        def _api(self, fn):
            try:
                self._send(200, fn())
            except LookupError as e:
                self._send(404, {"error": "Not found: %s" % e})
            except (ValueError, KeyError) as e:
                self._send(400, {"error": str(e)})
            except ai.AIError as e:
                self._send(502, {"error": str(e)})
            except Exception as e:  # keep the server alive, report the error
                self._send(500, {"error": "%s: %s" % (type(e).__name__, e)})

        def do_GET(self):
            if not self._host_ok():
                return
            u = urlparse(self.path)
            if u.path == "/api/calendar.ics":
                try:
                    body = app.calendar().encode("utf-8")
                except Exception as e:
                    return self._send(500, {"error": str(e)})
                return self._send(200, body, "text/calendar; charset=utf-8",
                                  {"Content-Disposition": 'attachment; filename="home-school.ics"'})
            if u.path.startswith("/api/"):
                return self._api(lambda: app.get(u.path, parse_qs(u.query)))
            self._static(u.path)

        def do_POST(self):
            if not self._host_ok():
                return
            if self.headers.get("X-Home-School") != "1":
                return self._send(403, {"error": "Missing X-Home-School header"})
            n = int(self.headers.get("Content-Length") or 0)
            if n > 1_000_000:
                return self._send(413, {"error": "Too large"})
            try:
                body = json.loads(self.rfile.read(n) or b"{}")
            except ValueError:
                return self._send(400, {"error": "Bad JSON"})
            self._api(lambda: app.post(urlparse(self.path).path, body))

        def _static(self, path):
            rel = posixpath.normpath(path).lstrip("/") or "index.html"
            full = os.path.join(config.WEB_DIR, *rel.split("/"))
            if not os.path.realpath(full).startswith(os.path.realpath(config.WEB_DIR)) or not os.path.isfile(full):
                full = os.path.join(config.WEB_DIR, "index.html")
            ctype = mimetypes.guess_type(full)[0] or "application/octet-stream"
            if ctype.startswith("text/") or ctype in ("application/javascript",):
                ctype += "; charset=utf-8"
            with open(full, "rb") as f:
                self._send(200, f.read(), ctype)

    return Handler


def serve(port=8110, open_browser=True):
    app = App()
    httpd = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, port))
    url = "http://127.0.0.1:%d/" % port
    print("Home School running at %s  (Ctrl+C to stop)" % url)
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
