"""Parse YouTube .vtt captions into plain, timestamped text.

Auto-generated captions repeat each line as it "rolls" up the screen; we
collapse that so a 45-minute lecture becomes a few hundred compact lines.
"""
import html
import re

_TS = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})")
_TAG = re.compile(r"<[^>]+>")


def _secs(ts):
    m = _TS.match(ts.strip())
    if not m:
        raise ValueError("bad timestamp: %r" % ts)
    h, mi, s, ms = m.groups()
    return int(h or 0) * 3600 + int(mi) * 60 + int(s) + int(ms) / 1000.0


def parse_vtt(text):
    """Return a list of (start_seconds, text) cues, de-duplicated."""
    cues = []
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n"))
    for block in blocks:
        lines = [l for l in block.split("\n") if l.strip()]
        arrow = next((i for i, l in enumerate(lines) if "-->" in l), None)
        if arrow is None:
            continue
        start = _secs(lines[arrow].split("-->")[0])
        body = " ".join(html.unescape(_TAG.sub("", l)).strip() for l in lines[arrow + 1:])
        body = re.sub(r"\s+", " ", body).strip()
        if body:
            cues.append((start, body))

    # Collapse rolling duplicates: keep only the words a cue adds.
    out = []
    prev = ""
    for start, body in cues:
        if body == prev or prev.endswith(body):
            continue
        if body.startswith(prev) and prev:
            new = body[len(prev):].strip()
        else:
            new = body
            # Auto captions often repeat the previous line as the first line.
            for k in range(min(len(prev), len(body)), 0, -1):
                if prev.endswith(body[:k]) and k > 10:
                    new = body[k:].strip()
                    break
        prev = body
        if new:
            out.append((start, new))
    return out


def chunk(cues, seconds=30):
    """Group cues into blocks of roughly `seconds` each: [(start, text)]."""
    out = []
    for start, text in cues:
        if out and start - out[-1][0] < seconds:
            out[-1] = (out[-1][0], out[-1][1] + " " + text)
        else:
            out.append((start, text))
    return out


def fmt(sec):
    sec = int(sec)
    return "%d:%02d" % (sec // 60, sec % 60)


def compact(cues, seconds=30):
    return "\n".join("[%s] %s" % (fmt(s), t) for s, t in chunk(cues, seconds))
