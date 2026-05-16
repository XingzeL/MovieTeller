from movieteller_config.schema import settings_from_dict

from model_gateway.router import (
    resolve_chat_endpoint,
    resolve_embedding_endpoint,
    resolve_speech_endpoint,
)
from model_gateway.types import ChatRequest, EmbeddingRequest, SpeechRequest


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


def test_resolve_speech_endpoint_volcengine_requires_key_and_model():
    settings = settings_from_dict(
        {
            "api_keys": {"volcengine": "sk-v"},
            "api_base_urls": {"volcengine": "https://ark.cn-beijing.volces.com/api/v3"},
        }
    )
    endpoint = resolve_speech_endpoint(
        SpeechRequest(
            provider="volcengine",
            voice="zh_female_shuangkuaisisi_moon_bigtts",
            text="x",
            model="volcengine-tts-standard",
        ),
        settings,
    )
    assert endpoint.provider == "volcengine"
    assert endpoint.adapter == "volcengine_tts"
    assert endpoint.api_key == "sk-v"
    assert endpoint.base_url == "https://ark.cn-beijing.volces.com/api/v3"
    assert endpoint.model == "volcengine-tts-standard"


def test_resolve_speech_endpoint_volcengine_tts_alias_uses_volcengine_adapter():
    settings = settings_from_dict(
        {
            "api_keys": {"volcengine_tts": "sk-vtts"},
            "api_base_urls": {"volcengine_tts": "https://openspeech.bytedance.com"},
        }
    )
    endpoint = resolve_speech_endpoint(
        SpeechRequest(
            provider="volcengine_tts",
            voice="zh_female_shuangkuaisisi_moon_bigtts",
            text="x",
            model="volcengine-tts-standard",
        ),
        settings,
    )
    assert endpoint.provider == "volcengine_tts"
    assert endpoint.adapter == "volcengine_tts"
    assert endpoint.api_key == "sk-vtts"
    assert endpoint.base_url == "https://openspeech.bytedance.com"
    assert endpoint.model == "volcengine-tts-standard"


def test_resolve_speech_endpoint_edge_tts_does_not_require_api_key():
    settings = settings_from_dict({})
    endpoint = resolve_speech_endpoint(
        SpeechRequest(provider="edge_tts", voice="en-US-EmmaMultilingualNeural", text="hi"),
        settings,
    )
    assert endpoint.adapter == "edge_tts"
    assert endpoint.api_key is None
