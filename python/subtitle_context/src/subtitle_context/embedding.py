from __future__ import annotations

from typing import Any, Callable, Sequence

import numpy as np

from movieteller_config.schema import Settings

_EMBEDDING_BATCH_SIZE = 10


def _openai_sdk_client_factory(api_key: str, base_url: str | None) -> Any:
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


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
    provider_slug: str | None = None,
    model: str | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> np.ndarray:
    items = [str(text).strip() for text in texts if str(text).strip()]
    if not items:
        return np.zeros((0, 0), dtype=np.float32)
    slug = (provider_slug or settings.subtitle_context_provider()).strip().lower() or "openai"
    resolved_model = str(model or settings.require_subtitle_context_embedding_model()).strip()
    if not resolved_model:
        raise ValueError("subtitle context embedding model is empty")
    api_key = settings.require_api_key(slug)
    base_url = settings.get_api_base_url(slug)
    if slug == "openai" and not base_url:
        base_url = settings.openai_base_url
    factory = client_factory or _openai_sdk_client_factory
    client = factory(api_key, base_url)
    rows: list[list[float]] = []
    for start in range(0, len(items), _EMBEDDING_BATCH_SIZE):
        batch = items[start : start + _EMBEDDING_BATCH_SIZE]
        resp = client.embeddings.create(model=resolved_model, input=batch)
        rows.extend(row.embedding for row in resp.data)
    vectors = np.asarray(rows, dtype=np.float32)
    return _l2_normalize(vectors)
