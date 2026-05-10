#!/usr/bin/env python3
"""Smoke: run subtitle_extraction CLI against a local media file (requires videocaptioner on PATH).

  source .venv/bin/activate
  PYTHONPATH=python/movieteller_config/src:python/subtitle_extraction/src \\
    python python/manual_tests/subtitle_extraction_cli_smoke.py /path/to/video.mp4
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser()
    ap.add_argument("video", help="Path to video or audio")
    args = ap.parse_args()
    env = dict(**__import__("os").environ)
    sep = __import__("os").pathsep
    pp = [
        str(root / "python/movieteller_config/src"),
        str(root / "python/subtitle_extraction/src"),
    ]
    env["PYTHONPATH"] = sep.join(pp + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
    cmd = [
        sys.executable,
        "-m",
        "subtitle_extraction",
        "--video",
        args.video,
        "--json",
    ]
    r = subprocess.run(cmd, cwd=str(root), env=env)
    return r.returncode


if __name__ == "__main__":
    raise SystemExit(main())
