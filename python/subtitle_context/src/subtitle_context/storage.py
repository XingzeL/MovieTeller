from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from subtitle_context.types import SubtitleContextChunk


def write_chunks(path: str | Path, chunks: tuple[SubtitleContextChunk, ...]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:
        for chunk in chunks:
            f.write(
                json.dumps(
                    {
                        "chunkId": chunk.chunk_id,
                        "startSec": chunk.start_sec,
                        "endSec": chunk.end_sec,
                        "text": chunk.text,
                        "cueCount": chunk.cue_count,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )


def load_chunks(path: str | Path) -> tuple[SubtitleContextChunk, ...]:
    p = Path(path)
    out: list[SubtitleContextChunk] = []
    with p.open("r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            row = json.loads(line)
            out.append(
                SubtitleContextChunk(
                    chunk_id=str(row["chunkId"]),
                    start_sec=float(row["startSec"]),
                    end_sec=float(row["endSec"]),
                    text=str(row["text"]),
                    cue_count=int(row["cueCount"]),
                )
            )
    return tuple(out)


def write_embeddings(path: str | Path, embeddings: np.ndarray) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    np.save(p, embeddings)


def load_embeddings(path: str | Path) -> np.ndarray:
    return np.load(Path(path))
