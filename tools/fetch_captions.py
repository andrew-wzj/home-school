#!/usr/bin/env python3
"""Download caption text (never the video) and write a compact transcript.

    python3 tools/fetch_captions.py VIDEO_ID [VIDEO_ID ...]

Needs yt-dlp on PATH or at .bin/yt-dlp (macOS standalone build:
https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp_macos).
Output goes to data/transcripts/ (git-ignored):
  <id>.<lang>.vtt   raw captions
  <id>.txt          "[m:ss] text" lines, ~45 s per line, for reading or digest.py
"""
import glob
import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from homeschool.transcript import compact, parse_vtt  # noqa: E402

OUT = os.path.join(ROOT, "data", "transcripts")


def ytdlp():
    local = os.path.join(ROOT, ".bin", "yt-dlp")
    return local if os.path.exists(local) else shutil.which("yt-dlp")


def best_vtt(vid):
    files = glob.glob(os.path.join(OUT, vid + ".*.vtt"))
    # Prefer uploaded captions (en-<code>) over auto-generated (en), and never translations.
    manual = [f for f in files if os.path.basename(f).split(".")[1].startswith("en-")]
    auto = [f for f in files if os.path.basename(f).split(".")[1] in ("en", "en-orig")]
    return (manual or auto or [None])[0]


def fetch(vid, tool):
    os.makedirs(OUT, exist_ok=True)
    cmd = [tool, "--skip-download", "--write-subs", "--write-auto-subs", "--sub-langs", "en,en-orig,en-[a-zA-Z0-9]*",
           "--sub-format", "vtt", "-o", os.path.join(OUT, "%(id)s.%(ext)s"), "--", vid]
    subprocess.run(cmd, check=False)
    path = best_vtt(vid)
    if not path:
        print("  no English captions for", vid)
        return
    with open(path, encoding="utf-8") as f:
        text = compact(parse_vtt(f.read()), 45)
    with open(os.path.join(OUT, vid + ".txt"), "w", encoding="utf-8") as f:
        f.write(text)
    print("  %s -> data/transcripts/%s.txt (%d words)" % (os.path.basename(path), vid, len(text.split())))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    tool = ytdlp()
    if not tool:
        sys.exit("yt-dlp not found. Put it on PATH or at .bin/yt-dlp.")
    for v in sys.argv[1:]:
        fetch(v, tool)
