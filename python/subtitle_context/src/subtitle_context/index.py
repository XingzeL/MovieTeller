from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Callable, Sequence

import numpy as np

from movieteller_config import load_settings
from movieteller_config.schema import (
    SubtitleContextBuildOptions,
    SubtitleContextRetrieveOptions,
)
from rerank import mmr_select
from subtitle_extraction.parse_srt import parse_srt_text

from subtitle_context.chunking import chunk_subtitle_cues
from subtitle_context.embedding import embed_texts
from subtitle_context.storage import (
    load_chunks,
    load_embeddings,
    write_chunks,
    write_embeddings,
)
from subtitle_context.types import (
    RetrievedSubtitleContextChunk,
    SubtitleContextBuildResult,
    SubtitleContextRetrievalResult,
)


def subtitle_context_index_is_complete(index_dir: str | Path) -> bool:
    root = Path(index_dir)
    if not root.is_dir():
        return False
    return (root / "chunks.jsonl").is_file() and (root / "embeddings.npy").is_file()


def build_subtitle_context_index(
    *,
    srt_path: str,
    output_dir: str | None = None,
    options: SubtitleContextBuildOptions | None = None,
    settings: object | None = None,
    embedder: Callable[[Sequence[str]], np.ndarray] | None = None,
) -> SubtitleContextBuildResult:
    cfg = settings if settings is not None else load_settings()
    out_dir = Path(output_dir or (str(Path(srt_path).with_suffix("")) + ".subtitle_context"))
    resolved_options = (
        options
        if options is not None
        else cfg.subtitle_context_build_options()
    )

    cues = parse_srt_text(Path(srt_path).read_text(encoding="utf-8"))
    chunks = chunk_subtitle_cues(
        cues,
        cue_count=resolved_options.chunk_cue_count,
        stride=resolved_options.chunk_stride,
    )
    texts = [chunk.text for chunk in chunks]
    if embedder is not None:
        embeddings = np.asarray(embedder(texts), dtype=np.float32)
    else:
        embeddings = embed_texts(texts, settings=cfg)
    if chunks and embeddings.shape[0] != len(chunks):
        raise RuntimeError(
            f"embedding row count mismatch: chunks={len(chunks)} embeddings={embeddings.shape[0]}"
        )

    parent_dir = out_dir.parent
    parent_dir.mkdir(parents=True, exist_ok=True)
    temp_dir = Path(
        tempfile.mkdtemp(prefix=f"{out_dir.name}.tmp.", dir=str(parent_dir))
    )
    chunks_path = temp_dir / "chunks.jsonl"
    embeddings_path = temp_dir / "embeddings.npy"
    write_chunks(chunks_path, chunks)
    write_embeddings(embeddings_path, embeddings)
    embedding_model = str(cfg.default_model_for_capability("embedding"))
    build_config = {
        "chunkCueCount": resolved_options.chunk_cue_count,
        "chunkStride": resolved_options.chunk_stride,
        "embeddingProvider": str(cfg.default_provider()),
        "embeddingModel": embedding_model,
    }
    (temp_dir / "build_config.json").write_text(
        json.dumps(build_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    backup_dir: Path | None = None
    if out_dir.exists():
        if out_dir.is_dir():
            backup_dir = parent_dir / f"{out_dir.name}.bak"
            if backup_dir.exists():
                shutil.rmtree(backup_dir)
            out_dir.replace(backup_dir)
        else:
            raise RuntimeError(f"subtitle context output path is not a directory: {out_dir}")
    try:
        temp_dir.replace(out_dir)
    except Exception:
        if backup_dir is not None and backup_dir.exists() and not out_dir.exists():
            backup_dir.replace(out_dir)
        raise
    else:
        if backup_dir is not None and backup_dir.exists():
            shutil.rmtree(backup_dir)
    return SubtitleContextBuildResult(
        output_dir=str(out_dir),
        chunks_path=str(out_dir / "chunks.jsonl"),
        embeddings_path=str(out_dir / "embeddings.npy"),
        chunk_count=len(chunks),
        embedding_dim=(int(embeddings.shape[1]) if embeddings.ndim == 2 and embeddings.size else 0),
    )


def retrieve_past_subtitle_context(
    *,
    index_dir: str,
    query_text: str,
    segment_start_sec: float,
    history_window_sec: float | None = None,
    top_k: int | None = None,
    options: SubtitleContextRetrieveOptions | None = None,
    settings: object | None = None,
    embedder: Callable[[Sequence[str]], np.ndarray] | None = None,
) -> SubtitleContextRetrievalResult:
    cfg = settings if settings is not None else load_settings()
    resolved_options = (
        options
        if options is not None
        else cfg.subtitle_context_retrieve_options(
            history_window_sec=history_window_sec,
            top_k=top_k,
        )
    )
    query = str(query_text or "").strip()
    if not query:
        raise ValueError("query_text is empty")
    root = Path(index_dir)
    chunks = load_chunks(root / "chunks.jsonl")
    embeddings = load_embeddings(root / "embeddings.npy")
    if len(chunks) != embeddings.shape[0]:
        raise RuntimeError(
            f"subtitle context index mismatch: chunks={len(chunks)} embeddings={embeddings.shape[0]}"
        )
    window = resolved_options.history_window_sec
    k = resolved_options.top_k
    eligible: list[int] = []
    for idx, chunk in enumerate(chunks):
        if chunk.end_sec > segment_start_sec:
            continue
        if window >= 0 and (segment_start_sec - chunk.end_sec) > window:
            continue
        eligible.append(idx)
    if not eligible:
        return SubtitleContextRetrievalResult(
            query_text=query,
            segment_start_sec=float(segment_start_sec),
            history_window_sec=window,
            retrieved_chunks=(),
        )
    if embedder is not None:
        query_vec = np.asarray(embedder([query]), dtype=np.float32)
    else:
        query_vec = embed_texts([query], settings=cfg)
    if query_vec.shape[0] != 1:
        raise RuntimeError(f"query embedder returned unexpected shape: {query_vec.shape}")
    eligible_matrix = embeddings[eligible]
    scores = eligible_matrix @ query_vec[0]
    ranked = mmr_select(
        query_vector=query_vec[0],
        candidate_vectors=eligible_matrix,
        relevance_scores=scores,
        top_k=k,
    )
    retrieved = tuple(
        RetrievedSubtitleContextChunk(
            chunk_id=chunks[eligible[row.index]].chunk_id,
            start_sec=chunks[eligible[row.index]].start_sec,
            end_sec=chunks[eligible[row.index]].end_sec,
            text=chunks[eligible[row.index]].text,
            cue_count=chunks[eligible[row.index]].cue_count,
            score=float(row.relevance_score),
        )
        for row in ranked
    )
    return SubtitleContextRetrievalResult(
        query_text=query,
        segment_start_sec=float(segment_start_sec),
        history_window_sec=window,
        retrieved_chunks=retrieved,
    )
