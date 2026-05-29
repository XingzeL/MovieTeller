from __future__ import annotations

from types import SimpleNamespace

import pytest
from movieteller_config.schema import settings_from_dict

from model_gateway.errors import GatewayProviderError
from model_gateway.facade import (
    _capability_max_attempts,
    _embed_texts,
    _synthesize_speech,
    _with_capability_timeout,
)
from model_gateway.types import EmbeddingRequest, SpeechRequest


def test_with_capability_timeout_applies_settings_when_request_unset() -> None:
    settings = settings_from_dict(
        {"capability_timeouts": {"embedding": 42.5, "tts": 99}}
    )
    embed_req = EmbeddingRequest(provider="openai", model="m", texts=["a"])
    speech_req = SpeechRequest(provider="p", voice="v", text="hi")

    embed_out = _with_capability_timeout(embed_req, settings, "embedding")
    speech_out = _with_capability_timeout(speech_req, settings, "tts")

    assert embed_out.timeout_sec == 42.5
    assert speech_out.timeout_sec == 99


def test_with_capability_timeout_keeps_explicit_request_timeout() -> None:
    settings = settings_from_dict({"capability_timeouts": {"embedding": 60}})
    req = EmbeddingRequest(
        provider="openai", model="m", texts=["a"], timeout_sec=10
    )
    out = _with_capability_timeout(req, settings, "embedding")
    assert out.timeout_sec == 10


def test_capability_max_attempts_reads_retries_map() -> None:
    settings = settings_from_dict(
        {"capability_retries": {"embedding": 4, "tts": 5}}
    )
    assert _capability_max_attempts(settings, "embedding") == 4
    assert _capability_max_attempts(settings, "tts") == 5


def test_facade_embed_passes_timeout_to_openai_client() -> None:
    captured: dict = {}

    class FakeEmbeddingsApi:
        def create(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.5])])

    class FakeClient:
        def __init__(self):
            self.embeddings = FakeEmbeddingsApi()

    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-test"},
            "api_providers": {"openai": "https://api.openai.com/v1"},
            "capability_timeouts": {"embedding": 55},
        }
    )
    _embed_texts(
        EmbeddingRequest(provider="openai", model="text-embedding-3-small", texts=["a"]),
        settings=settings,
        client_factory=lambda _k, _b: FakeClient(),
        capability="embedding",
    )
    assert captured.get("timeout") == 55


def test_facade_embed_retries_with_capability_retries() -> None:
    calls = {"n": 0}

    class FakeEmbeddingsApi:
        def create(self, **kwargs):
            calls["n"] += 1
            if calls["n"] < 2:
                raise GatewayProviderError("Error code: 500 internal_server_error")
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0])])

    class FakeClient:
        def __init__(self):
            self.embeddings = FakeEmbeddingsApi()

    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-test"},
            "api_providers": {"openai": "https://api.openai.com/v1"},
            "capability_retries": {"embedding": 3},
        }
    )
    result = _embed_texts(
        EmbeddingRequest(provider="openai", model="text-embedding-3-small", texts=["a"]),
        settings=settings,
        client_factory=lambda _k, _b: FakeClient(),
        capability="embedding",
    )
    assert calls["n"] == 2
    assert result.meta.retry_count == 1


def test_facade_tts_volcengine_passes_timeout_to_client(tmp_path) -> None:
    captured: dict = {}

    class FakeSpeechApi:
        def create(self, **kwargs):
            captured.update(kwargs)

            class R:
                def write_to_file(self, p):
                    from pathlib import Path

                    Path(p).write_bytes(b"mp3")

            return R()

    class FakeClient:
        def __init__(self):
            self.audio = SimpleNamespace(speech=FakeSpeechApi())

    settings = settings_from_dict(
        {
            "api_keys": {"volcengine": "sk-volc"},
            "api_providers": {"volcengine": "https://ark.cn-beijing.volces.com/api/v3"},
            "capability_timeouts": {"tts": 120},
        }
    )
    _synthesize_speech(
        SpeechRequest(
            provider="volcengine",
            voice="zh_female_shuangkuaisisi_moon_bigtts",
            text="hello",
            model="volcengine-tts-standard",
            output_path=str(tmp_path / "out.mp3"),
            metadata_path=str(tmp_path / "meta.json"),
        ),
        settings=settings,
        communicator_factory=lambda _k, _b: FakeClient(),
        capability="tts",
    )
    assert captured.get("timeout") == 120.0


def test_facade_tts_edge_honors_capability_timeout(tmp_path) -> None:
    import asyncio

    class SlowCommunicate:
        async def save(self, audio_path, metadata_path):
            await asyncio.sleep(0.2)
            from pathlib import Path

            Path(audio_path).write_bytes(b"audio")

    settings = settings_from_dict({"capability_timeouts": {"tts": 0.05}})
    with pytest.raises(GatewayProviderError, match="timed out"):
        _synthesize_speech(
            SpeechRequest(
                provider="edge_tts",
                voice="en-US-EmmaMultilingualNeural",
                text="hello",
                output_path=str(tmp_path / "out.mp3"),
                metadata_path=str(tmp_path / "meta.json"),
            ),
            settings=settings,
            communicator_factory=lambda *args, **kwargs: SlowCommunicate(),
            capability="tts",
        )


def test_facade_embed_logs_timeout_retry_contract(tmp_path) -> None:
    import json
    from movieteller_logging import configure_async_logging, flush_async_logging, shutdown_async_logging
    from movieteller_logging import events as log_events

    class FakeEmbeddingsApi:
        def create(self, **kwargs):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[0.5])])

    class FakeClient:
        def __init__(self):
            self.embeddings = FakeEmbeddingsApi()

    log_path = tmp_path / "gateway.jsonl"
    configure_async_logging(
        enabled=True,
        level="INFO",
        format="jsonl",
        stderr=False,
        file=str(log_path),
    )
    try:
        settings = settings_from_dict(
            {
                "gateway": {"default_provider": "openai"},
                "api_keys": {"openai": "sk-test"},
                "api_providers": {"openai": "https://api.openai.com/v1"},
                "capability_timeouts": {"embedding": 55},
                "capability_retries": {"embedding": 3},
            }
        )
        _embed_texts(
            EmbeddingRequest(provider="openai", model="text-embedding-3-small", texts=["a"]),
            settings=settings,
            client_factory=lambda _k, _b: FakeClient(),
            capability="embedding",
        )
        flush_async_logging()
    finally:
        shutdown_async_logging()

    rows = [json.loads(line) for line in log_path.read_text(encoding="utf-8").splitlines()]
    start = next(row for row in rows if row["event"] == log_events.GATEWAY_EMBEDDING_START)
    done = next(row for row in rows if row["event"] == log_events.GATEWAY_EMBEDDING_DONE)
    assert start["timeout_sec"] == 55.0
    assert start["retry_count"] == 0
    assert start["max_attempts"] == 3
    assert done["timeout_sec"] == 55.0
    assert done["retry_count"] == 0
    assert done["max_attempts"] == 3
    assert "duration_ms" in done
