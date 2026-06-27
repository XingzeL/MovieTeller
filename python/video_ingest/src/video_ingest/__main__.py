from __future__ import annotations

import argparse
import json
import sys

from video_ingest.router import download_video, parse_video


def main() -> int:
    ap = argparse.ArgumentParser(description="MovieTeller remote video ingest")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_parse = sub.add_parser("parse")
    p_parse.add_argument("--url", required=True)
    p_parse.add_argument("--json", action="store_true")

    p_download = sub.add_parser("download")
    p_download.add_argument("--url", required=True)
    p_download.add_argument("--output-dir", required=True)
    p_download.add_argument("--max-height", type=int, default=720)
    p_download.add_argument("--json", action="store_true")

    args = ap.parse_args()

    try:
        if args.cmd == "parse":
            payload = parse_video(args.url)
        else:
            payload = download_video(
                args.url,
                args.output_dir,
                max_height=args.max_height,
            )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
