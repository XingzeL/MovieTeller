from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SubtitleContextChunk:
    chunk_id: str
    start_sec: float
    end_sec: float
    text: str
    cue_count: int


@dataclass(frozen=True)
class RetrievedSubtitleContextChunk:
    chunk_id: str
    start_sec: float
    end_sec: float
    text: str
    cue_count: int
    score: float


@dataclass(frozen=True)
class SubtitleContextBuildResult:
    output_dir: str
    chunks_path: str
    embeddings_path: str
    chunk_count: int
    embedding_dim: int


@dataclass(frozen=True)
class SubtitleContextRetrievalResult:
    query_text: str
    segment_start_sec: float
    history_window_sec: float
    retrieved_chunks: tuple[RetrievedSubtitleContextChunk, ...]
