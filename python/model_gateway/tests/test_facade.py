from types import SimpleNamespace

from movieteller_config.schema import settings_from_dict

from model_gateway.errors import GatewayConfigError
from model_gateway.facade import (
    _embed_texts,
    _generate_chat,
    _synthesize_speech,
    embed_texts_for_capability,
    generate_narration,
    polish_text,
    synthesize_speech_for_capability,
)
from model_gateway.types import ChatRequest, EmbeddingRequest, SpeechRequest


def test_facade_generate_chat_routes_through_openai_compatible_adapter():
    class FakeChatApi:
        def create(self, **kwargs):
            return SimpleNamespace(
                choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="ok"))]
            )

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeChatApi())

    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-test"},
            "api_providers": {"openai": "https://api.openai.com/v1"},
        }
    )
    result = _generate_chat(
        ChatRequest(provider="openai", model="gpt-4o-mini", messages=[]),
        settings=settings,
        client_factory=lambda _k, _b: FakeClient(),
    )
    assert result.text == "ok"


def test_facade_embed_texts_routes_through_openai_compatible_adapter():
    class FakeEmbeddingsApi:
        def create(self, *, model, input):
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0]) for _ in input])

    class FakeClient:
        def __init__(self):
            self.embeddings = FakeEmbeddingsApi()

    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-test"},
            "api_providers": {"openai": "https://api.openai.com/v1"},
        }
    )
    result = _embed_texts(
        EmbeddingRequest(provider="openai", model="text-embedding-3-small", texts=["a"]),
        settings=settings,
        client_factory=lambda _k, _b: FakeClient(),
    )
    assert result.vectors == ((1.0,),)


def test_facade_synthesize_speech_routes_through_edge_tts_adapter(tmp_path):
    class FakeCommunicate:
        async def save(self, audio_path, metadata_path):
            from pathlib import Path

            Path(audio_path).write_bytes(b"audio")
            Path(metadata_path).write_text("{}", encoding="utf-8")

    settings = settings_from_dict({})
    result = _synthesize_speech(
        SpeechRequest(
            provider="edge_tts",
            voice="en-US-EmmaMultilingualNeural",
            text="hello",
            output_path=str(tmp_path / "out.mp3"),
            metadata_path=str(tmp_path / "out.mp3.jsonl"),
        ),
        settings=settings,
        communicator_factory=lambda *args, **kwargs: FakeCommunicate(),
    )
    assert result.audio_path.endswith(".mp3")


def test_facade_synthesize_speech_routes_through_volcengine_adapter(tmp_path):
    class FakeSpeechApi:
        def create(self, **kwargs):
            assert kwargs["model"] == "volcengine-tts-standard"
            assert kwargs["voice"] == "zh_female_shuangkuaisisi_moon_bigtts"
            assert kwargs["input"] == "hello"

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
        }
    )
    result = _synthesize_speech(
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
    )
    assert result.audio_path.endswith(".mp3")
    assert result.meta is not None
    assert result.meta.model == "volcengine-tts-standard"


def test_facade_synthesize_speech_routes_through_dashscope_adapter(tmp_path):
    class FakeSynthesizer:
        @staticmethod
        def call(**kwargs):
            assert kwargs["model"] == "qwen3-tts-flash"
            assert kwargs["api_key"] == "sk-dash"
            assert kwargs["text"] == "hello"
            assert kwargs["voice"] == "Cherry"
            return SimpleNamespace(
                status_code=200,
                code="",
                message="",
                output=SimpleNamespace(audio={"url": "https://example.test/audio.wav"}),
            )

    class FakeAudio:
        qwen_tts = SimpleNamespace(SpeechSynthesizer=FakeSynthesizer)

    class FakeDashScope:
        audio = FakeAudio()
        base_http_api_url = None

    settings = settings_from_dict(
        {
            "api_keys": {"dashscope": "sk-dash"},
            "api_providers": {"dashscope": "https://dashscope.aliyuncs.com/compatible-mode"},
        }
    )
    class FakeHttpResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def read(self):
            return b"mp3"

    from unittest.mock import patch

    with patch("model_gateway.adapters.dashscope_tts.urlopen", return_value=FakeHttpResponse()):
        result = _synthesize_speech(
            SpeechRequest(
                provider="dashscope",
                voice="Cherry",
                text="hello",
                model="qwen3-tts-flash",
                output_path=str(tmp_path / "out.mp3"),
                metadata_path=str(tmp_path / "meta.json"),
            ),
            settings=settings,
            communicator_factory=lambda _k: FakeDashScope(),
        )
    
    assert result.audio_path.endswith(".mp3")
    assert result.meta is not None
    assert result.meta.model == "qwen3-tts-flash"


def test_facade_synthesize_speech_rejects_openspeech_base_url_for_openai_style_tts(tmp_path):
    settings = settings_from_dict(
        {
            "api_keys": {"volcengine_tts": "sk-vtts"},
            "api_providers": {"volcengine_tts": "https://openspeech.bytedance.com"},
        }
    )
    try:
        _synthesize_speech(
            SpeechRequest(
                provider="volcengine_tts",
                voice="zh_female_shuangkuaisisi_moon_bigtts",
                text="hello",
                model="volcengine-tts-standard",
                output_path=str(tmp_path / "out.mp3"),
            ),
            settings=settings,
        )
        assert False, "expected GatewayConfigError"
    except GatewayConfigError as exc:
        assert "OpenAI-compatible audio.speech" in str(exc)
        assert "ark.cn-beijing.volces.com/api/v3" in str(exc)


def test_facade_generate_narration_uses_default_model_and_provider():
    class FakeChatApi:
        def create(self, **kwargs):
            assert kwargs["model"] == "vision-default"
            return SimpleNamespace(
                choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="ok"))]
            )

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeChatApi())

    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_providers": {"newapi": "http://127.0.0.1:3000/v1"},
            "api_keys": {"newapi": "sk-new"},
            "model_catalog": ["vision-default"],
            "model_defaults": {"narration": "vision-default"},
        }
    )
    result = generate_narration(
        messages=[],
        settings=settings,
        client_factory=lambda _k, _b: FakeClient(),
    )
    assert result.text == "ok"


def test_facade_polish_text_uses_default_model_and_provider():
    class FakeChatApi:
        def create(self, **kwargs):
            assert kwargs["model"] == "polish-default"
            return SimpleNamespace(
                choices=[SimpleNamespace(finish_reason="stop", message=SimpleNamespace(content="ok-polish"))]
            )

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeChatApi())

    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_providers": {"newapi": "http://127.0.0.1:3000/v1"},
            "api_keys": {"newapi": "sk-new"},
            "model_catalog": ["polish-default"],
            "model_defaults": {"polish": "polish-default"},
        }
    )
    result = polish_text(
        messages=[],
        settings=settings,
        client_factory=lambda _k, _b: FakeClient(),
    )
    assert result.text == "ok-polish"


def test_facade_embed_texts_for_capability_uses_default_model():
    class FakeEmbeddingsApi:
        def create(self, *, model, input):
            assert model == "embed-default"
            return SimpleNamespace(data=[SimpleNamespace(embedding=[1.0]) for _ in input])

    class FakeClient:
        def __init__(self):
            self.embeddings = FakeEmbeddingsApi()

    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_providers": {"newapi": "http://127.0.0.1:3000/v1"},
            "api_keys": {"newapi": "sk-new"},
            "model_catalog": ["embed-default"],
            "model_defaults": {"embedding": "embed-default"},
        }
    )
    result = embed_texts_for_capability(
        texts=["a"],
        settings=settings,
        client_factory=lambda _k, _b: FakeClient(),
    )
    assert result.vectors == ((1.0,),)


def test_facade_synthesize_speech_for_capability_uses_default_model(tmp_path):
    class FakeSpeechApi:
        def create(self, **kwargs):
            assert kwargs["model"] == "qwen3-tts-flash"
            assert kwargs["voice"] == "Cherry"
            assert kwargs["input"] == "hello"

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
            "gateway": {"default_provider": "newapi"},
            "api_providers": {"newapi": "http://127.0.0.1:3000/v1"},
            "api_keys": {"newapi": "sk-new"},
            "model_catalog": ["qwen3-tts-flash"],
            "model_defaults": {"tts": "qwen3-tts-flash"},
        }
    )
    result = synthesize_speech_for_capability(
        text="hello",
        voice="Cherry",
        output_path=str(tmp_path / "out.mp3"),
        settings=settings,
        communicator_factory=lambda _k, _b: FakeClient(),
    )
    assert result.audio_path.endswith(".mp3")
