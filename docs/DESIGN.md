# Product design

This document describes how the app behaves and why. For the code, see
[ARCHITECTURE.md](ARCHITECTURE.md). For the motivation, see [PROBLEM.md](PROBLEM.md).

## The study loop

```
          ┌──────────── Today ────────────┐
          │ "L5 · Function Definitions"   │
          │ 30 min · break every 25 · DND │
          │ 1 Prep  2 Watch  3 Quiz       │
          └──────────────┬────────────────┘
                         │ Start (Do Not Disturb reminder)
                         ▼
   ┌──────────────────── Lesson ─────────────────────┐
   │ guiding question → segment video → key points    │
   │ answer → Send to AI → PASS / NOT YET + follow-up │
   │ Stuck → logged        timer → break every 25 min │
   └──────────────┬──────────────────────────────────┘
                  │ Homework
                  ▼
   ┌────────────────── Assignment ───────────────────┐
   │ materials → local folder                         │
   │ tutor prompt → your own AI chat                  │
   │ question timer → 15 min → log stuck, skip        │
   │ tests decide right/wrong; mastery per concept    │
   └──────────────┬──────────────────────────────────┘
                  │ stuck points, attempts, mastery
                  ▼
          back to Today: Retry · progress note
```

## Course structure

```
Course
 └─ Module            has one guiding "module question"
     └─ Lecture       may have its own guiding question
         └─ Segment   YouTube id, start/end, slide pages, summary,
                      concepts, prerequisites, key points (en + zh)
 └─ Assignment        module, lectures, materials, concepts to quiz,
                      due rule (N days after lecture X)
```

The AI "digests" each lecture before you watch it: captions are downloaded (never the video),
split into segments that match slide sections, and each segment gets a summary, key concepts,
prerequisites, and key points. For CMU 15-110 Module 1 this was done by reading the transcripts;
`tools/digest.py` does it with your API key for new lectures.

## Pages

### Today

Only answers "what do I do now?".

- **Today card**: the next lecture with unwatched segments, the suggested session length, break
  rhythm, phone reminder, and three steps with minutes each:
  - Prep: read the guiding question and the slide pages for today's segments (5 min).
  - Watch: the segments that fit in the session (segment length × 1.2 for pausing and notes).
    At least one segment is always planned, even if it is longer than the session.
  - Quiz: answer the question and get it checked (5 min).
- **Due**: assignments sorted by date. The nearest unfinished one is orange, the others grey, finished
  ones green. Red is never used. An assignment counts as done when all its concepts are Passed.
- **This week**: lectures done / lectures scheduled this week.
- **Course**: every lecture with its planned date and progress.
- **Last stuck**: the most recent unresolved stuck point and a Retry link.
- **Progress note**: appears only when the records show a concrete improvement (see below).

### Lesson

Designed to fit one screen without scrolling.

- **Question card** above the video. Which question depends on the lecture:
  - the lecture has its own question → answer it after this lecture;
  - this is the module's last lecture → answer the module question;
  - otherwise → the module question is shown as context ("Answer after L5"), and the answer box asks
    for a recall: "explain the main ideas in your own words".
- **Video**: YouTube embed with `start` and `end`, so only the current segment plays. When it ends,
  the segment is marked watched automatically. If embedding fails, a direct link to the right second
  is shown. Lectures without a recording (CMU 15-110 L1) show the slides instead.
- **Segment list**: done / current / to do, with time range and slide pages.
- **Answer box** and **Send to AI** (see Grading). Drafts are saved as you type.
- **Key points**: hidden for segments you haven't watched.
- **Stuck** (opens a short form, minutes pre-filled from time on the segment) and **Homework**.
- **Timer** in the top bar: elapsed / planned minutes and time to the next break.

### Assignment

- **Materials**: links to the originals, and "Save to my folder", which downloads them into
  `workspace/<course>/<assignment>/`. Existing files are never overwritten.
- **Question timer**: type the question label (e.g. `Q3`), Start, then Done or Stuck. After the
  stuck threshold (15 min) a notice suggests logging it and moving on; "Keep going" snoozes it
  5 minutes. Done on a question that had an open stuck point resolves it.
- **Mastery**: each concept is Passed / Retest / Pending. For now the student fills these in from
  the tutor's verdict; every change is stored with a timestamp.
- **Tests** (programming assignments): runs `test_*.py` in the assignment folder with `unittest`,
  60-second timeout, and shows the output.
- **Stuck points**: the log for this assignment, with Resolved buttons.
- **AI prompt**: collapsible, with Copy. Paste it into a new chat with your own model.

### Settings

AI provider, model and key; lectures per week; start date; default session length; break interval
and length; stuck threshold; calendar export.

## Rules

### Supervision (Focus)

On by default. When off: no break overlay, no Do Not Disturb reminder, no stuck notice.
Sessions, answers, attempts, and stuck points are recorded either way.

### Breaks

Every `break_every` (25) minutes of session time, a full-screen break of `break_len` (5) minutes
pauses the video and counts down. It can be skipped. Break time doesn't count as study time.
If the tab is in the background, a system notification is sent (when permission was granted).

### Session length

No history yet → the default (30 minutes; this number is a guess). After 3 finished sessions of at
least 5 minutes → the median of the last 5, rounded to 5 minutes and kept between 20 and 90.
This is a placeholder; see [ROADMAP.md](ROADMAP.md).

### Stuck points

A question becomes a stuck point after `stuck_minutes` (15). The rule is "log it and skip": the
student moves on, and the stuck point is shown on Today and included in the tutor prompt. The brief
plans to lengthen the threshold gradually as the student advances; for now it's a setting.

### Grading a written answer

The app sends the question, the student's answer, and the lecture's key points (as a reference the
student hasn't seen) with this instruction:

- Judge real understanding. Vague, partly wrong, or memorized-sounding → `NOT YET`. When in doubt,
  `NOT YET`.
- No praise, no softening. Say what is right, what is missing, and stop.
- End with one follow-up question on the same idea from a different angle.

Without an API key, the same prompt is shown for copying into any chat.

### Homework tutoring

The app never accepts homework uploads. Instead it generates a prompt for the student's own model:

```
You are my homework tutor.
Course: CMU 15-110 · Hw1
My files: <local folder>

1. While I work: hints only, no full code.
2. When I say "done": read hw1.py, run the tests. Tests decide right or wrong;
   you only explain. If test_hw1.py does not exist yet, write it from the
   instructions (hw1-prog.pdf, hw1.pdf) first and list which cases I should
   check by hand. Do not put solutions in it.
3. Quiz me on: define vs. call; return vs. print; parameters.
4. 2+ angles per concept. Wrong = not passed; retest from a new angle.
5. Output: pass/fail per concept + my stuck points.

Stuck so far: Q3 (15 min).
No praise unless it names a concrete improvement.
```

Written assignments get "hints only, no answers" and "I will paste my answers" instead of tests.

### Encouragement

Encouragement is shown only on Today, never during grading, and only when it can point to a
specific improvement in the records. Two rules exist today:

1. The same question was attempted again, finished this time, and took at least 15% less time:
   *"HW1 · Q4: 18 min on Nov 11, 9 min on Nov 25."*
2. A concept was marked Retest and later Passed:
   *"return vs. print: retest on Nov 20, passed on Nov 24."*

If neither applies, nothing is shown.

### Schedule and due dates

Lectures are placed on fixed weekdays from the start date: 3 per week → Mon / Wed / Fri,
2 per week → Mon / Thu. Each assignment is due N days after its last lecture, where N is the gap in
the original course (CMU 15-110: Check1 is 4 days after L3, Hw1 3 days after L5). Due dates don't
move when you fall behind; the Today page always shows the next unfinished lecture.

## Interface

- English by default; one button switches everything to Chinese, and the choice is saved.
- Neutral palette (off-white background, white cards, one blue accent, orange for the nearest
  deadline, green for done). Inter and Noto Sans SC.
- No streaks, points, badges, or red warnings.
- Touch targets ≥ 44 px; real buttons and labels, keyboard focus visible.
