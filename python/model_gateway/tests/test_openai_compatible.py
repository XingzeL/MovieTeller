from types import SimpleNamespace

from model_gateway.adapters.openai_compatible import embed_texts, generate_chat
from model_gateway.router import ResolvedEndpoint
from model_gateway.types import ChatRequest, EmbeddingRequest


def test_generate_chat_normalizes_text_response():
    class FakeChatApi:
        def create(self, **kwargs):
            assert kwargs["model"] == "demo-model"
            return SimpleNamespace(
                id="resp_1",
                choices=[
                    SimpleNamespace(
                        finish_reason="stop",
                        message=SimpleNamespace(content="hello world"),
                    )
                ],
                usage=SimpleNamespace(
                    prompt_tokens=10,
                    completion_tokens=5,
                    total_tokens=15,
                ),
            )

    class FakeClient:
        def __init__(self):
            self.chat = SimpleNamespace(completions=FakeChatApi())

    result = generate_chat(
        ChatRequest(
            provider="openai",
            model="demo-model",
            messages=[{"role": "user", "content": "hi"}],
        ),
        ResolvedEndpoint(
            provider="openai",
            model="demo-model",
            base_url=None,
            api_key="sk",
            adapter="openai_compatible",
        ),
        client_factory=lambda _k, _b: FakeClient(),
    )
    assert result.text == "hello world"
    assert result.usage is not None
    assert result.usage.total_tokens == 15


def test_embed_texts_normalizes_vectors():
    class FakeEmbeddingsApi:
        def create(self, *, model, input):
            assert model == "embed-model"
            return SimpleNamespace(
                id="emb_1",
                data=[SimpleNamespace(embedding=[1.0, 2.0]) for _ in input],
            )

    class FakeClient:
        def __init__(self):
            self.embeddings = FakeEmbeddingsApi()

    result = embed_texts(
        EmbeddingRequest(
            provider="openai",
            model="embed-model",
            texts=["a", "b"],
        ),
        ResolvedEndpoint(
            provider="openai",
            model="embed-model",
            base_url=None,
            api_key="sk",
            adapter="openai_compatible",
        ),
        client_factory=lambda _k, _b: FakeClient(),
    )
    assert result.vectors == ((1.0, 2.0), (1.0, 2.0))
