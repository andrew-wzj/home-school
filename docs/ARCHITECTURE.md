# Architecture

Home School is a small local web app: a Python standard-library HTTP server with SQLite, and a
front end in plain HTML/CSS/JavaScript with no build step.

```
browser (127.0.0.1:8110)
  │  web/index.html, app.js, i18n.js, style.css
  │  YouTube IFrame API (only segment start/end)
  ▼
homeschool/server.py ── JSON API ──┬─ planner.py   schedule, today plan, session length, progress notes
                                   ├─ db.py        SQLite: data/homeschool.db
                                   ├─ prompts.py   grading prompt, homework tutor prompt
                                   ├─ ai.py        HTTPS to Anthropic or OpenAI (your key)
                                   └─ workspace.py materials download, test runner, .ics export
courses/<id>/course.json  (read on each request)
config.local.json         (API key, git-ignored, mode 600)
```

## Why this stack

- **Zero install.** `python3 run.py` works on the Python 3.9 that ships with macOS and on any newer
  Python. No pip, no Node, no build.
- **One user, one machine.** A threaded `http.server` and one SQLite file are enough.
- **No SDKs.** The official Anthropic SDK needs Python 3.10+. Both providers are called with
  `urllib` over HTTPS (about 60 lines in `ai.py`), which also keeps the two providers symmetrical.
- **Readable data.** Courses are JSON files you can edit by hand; prompts are plain strings.

If the project grows (a side-panel tutor, multiple courses at once, sync), the obvious next step is
a proper framework. It hasn't been needed yet.

## Files

| Path | Role |
|---|---|
| `run.py` | Entry point. `--port`, `--no-browser`. |
| `homeschool/server.py` | Routing, request checks, `App` (state assembly and actions). |
| `homeschool/planner.py` | Course loading, schedule, due dates, suggested length, today's plan, answer targets, progress notes. Pure functions, unit-tested. |
| `homeschool/db.py` | Schema and queries. |
| `homeschool/prompts.py` | Grader prompt and verdict parsing; homework tutor prompt in en/zh. |
| `homeschool/ai.py` | `ask(system, user)` for the configured provider. |
| `homeschool/workspace.py` | Per-assignment folders, safe downloads, `unittest` runner, calendar file. |
| `homeschool/transcript.py` | VTT caption parsing, de-duplicating rolling auto-captions, compact `[m:ss]` text. |
| `homeschool/config.py` | Paths (overridable by env) and the local key file. |
| `web/app.js` | All pages, hash router, session timer, breaks, question timer. |
| `web/i18n.js` | Every UI string in English and Chinese. |
| `tools/fetch_captions.py` | Download caption text with yt-dlp and write a compact transcript. |
| `tools/digest.py` | Ask your model to draft segments for one lecture from its transcript. |
| `tests/test_core.py` | Unit and HTTP tests. |

## Data model

SQLite file `data/homeschool.db`:

| Table | Columns | Notes |
|---|---|---|
| `settings` | key, value (JSON) | lang, focus, course, pace, start_date, session_default, break_every, break_len, stuck_minutes |
| `segment_progress` | course_id, segment_id, watched_at | one row per watched segment |
| `sessions` | id, course_id, lecture_id, planned_min, started_at, ended_at, actual_min, breaks | feeds the suggested length |
| `answers` | id, course_id, ref, question, text, verdict, feedback, created_at | ref = lecture id, module id, or `<lecture>-recall` |
| `mastery` | id, course_id, assignment_id, concept, status, note, created_at | append-only history; latest row per concept is current |
| `stuck` | id, course_id, ref, question, minutes, description, created_at, resolved_at | ref = lecture or assignment id |
| `attempts` | id, course_id, assignment_id, question, minutes, outcome, created_at | from the question timer; outcome `done` or `stuck` |

Course content is not stored in the database; it is read from `courses/<id>/course.json`.
See [COURSE_FORMAT.md](COURSE_FORMAT.md).

## HTTP API

All responses are JSON unless noted. POST bodies are JSON.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/state` | Everything the Today and Lesson pages need: settings, AI status (never the key), course with answer targets, watched segments, schedule, due list, suggested length, today's plan, week progress, last stuck point, progress note. |
| GET | `/api/assignment/<id>` | Assignment, due date, current mastery, stuck points, recent attempts, local folder and files, tutor prompt in en and zh. |
| GET | `/api/answers?ref=<ref>` | Past answers for a question. |
| GET | `/api/calendar.ics` | Calendar file (lecture days, due dates with a 1-day reminder). |
| POST | `/api/settings` | Update settings (only known keys). |
| POST | `/api/config` | Set provider, model, key; or `clear_key`. Returns the public view. |
| POST | `/api/segment` | `{segment_id, watched}` |
| POST | `/api/session/start` | `{lecture_id, planned}` → `{id}` |
| POST | `/api/session/end` | `{id, actual_min, breaks}` |
| POST | `/api/answer` | `{ref, question, text, points}` → `{sent, verdict, feedback}` or, without a key, `{sent: false, copy}` |
| POST | `/api/stuck`, `/api/stuck/resolve` | Log or resolve a stuck point. |
| POST | `/api/attempt` | `{assignment_id, question, minutes, outcome}` |
| POST | `/api/mastery` | `{assignment_id, concept, status}` |
| POST | `/api/assignment/<id>/download` | Save materials to the local folder. |
| POST | `/api/assignment/<id>/test` | Run `test_*.py` in that folder. |

## Security

The server holds an API key and can run Python tests on your machine, so it is locked down even
though it is local:

- Binds to `127.0.0.1` only.
- Rejects any request whose `Host` header is not `127.0.0.1:<port>` or `localhost:<port>`, which
  blocks DNS-rebinding attacks from web pages.
- Every POST must carry the header `X-Home-School: 1`. A page on another site cannot add a custom
  header without a CORS preflight, which this server never approves, so it cannot trigger actions.
- Static files are served only from `web/`; path traversal falls back to `index.html`.
- The key is written to `config.local.json` with mode 600 and never returned to the browser
  (only the last 4 characters as a hint).
- Downloads only accept the course site's host and simple file names, and never overwrite.
- Tests run with a 60-second timeout in the assignment folder. They are your own files.

## AI calls

- **Claude:** `POST https://api.anthropic.com/v1/messages`, `anthropic-version: 2026-10-21`,
  default model `claude-opus-5-5`. For models that support it, server-side refusal fallback is
  enabled (`fallbacks: "default"`); a `refusal` stop reason is reported as an error.
- **OpenAI:** `POST https://api.openai.com/v1/chat/completions`. The default model name in
  Settings may need updating.
- One request per "Send to AI"; one per `tools/digest.py` run. Nothing else calls a model.

The homework tutor deliberately runs in the student's own chat, not inside the app. That chat can
read local files and run tests if the student uses a tool that allows it (for example a coding
agent pointed at the workspace folder).

### Local models

Learning, coding, and API calls need only an ordinary computer. Local models are possible later
but are clearly weaker at explaining and grading: a 16 GB Apple-silicon Mac runs 7–8B models,
32 GB runs about 14B, and 30B-class models only with 4-bit quantisation. For the teacher role a
cloud model is recommended.

## Testing

```sh
python3 -m unittest discover -s tests -v
```

Covers caption parsing, course data integrity (segments contiguous and inside the video, every
text in both languages, absolute material URLs), scheduling, session length, today's plan, answer
targets, progress notes, prompts, the test runner, the calendar file, and the HTTP layer
(state flow, required header, host check, static path traversal). Tests use a temporary data
directory and an in-memory database.
