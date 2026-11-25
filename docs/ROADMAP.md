# Roadmap

Version 0.1 is a working prototype: the idea is complete end to end, but many parts are simple on
purpose. This page lists what is rough, what is undecided, and what comes next.

## Known rough edges in 0.1

- **Mastery is filled in by hand.** The tutor runs in your own chat, so its pass/fail verdict has to
  be copied back by clicking Passed / Retest. Easy to skip, easy to be generous with yourself.
- **No per-lecture quiz bank.** The Quiz step is one guiding question (or a recall prompt). There
  are no multiple short questions per segment yet.
- **One course at a time**, switched via the API. No course picker, no "add course" screen.
- **Only Module 1 of CMU 15-110 is filled in** (L1–L5, Check1, Hw1). The rest of the semester needs
  segment times, summaries, and questions.
- **Segment times were aligned by reading transcripts**, not by watching. Boundaries may be off by
  a few seconds to a minute.
- **The timer lives in the browser** (localStorage). Closing the tab mid-session keeps the timer
  running until you come back and press Finish; a forgotten session inflates your history.
- **Breaks are time-based only.** The video pauses, but nothing checks you actually left the desk.
- **The suggested session length is a placeholder** (default 30 min, then a median). It ignores time
  of day, difficulty, and how the last session went.
- **Progress notes** only cover two patterns (faster retry, retest → passed).
- **Tests depend on the AI** writing `test_<starter>.py` correctly. The app runs them but can't tell
  whether they test the right things.
- **Chinese captions** are requested from YouTube's player (`cc_lang_pref=zh-Hans`). Whether
  auto-translation reliably turns on inside an embed has not been verified.
- **Calendar** is a one-time `.ics` export. Changing the pace or start date needs a re-import.
- **The default OpenAI model name** may be outdated; set it in Settings.
- **No accessibility audit** beyond basics (labels, focus, contrast, touch targets).

## Open questions from the brief

| Question | Current answer | To decide |
|---|---|---|
| Pace: 3 or 2 lectures a week? | Setting, default 3 (same as the original course) | Try both for a month |
| How should the AI suggest session length? | Median of recent sessions | Use completion rate, answer verdicts, time of day? |
| When does the student need encouragement? | Not detected | Candidate signals: 3 NOT YETs in a row; 2+ stuck points in one session; 2 planned days skipped in a row. All unverified. |
| How to split modules? | Written by hand | AI proposes from the syllabus, student confirms |
| Google Calendar sync and phone push | `.ics` export | Google Calendar API, or a calendar subscription URL |
| API cost | Not measured | Log tokens per request and show a monthly total |
| How much to trust AI grading? | Strict prompt + tests for code | Spot-check rate, second-opinion grading |

## Next

Roughly in order:

1. **Bring tutor results back automatically.** Ask the tutor to end with a fixed block
   (`MASTERY: define vs. call = PASS ...`) and add a "Paste result" box that fills Mastery.
2. **Short quizzes per segment**, generated during digestion, 2 angles per concept, stored in the
   course file.
3. **Complete CMU 15-110** with the digest tools, and review segment boundaries by watching.
4. **Course picker** and an "add course" flow that runs fetch → digest → review in the UI.
5. **Session robustness:** auto-pause when the tab is hidden for long, end abandoned sessions.
6. **Encouragement and slump signals** once there is enough data to test them.
7. **Cost tracking** per request and per month.

## Later

- **Side-panel tutor:** a chat inside the app that can read the local homework folder and run tests
  directly, instead of copy-pasting a prompt into another chat.
- **Spaced review:** bring back failed concepts and old stuck points after a few days.
- **Local model option** for summaries and simple checks.
- **Voice-over / dubbing** of lectures, as a separate project.
- **More courses:** any course with embeddable recordings and public materials.
