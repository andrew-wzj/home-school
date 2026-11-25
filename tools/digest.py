#!/usr/bin/env python3
"""Let your AI model draft segments for one lecture from its transcript.

    python3 tools/digest.py VIDEO_ID "topic A (p.4-7)" "topic B (p.8-15)" ...

Reads data/transcripts/VIDEO_ID.txt (from fetch_captions.py), asks the model
configured in Settings to find where each topic starts and ends, and to write
a summary, key concepts, prerequisites and key points per segment in English
and Chinese. Prints JSON segments to paste into courses/<id>/course.json.

The draft is a starting point: check the times against the video before you
rely on them. This costs one API call on your key.
"""
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from homeschool import ai  # noqa: E402

SYSTEM = """You split a recorded university lecture into study segments.
You get a transcript with [m:ss] timestamps and an ordered list of topics (with slide pages).
For each topic, find the second where the lecturer starts it. Segments are contiguous: each ends where the next starts; the first starts at 0; the last ends at the video's end.
Write for a self-taught student. Be concrete; no filler.
Return only a JSON array, no prose, where each item is:
{"pages": "...", "start": <int seconds>, "end": <int seconds>,
 "title": {"en": "...", "zh": "..."},
 "summary": {"en": "2-3 sentences", "zh": "..."},
 "concepts": ["short concept names, English"],
 "prereqs": ["concepts the student must already know"],
 "points": {"en": ["2-3 one-line key points"], "zh": ["..."]}}"""


def main():
    if len(sys.argv) < 3:
        sys.exit(__doc__)
    vid, topics = sys.argv[1], sys.argv[2:]
    path = os.path.join(ROOT, "data", "transcripts", vid + ".txt")
    with open(path, encoding="utf-8") as f:
        transcript = f.read()
    last = re.findall(r"^\[(\d+):(\d+)\]", transcript, re.M)
    approx_end = int(last[-1][0]) * 60 + int(last[-1][1]) + 60 if last else 0
    user = "Topics in order:\n%s\n\nVideo length: about %d seconds.\n\nTranscript:\n%s" % (
        "\n".join("%d. %s" % (i + 1, t) for i, t in enumerate(topics)), approx_end, transcript)
    reply = ai.ask(SYSTEM, user)
    m = re.search(r"\[.*\]", reply, re.S)
    if not m:
        sys.exit("Model did not return JSON:\n" + reply)
    segs = json.loads(m.group(0))
    print(json.dumps(segs, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except ai.AIError as e:
        sys.exit("AI error: %s" % e)
