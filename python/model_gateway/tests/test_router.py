from movieteller_config.schema import settings_from_dict

from model_gateway.router import resolve_chat_endpoint, resolve_embedding_endpoint
from model_gateway.types import ChatRequest, EmbeddingRequest


def test_resolve_chat_endpoint_uses_provider_key_and_base_url():
    settings = settings_from_dict(
        {
            "api_keys": {"dashscope": "k1"},
            "api_base_urls": {"dashscope": "https://dash.example/v1"},
        }
    )
    endpoint = resolve_chat_endpoint(
        ChatRequest(provider="dashscope", model="qwen-plus", messages=[]),
        settings,
    )
    assert endpoint.provider == "dashscope"
    assert endpoint.model == "qwen-plus"
    assert endpoint.api_key == "k1"
    assert endpoint.base_url == "https://dash.example/v1"
    assert endpoint.adapter == "openai_compatible"


def test_resolve_embedding_endpoint_uses_openai_fallback_base_url():
    settings = settings_from_dict(
        {
            "openai_api_key": "sk-openai",
            "openai_base_url": "https://openai.example/v1",
        }
    )
    endpoint = resolve_embedding_endpoint(
        EmbeddingRequest(provider="openai", model="text-embedding-3-small", texts=["x"]),
        settings,
    )
    assert endpoint.base_url == "https://openai.example/v1"
