from __future__ import annotations

import argparse
import json
import sys

from subtitle_context.index import (
    build_subtitle_context_index,
    retrieve_past_subtitle_context,
)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        prog="python -m subtitle_context",
        description="Build and query a local subtitle semantic context index.",
    )
    sub = ap.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="Build subtitle context index")
    build.add_argument("--srt", required=True, help="Extracted subtitle .srt path")
    build.add_argument("--output-dir", default=None, help="Output index directory")
    build.add_argument("--json", action="store_true", help="Print JSON payload")

    retrieve = sub.add_parser("retrieve", help="Retrieve historical subtitle context")
    retrieve.add_argument("--index-dir", required=True, help="Index directory path")
    retrieve.add_argument("--query", required=True, help="Query text")
    retrieve.add_argument(
        "--segment-start-sec",
        required=True,
        type=float,
        help="Current no-subtitle segment start time in seconds",
    )
    retrieve.add_argument("--history-window-sec", type=float, default=None)
    retrieve.add_argument("--top-k", type=int, default=None)
    retrieve.add_argument("--json", action="store_true", help="Print JSON payload")

    args = ap.parse_args(argv)

    try:
        if args.command == "build":
            result = build_subtitle_context_index(
                srt_path=args.srt,
                output_dir=args.output_dir,
            )
            payload = {
                "outputDir": result.output_dir,
                "chunksPath": result.chunks_path,
                "embeddingsPath": result.embeddings_path,
                "chunkCount": result.chunk_count,
                "embeddingDim": result.embedding_dim,
            }
        else:
            result = retrieve_past_subtitle_context(
                index_dir=args.index_dir,
                query_text=args.query,
                segment_start_sec=args.segment_start_sec,
                history_window_sec=args.history_window_sec,
                top_k=args.top_k,
            )
            payload = {
                "queryText": result.query_text,
                "segmentStartSec": result.segment_start_sec,
                "historyWindowSec": result.history_window_sec,
                "chunks": [
                    {
                        "chunkId": chunk.chunk_id,
                        "startSec": chunk.start_sec,
                        "endSec": chunk.end_sec,
                        "text": chunk.text,
                        "cueCount": chunk.cue_count,
                        "score": chunk.score,
                    }
                    for chunk in result.retrieved_chunks
                ],
            }
    except Exception as exc:
        msg = str(exc) or exc.__class__.__name__
        if getattr(args, "json", False):
            print(json.dumps({"error": msg}, ensure_ascii=False), file=sys.stdout)
        else:
            print(msg, file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        if args.command == "build":
            print(payload["outputDir"])
        else:
            for row in payload["chunks"]:
                print(
                    f"{row['startSec']:.3f}-{row['endSec']:.3f} "
                    f"score={row['score']:.4f} {row['text']}"
                )
    return 0
