from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

import numpy as np


@dataclass(frozen=True)
class MMRSelection:
    index: int
    relevance_score: float
    mmr_score: float
    redundancy_score: float


def _normalize_query(vector: np.ndarray) -> np.ndarray:
    arr = np.asarray(vector, dtype=np.float32).reshape(-1)
    norm = float(np.linalg.norm(arr))
    if norm == 0.0:
        return arr
    return arr / norm


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    arr = np.asarray(vectors, dtype=np.float32)
    if arr.ndim != 2:
        raise ValueError(f"candidate_vectors must be rank-2, got shape={arr.shape}")
    if arr.size == 0:
        return arr
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def mmr_select(
    *,
    query_vector: np.ndarray,
    candidate_vectors: np.ndarray,
    top_k: int,
    relevance_scores: Sequence[float] | np.ndarray | None = None,
    lambda_mult: float = 0.7,
) -> tuple[MMRSelection, ...]:
    """
    Select up to ``top_k`` candidates using Maximal Marginal Relevance.

    Candidates are ranked by a balance of:
    - query relevance
    - diversity against already selected items
    """
    k = max(0, int(top_k))
    normalized_candidates = _normalize_rows(candidate_vectors)
    if normalized_candidates.shape[0] == 0 or k == 0:
        return ()
    normalized_query = _normalize_query(query_vector)
    if normalized_query.shape[0] != normalized_candidates.shape[1]:
        raise ValueError(
            "query_vector dimension does not match candidate_vectors: "
            f"{normalized_query.shape[0]} != {normalized_candidates.shape[1]}"
        )
    lam = float(lambda_mult)
    if lam < 0.0 or lam > 1.0:
        raise ValueError(f"lambda_mult must be within [0, 1], got {lambda_mult}")
    if relevance_scores is None:
        relevance = normalized_candidates @ normalized_query
    else:
        relevance = np.asarray(relevance_scores, dtype=np.float32).reshape(-1)
    if relevance.shape[0] != normalized_candidates.shape[0]:
        raise ValueError(
            "relevance_scores length does not match candidate_vectors: "
            f"{relevance.shape[0]} != {normalized_candidates.shape[0]}"
        )
    similarity_matrix = normalized_candidates @ normalized_candidates.T
    selected_local: list[int] = []
    out: list[MMRSelection] = []
    remaining = set(range(normalized_candidates.shape[0]))
    limit = min(k, normalized_candidates.shape[0])

    while remaining and len(selected_local) < limit:
        best_idx: int | None = None
        best_mmr = float("-inf")
        best_relevance = float("-inf")
        best_redundancy = 0.0
        for idx in sorted(remaining):
            redundancy = (
                float(np.max(similarity_matrix[idx, selected_local]))
                if selected_local
                else 0.0
            )
            mmr_score = (lam * float(relevance[idx])) - ((1.0 - lam) * redundancy)
            if best_idx is None or mmr_score > best_mmr or (
                mmr_score == best_mmr and float(relevance[idx]) > best_relevance
            ):
                best_idx = idx
                best_mmr = mmr_score
                best_relevance = float(relevance[idx])
                best_redundancy = redundancy
        assert best_idx is not None
        selected_local.append(best_idx)
        remaining.remove(best_idx)
        out.append(
            MMRSelection(
                index=best_idx,
                relevance_score=best_relevance,
                mmr_score=best_mmr,
                redundancy_score=best_redundancy,
            )
        )
    return tuple(out)
