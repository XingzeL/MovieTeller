"""CLI: ``python -m movieteller_logging <workflow.jsonl>`` → overall progress JSON."""

from __future__ import annotations

import json
import sys

from movieteller_logging.overall_progress import overall_progress
from movieteller_logging.progress import progress_from_jsonl


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 1:
        print(
            "usage: python -m movieteller_logging <path/to/workflow.jsonl>",
            file=sys.stderr,
        )
        return 2
    job = progress_from_jsonl(args[0])
    print(json.dumps(overall_progress(job), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
