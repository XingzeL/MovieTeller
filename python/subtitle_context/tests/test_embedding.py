from types import SimpleNamespace

import numpy as np

from movieteller_config.schema import settings_from_dict

from subtitle_context.embedding import embed_texts


def test_embed_texts_batches_requests_for_provider_limits():
    calls: list[list[str]] = []

    class FakeEmbeddingsApi:
        def create(self, *, model, input):
            assert model == "text-embedding-v4"
            calls.append(list(input))
            return SimpleNamespace(
                data=[
                    SimpleNamespace(embedding=[float(idx + 1), 0.0])
                    for idx, _ in enumerate(input)
                ]
            )

    class FakeClient:
        def __init__(self):
            self.embeddings = FakeEmbeddingsApi()

    settings = settings_from_dict(
        {
            "narration_image_model": "x",
            "subtitle_context_embedding_provider": "dashscope",
            "subtitle_context_embedding_model": "text-embedding-v4",
            "api_keys": {"dashscope": "dummy"},
            "api_base_urls": {"dashscope": "https://example.com/v1"},
        }
    )

    vectors = embed_texts(
        [f"text-{idx}" for idx in range(12)],
        settings=settings,
        client_factory=lambda api_key, base_url: FakeClient(),
    )

    assert calls == [
        [f"text-{idx}" for idx in range(10)],
        [f"text-{idx}" for idx in range(10, 12)],
    ]
    assert vectors.shape == (12, 2)
    assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0)
