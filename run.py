#!/usr/bin/env python3
"""Start Home School:  python3 run.py  [--port 8110] [--no-browser]"""
import argparse
import sys

if sys.version_info < (3, 9):
    sys.exit("Home School needs Python 3.9 or newer.")

from homeschool.server import serve

if __name__ == "__main__":
    p = argparse.ArgumentParser(description="Home School: a local, semi-supervised self-study app.")
    p.add_argument("--port", type=int, default=8110)
    p.add_argument("--no-browser", action="store_true")
    a = p.parse_args()
    serve(a.port, not a.no_browser)
