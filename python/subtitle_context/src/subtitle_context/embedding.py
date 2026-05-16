from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np

from model_gateway import embed_texts_for_capability as gateway_embed_texts_for_capability
from movieteller_config.schema import Settings

_EMBEDDING_BATCH_SIZE = 10


def _l2_normalize(vectors: np.ndarray) -> np.ndarray:
    if vectors.size == 0:
        return vectors.astype(np.float32, copy=False)
    arr = np.asarray(vectors, dtype=np.float32)
    norms = np.linalg.norm(arr, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return arr / norms


def embed_texts(
    texts: Sequence[str],
    *,
    settings: Settings,
    client_factory: Callable[..., Any] | None = None,
) -> np.ndarray:
    items = [str(text).strip() for text in texts if str(text).strip()]
    if not items:
        return np.zeros((0, 0), dtype=np.float32)
    rows: list[list[float]] = []
    for start in range(0, len(items), _EMBEDDING_BATCH_SIZE):
        batch = items[start : start + _EMBEDDING_BATCH_SIZE]
        result = gateway_embed_texts_for_capability(
            texts=batch,
            settings=settings,
            client_factory=client_factory,
        )
        rows.extend(list(row) for row in result.vectors)
    vectors = np.asarray(rows, dtype=np.float32)
    return _l2_normalize(vectors)
