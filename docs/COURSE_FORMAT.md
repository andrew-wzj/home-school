# Adding a course

A course is a single file, `courses/<course-id>/course.json`. The reference example is
[`courses/cmu-15-110-s26/course.json`](../courses/cmu-15-110-s26/course.json).

## Requirements for a course

- Lecture recordings on YouTube that allow embedding.
- English captions (auto-generated is fine; uploaded is better).
- Public slides and assignment handouts.

## Schema

Every user-facing text is an object with `en` and `zh`.

```jsonc
{
  "id": "cmu-15-110-s26",            // folder name
  "code": "15-110",
  "title": {"en": "...", "zh": "..."},
  "school": "Carnegie Mellon University",
  "term": "Spring 2026",
  "site": "https://www.cs.cmu.edu/~15110-s26/",   // relative URLs below resolve against this
  "channel": "https://www.youtube.com/@CMULearn",
  "notes": "free text for maintainers",

  "modules": [{
    "id": "m1",
    "title": {"en": "...", "zh": "..."},
    "lectures": ["L1", "L2", "L3", "L4", "L5"],
    "question": {"en": "...", "zh": "..."},       // guiding question for the module
    "answer_after": "L5"                         // lecture after which it is answered
  }],

  "lectures": [{
    "id": "L2", "n": 2, "date": "2026-01-14",    // date in the original course (reference only)
    "title": {"en": "...", "zh": "..."},
    "slides": "slides/week1-2-programming.pdf",
    "code": "slides/week1-2-code.py",            // optional
    "video": {"youtube": "oPSMMckx3eY", "duration": 2715, "label": "YouTube: Lecture 1"},
                                                 // null when there is no recording
    "question": {"en": "...", "zh": "..."},      // optional, lecture-level guiding question
    "segments": [{
      "id": "L2-1",
      "pages": "4–7",                            // slide pages; "all" for slides-only lectures
      "start": 0, "end": 365,                    // seconds; null for slides-only
      "read_minutes": 20,                        // only for slides-only segments
      "title":    {"en": "...", "zh": "..."},
      "summary":  {"en": "2–3 sentences", "zh": "..."},
      "concepts": ["program vs. algorithm"],     // short names, English
      "prereqs":  ["algorithm"],                 // concepts needed first
      "points":   {"en": ["one-line key point"], "zh": ["..."]}
    }]
  }],

  "assignments": [{
    "id": "hw1", "name": "Hw1",
    "title": {"en": "...", "zh": "..."},
    "module": "m1",
    "kind": "programming",                       // or "written"
    "lectures": ["L1", "L2", "L3", "L4", "L5"],
    "due_after": {"lecture": "L5", "days": 3},   // due N days after that lecture's planned date
    "materials": [
      {"label": "hw1-prog.pdf", "url": "hw/hw1-prog.pdf"},
      {"label": "hw1.py", "url": "hw/hw1.py", "starter": true}  // starter → tests are test_hw1.py
    ],
    "concepts": [{"en": "define vs. call", "zh": "定义 vs 调用"}]  // quizzed 2+ angles each
  }]
}
```

### Rules the tests check

- Segments of a lecture with video are contiguous: the first starts at 0, each ends where the next
  starts, and the last ends at or before `duration`.
- Every segment has `title`, `summary`, and `points` in both languages.
- Material URLs resolve to the course site.

### Choosing the guiding questions

Keep them few and pointed. Sometimes one per lecture, sometimes one module question shared by
2–5 lectures. A good question can't be answered by repeating a definition; it asks *why* or asks
to tell two things apart ("define vs. call", "return vs. print"). It's shown before watching and
answered after.

### Due-date gaps

Use the gap from the original syllabus. CMU 15-110 Hw1 was due Monday after the Friday lecture
(3 days); Check1 was due Tuesday after Friday (4 days).

## Workflow for a new lecture

1. **Find the video IDs.** With yt-dlp:
   ```sh
   .bin/yt-dlp --flat-playlist --print "%(id)s|%(title)s" "https://www.youtube.com/@CHANNEL/videos"
   ```
   Check the numbering: CMU's YouTube "Lecture 1" for 15-110 S26 is the course's second lecture,
   because the first wasn't recorded.

2. **Fetch captions** (text only):
   ```sh
   python3 tools/fetch_captions.py VIDEO_ID
   ```
   Writes `data/transcripts/VIDEO_ID.<lang>.vtt` and a compact `VIDEO_ID.txt` (`[m:ss] text`, about
   45 s per line). Uploaded captions are preferred over auto-generated ones. yt-dlp must be on your
   PATH or at `.bin/yt-dlp` (on macOS the standalone binary `yt-dlp_macos` from the yt-dlp releases
   page works without Python packages).

3. **Draft segments** with your configured model:
   ```sh
   python3 tools/digest.py VIDEO_ID "Python and the IDE (p.4-7)" "Data types (p.8-15)" ...
   ```
   Take the topic list from the slide deck's section headings. The output is a JSON array of
   segments; paste it into the lecture.

4. **Check the times.** Open the lecture in the app and jump between segments. Boundaries should
   fall where the lecturer changes topic, not mid-sentence. Adjust by hand.

5. **Write the guiding question** and add the assignment(s).

6. **Run the tests:** `python3 -m unittest discover -s tests`.

## Switching courses

`settings.course` holds the active course id. There's no course picker in the UI yet; set it with
```sh
curl -X POST -H "X-Home-School: 1" -H "Content-Type: application/json" \
  -d '{"course": "your-course-id"}' http://127.0.0.1:8110/api/settings
```
A picker is on the [roadmap](ROADMAP.md).

## Copyright

Course files in this repository contain only links, timestamps, and our own summaries and
questions. Don't commit videos, slides, transcripts, homework handouts, or solutions.
