# Contributing

This is an early, personal project. Issues and pull requests are welcome, especially:

- **Course data:** segments, summaries, and guiding questions for more CMU 15-110 lectures, or a new
  course. See [docs/COURSE_FORMAT.md](docs/COURSE_FORMAT.md).
- **Checking segment times** by actually watching the lectures.
- Items on the [roadmap](docs/ROADMAP.md).

## Ground rules

- **No solutions.** Never commit homework answers, filled-in starter files, or tests that reveal
  answers. Course policies forbid publishing them. `workspace/` is git-ignored for this reason.
- **No copied course material.** Link to videos, slides, and handouts; don't add them to the repo.
  Captions and transcripts stay in the git-ignored `data/` folder.
- **No secrets.** `config.local.json` holds API keys and is git-ignored. Double-check before
  committing.
- **Both languages.** Every new UI string goes into `web/i18n.js` in English and Chinese; every
  course text has `en` and `zh`.
- **Standard library only** on the Python side, and no build step on the front end, unless there is
  a strong reason. Keeping `python3 run.py` as the whole install is a feature.
- **Keep the tone of the product:** strict feedback, no empty praise, no gamification.

## Development

```sh
python3 run.py --no-browser          # http://127.0.0.1:8110/
python3 -m unittest discover -s tests -v
```

Set `HOMESCHOOL_LOG=1` to print requests. `HOMESCHOOL_DATA`, `HOMESCHOOL_WORKSPACE` and
`HOMESCHOOL_CONFIG` move the data folder, workspace, and key file (the tests use these).

Please run the tests before opening a pull request, and describe how you checked UI changes.
