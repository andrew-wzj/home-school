# Problem statement

## In one sentence

Plenty of university courses are now public, but a student studying alone gets the
**material** without the **structure around it**: someone who sets the pace, sets deadlines,
checks whether you actually understood, and notices when you are stuck. Home School tries to
supply that structure with an AI teacher that runs on your own computer.

## Who this is for

The first user is the author. The target user looks like this:

- Motivated to learn a real subject at university depth (to start: introductory computer science).
- Can't pay for a degree, or doesn't need the credential, only the knowledge.
- Has a computer, an internet connection, and is willing to pay a few dollars of API usage on their
  own Claude or OpenAI key.
- Studies alone, usually in the evening or between other commitments.

It is **not** built for schools, teachers managing a class, or anyone who needs a certificate.
There is no business model and no plan for one.

## What is already free, and what is not

Courses such as CMU 15-110 publish almost everything a registered student gets:

| A registered student gets | Public? |
|---|---|
| Lecture recordings | Yes (YouTube) |
| Slides, starter code, homework handouts | Yes (course website) |
| A schedule with fixed due dates | Yes, but only for the original semester |
| Autograder feedback (Gradescope) | **No** |
| Recitations, office hours, TAs | **No** |
| Someone who notices you fell behind | **No** |
| Quizzes and exams that force you to check understanding | Partly (some practice material) |
| Classmates studying the same thing this week | **No** |

So the content gap is small. The gap is in **supervision and feedback**. In practice, self-study
fails in a few predictable ways:

1. **No pace.** Without deadlines, "I'll watch the next lecture tomorrow" repeats until the course
   is abandoned. The original due dates belong to a semester that is already over.
2. **Passive watching feels like learning.** Watching a 45-minute lecture end to end is easy and
   leaves little behind. Nobody asks you a question before or after.
3. **Getting stuck silently.** One homework problem eats an evening. There is no TA to ask, no
   record that it happened, and no reason to come back to it later.
4. **No honest check of understanding.** Without an autograder or exam, it's easy to believe you
   understood "return vs. print" because the video made sense.
5. **Generic AI help is too helpful.** A general chatbot will happily write the homework for you, or
   tell you "Great job!" on a half-right answer. Both remove the learning.
6. **Long sessions and phones.** Studying alone at home means no fixed class length, no breaks, and
   a phone within reach.

## What Home School does about each

| Failure | What the app does |
|---|---|
| No pace | Rebuilds the course schedule from *your* start date (2 or 3 lectures a week). Every assignment gets a due date relative to its last lecture, the same gap as the original course. The Today page shows one thing to do now. |
| Passive watching | Lectures are cut into segments of roughly 5–25 minutes; only the current segment plays. A guiding question is shown **before** you watch and answered **after**. Key points stay hidden until you have watched. |
| Stuck silently | A per-question timer. After 15 minutes it says: log this as a stuck point and move on. Stuck points are kept, shown on Today with a Retry link, and passed to the AI tutor. |
| No honest check | Programming homework is judged by **tests**, not by the AI. Each concept in an assignment is quizzed from at least 2 angles; one wrong answer means "Retest". Written answers get a strict `PASS` / `NOT YET` with a follow-up question. |
| AI too helpful | Every prompt the app produces tells the model: hints only, no full solutions, no praise unless it names a concrete improvement. Encouragement appears only on the Today page and only when the data shows real progress ("Q4: 18 min two weeks ago, 9 min today"). |
| Long sessions, phone | Suggested session length (30 min to start, then based on your history), a 5-minute break every 25 minutes, and a Do Not Disturb reminder before each session. Supervision can be turned off; records are kept regardless. |

## Goals

1. **One answer to "what should I do today?"** on opening the app, with an estimated time.
2. **Active learning by default:** question before, answer after, strict check, every lecture.
3. **Honest feedback:** tests decide correctness; the AI explains and quizzes but does not grade code.
4. **A record of difficulty:** stuck points, retries, and time per question are kept and used.
5. **Runs locally, cheaply, and privately:** no account, no server, your own API key stored only on
   your computer, your study data in one SQLite file.
6. **Easy to add a course** that has public videos and materials: one JSON file per course,
   with tools to draft it from captions.
7. **Bilingual (English / Chinese)** from the start, because the first user studies in English but
   thinks in both.

## Non-goals (for now)

- Replacing the original course: videos, slides, and homework stay on the course's own sites and
  are linked, never copied or re-hosted.
- Publishing solutions. Course policies forbid it, so homework and tests stay in a git-ignored folder.
- Credentials, certificates, or proof of completion.
- Mobile apps or controlling the phone. A web page can only remind.
- Voice-over or dubbing of lectures (planned as a separate project).
- A hosted, multi-user service.

## Design principles

- **Supervision is a tool the student controls.** It can be switched off at any time; turning it off
  silences reminders but keeps records.
- **Strict over kind.** A wrong answer is "not passed", and the retest comes from a different angle.
  Praise without evidence is treated as noise.
- **Small steps.** One segment, one question, one 25-minute block. A day's plan should fit the time
  you actually have.
- **Bring your own model.** No vendor lock-in. Without a key, every AI step degrades to a prompt you
  can paste into any chat.
- **Plain, inspectable data.** Course data is JSON, records are SQLite, prompts are readable text.
- **Minimal, professional interface.** No gamification, no streak counters, no red alerts.
  The nearest due date is orange, the rest are grey.

## How we will know it works

There is one user so far, so these are personal signals rather than metrics:

- The author finishes Module 1 of CMU 15-110 (5 lectures, Check1, Hw1) on the planned schedule,
  or close to it.
- Each assignment's concepts reach "Passed" through the 2-angle quiz, not by self-assessment.
- Time on re-attempted problems goes down, as recorded by the question timer.
- The app gets opened on days without a deadline.

## Risks and constraints

- **Videos can disappear** or be blocked from embedding. The app falls back to a direct link, and
  caption text is backed up locally.
- **AI grading of free text is subjective** and may still be lenient despite the prompt. It needs
  spot-checking. Code is judged by tests for this reason.
- **AI-written tests can be wrong.** The tutor is asked to list cases to check by hand.
- **API cost** is not estimated yet. Each "Send to AI" is one request.
- **A web page can't take your phone away.**

See [ROADMAP.md](ROADMAP.md) for what is rough today and what is undecided.
