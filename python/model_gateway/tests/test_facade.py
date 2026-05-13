from types import SimpleNamespace

from movieteller_config.schema import settings_from_dict

from model_gateway.facade import embed_texts, generate_chat, synthesize_speech
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

    settings = settings_from_dict({"openai_api_key": "sk-test"})
    result = generate_chat(
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

    settings = settings_from_dict({"openai_api_key": "sk-test"})
    result = embed_texts(
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
    result = synthesize_speech(
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
