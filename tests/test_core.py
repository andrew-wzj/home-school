import datetime as dt
import json
import os
import tempfile
import threading
import unittest
import urllib.request
from http.server import ThreadingHTTPServer

TMP = tempfile.mkdtemp()
os.environ["HOMESCHOOL_DATA"] = os.path.join(TMP, "data")
os.environ["HOMESCHOOL_WORKSPACE"] = os.path.join(TMP, "ws")
os.environ["HOMESCHOOL_CONFIG"] = os.path.join(TMP, "config.local.json")

from homeschool import planner, prompts, transcript, workspace  # noqa: E402
from homeschool.db import DB  # noqa: E402
from homeschool.server import App, make_handler  # noqa: E402

COURSE = planner.load_course("cmu-15-110-s26")


class TranscriptTest(unittest.TestCase):
    def test_parse_and_dedupe_rolling_captions(self):
        vtt = ("WEBVTT\n\n00:00:01.000 --> 00:00:03.000\nhello <c>world</c>\n\n"
               "00:00:03.000 --> 00:00:05.000\nhello world\nthis is new text here\n\n"
               "00:01:10.500 --> 00:01:12.000\nlater &amp; more\n")
        cues = transcript.parse_vtt(vtt)
        self.assertEqual(cues[0], (1.0, "hello world"))
        self.assertEqual(cues[1][1], "this is new text here")
        self.assertEqual(cues[2], (70.5, "later & more"))
        self.assertTrue(transcript.compact(cues, 30).startswith("[0:01] hello world this is new"))


class CourseDataTest(unittest.TestCase):
    def test_segments_are_contiguous_and_inside_video(self):
        for lec in COURSE["lectures"]:
            if not lec["video"]:
                continue
            segs = lec["segments"]
            self.assertEqual(segs[0]["start"], 0, lec["id"])
            for a, b in zip(segs, segs[1:]):
                self.assertEqual(a["end"], b["start"], a["id"])
            self.assertLessEqual(segs[-1]["end"], lec["video"]["duration"], lec["id"])
            for s in segs:
                for k in ("title", "summary", "points"):
                    self.assertIn("zh", s[k], s["id"])

    def test_material_urls_are_absolute(self):
        for a in COURSE["assignments"]:
            for m in a["materials"]:
                self.assertTrue(m["url"].startswith("https://www.cs.cmu.edu/~15110-s26/"), m["url"])


class PlannerTest(unittest.TestCase):
    def test_schedule_mwf_from_a_wednesday(self):
        sched = planner.schedule(COURSE, "2026-11-25", 3)  # a Wednesday
        self.assertEqual(sched["L1"], dt.date(2026, 11, 25))
        self.assertEqual(sched["L2"], dt.date(2026, 11, 27))
        self.assertEqual(sched["L3"], dt.date(2026, 11, 30))
        dues = planner.due_dates(COURSE, sched)
        self.assertEqual(dues["check1"], dt.date(2026, 12, 4))

    def test_two_per_week(self):
        sched = planner.schedule(COURSE, "2026-11-30", 2)  # Monday
        self.assertEqual([sched[l]. weekday() for l in ("L1", "L2", "L3")], [0, 3, 0])

    def test_suggested_minutes(self):
        self.assertEqual(planner.suggested_minutes([], 30), (30, "default"))
        rows = [{"actual_min": m} for m in (42, 38, 51, 3)]
        self.assertEqual(planner.suggested_minutes(rows, 30), (40, "history"))

    def test_today_plan_fits_budget_and_always_has_one_segment(self):
        watched = {"L1-1": "x"}
        p = planner.today_plan(COURSE, watched, 30)
        self.assertEqual(p["lecture"], "L2")
        self.assertEqual(p["segments"], ["L2-1"])  # L2-2 alone is ~20 min, does not fit after L2-1
        p = planner.today_plan(COURSE, dict(watched, **{"L2-1": "x"}), 20)
        self.assertEqual(p["segments"], ["L2-2"])  # too long, but at least one

    def test_answer_target(self):
        lm = planner.lecture_map(COURSE)
        self.assertEqual(planner.answer_target(COURSE, lm["L2"])["kind"], "lecture")
        self.assertEqual(planner.answer_target(COURSE, lm["L5"])["ref"], "m1")
        self.assertEqual(planner.answer_target(COURSE, lm["L4"])["kind"], "recall")

    def test_progress_note_needs_real_improvement(self):
        a = [{"assignment_id": "hw1", "question": "Q4", "minutes": 18, "outcome": "stuck", "created_at": "2026-11-11T10:00:00"},
             {"assignment_id": "hw1", "question": "Q4", "minutes": 9, "outcome": "done", "created_at": "2026-11-25T10:00:00"}]
        self.assertEqual(planner.progress_notes(a, [], "en"), "HW1 · Q4: 18 min on Nov 11, 9 min on Nov 25.")
        self.assertIsNone(planner.progress_notes(a[:1], [], "en"))
        m = [{"assignment_id": "hw1", "concept": "return vs. print", "status": "retest", "created_at": "2026-11-20T00:00:00"},
             {"assignment_id": "hw1", "concept": "return vs. print", "status": "passed", "created_at": "2026-11-24T00:00:00"}]
        self.assertIn("passed on Nov 24", planner.progress_notes([], m, "en"))


class PromptTest(unittest.TestCase):
    def test_homework_prompt(self):
        hw = next(a for a in COURSE["assignments"] if a["id"] == "hw1")
        p = prompts.homework_prompt(COURSE, hw, "en", "/x/hw1", ["Q3 (15 min)"])
        self.assertIn("CMU 15-110 · Hw1", p)
        self.assertIn("define vs. call; return vs. print; parameters", p)
        self.assertIn("test_hw1.py", p)
        self.assertIn("Q3 (15 min)", p)
        zh = prompts.homework_prompt(COURSE, hw, "zh", "/x/hw1", [])
        self.assertIn("你是我的作业辅导老师", zh)

    def test_verdict(self):
        self.assertEqual(prompts.parse_verdict("VERDICT: NOT YET\nmissing x"), "not_yet")
        self.assertEqual(prompts.parse_verdict("VERDICT: PASS"), "pass")
        self.assertIsNone(prompts.parse_verdict("hmm"))


class WorkspaceTest(unittest.TestCase):
    def test_run_tests(self):
        d = workspace.folder("c", "a")
        os.makedirs(d, exist_ok=True)
        self.assertFalse(workspace.run_tests("c", "a")["ran"])
        with open(os.path.join(d, "test_x.py"), "w") as f:
            f.write("import unittest\nclass T(unittest.TestCase):\n def test_a(self): self.assertEqual(1, 1)\n"
                    " def test_b(self): self.assertEqual(1, 2)\n")
        r = workspace.run_tests("c", "a")
        self.assertTrue(r["ran"])
        self.assertFalse(r["ok"])
        self.assertEqual(r["count"], 2)
        self.assertIn("failures=1", r["summary"])

    def test_calendar(self):
        sched = planner.schedule(COURSE, "2026-11-25", 3)
        ics = workspace.calendar(COURSE, sched, planner.due_dates(COURSE, sched))
        self.assertIn("SUMMARY:15-110 Hw1 due", ics)
        self.assertEqual(ics.count("BEGIN:VEVENT"), len(COURSE["lectures"]) + len(COURSE["assignments"]))


class ServerTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = App(DB(":memory:"))
        cls.httpd = ThreadingHTTPServer(("127.0.0.1", 0), None)
        port = cls.httpd.server_address[1]
        cls.httpd.RequestHandlerClass = make_handler(cls.app, port)
        cls.base = "http://127.0.0.1:%d" % port
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()

    def req(self, path, body=None, headers=None):
        h = {"X-Home-School": "1", "Content-Type": "application/json"}
        h.update(headers or {})
        data = json.dumps(body).encode() if body is not None else None
        r = urllib.request.Request(self.base + path, data=data, headers=h, method="POST" if body is not None else "GET")
        try:
            with urllib.request.urlopen(r) as resp:
                return resp.status, resp.read()
        except urllib.error.HTTPError as e:
            return e.code, e.read()

    def test_state_and_flow(self):
        code, raw = self.req("/api/state")
        self.assertEqual(code, 200)
        s = json.loads(raw)
        self.assertEqual(s["today"]["lecture"], "L1")
        self.assertEqual(s["suggested"]["minutes"], 30)
        self.assertEqual(self.req("/api/segment", {"segment_id": "L1-1"})[0], 200)
        s = json.loads(self.req("/api/state")[1])
        self.assertEqual(s["today"]["lecture"], "L2")
        # no key: answer is stored and a copy-paste prompt comes back
        r = json.loads(self.req("/api/answer", {"ref": "L2", "question": "q", "text": "my answer", "points": ["p"]})[1])
        self.assertFalse(r["sent"])
        self.assertIn("my answer", r["copy"])
        a = json.loads(self.req("/api/assignment/hw1")[1])
        self.assertIn("You are my homework tutor.", a["prompt"]["en"])
        self.assertEqual(self.req("/", None)[0], 200)

    def test_post_requires_custom_header(self):
        r = urllib.request.Request(self.base + "/api/settings", data=b'{"lang":"zh"}', method="POST",
                                   headers={"Content-Type": "application/json"})
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(r)
        self.assertEqual(cm.exception.code, 403)

    def test_rejects_foreign_host(self):
        code, _ = self.req("/api/state", headers={"Host": "evil.example:80"})
        self.assertEqual(code, 403)

    def test_static_cannot_escape_web_dir(self):
        code, body = self.req("/../homeschool/config.py")
        self.assertEqual(code, 200)
        self.assertIn(b"<!doctype html>", body)


if __name__ == "__main__":
    unittest.main()
