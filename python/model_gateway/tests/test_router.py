from movieteller_config.schema import settings_from_dict

from model_gateway.router import (
    _resolve_chat_endpoint,
    _resolve_embedding_endpoint,
    _resolve_speech_endpoint,
    resolve_capability_model_endpoint,
    resolve_default_model,
    resolve_model_endpoint,
    resolve_model_provider,
)
from model_gateway.types import ChatRequest, EmbeddingRequest, SpeechRequest


def test__resolve_chat_endpoint_uses_provider_key_and_base_url():
    settings = settings_from_dict(
        {
            "api_keys": {"dashscope": "k1"},
            "api_providers": {"dashscope": "https://dash.example/v1"},
        }
    )
    endpoint = _resolve_chat_endpoint(
        ChatRequest(provider="dashscope", model="qwen-plus", messages=[]),
        settings,
    )
    assert endpoint.provider == "dashscope"
    assert endpoint.model == "qwen-plus"
    assert endpoint.api_key == "k1"
    assert endpoint.base_url == "https://dash.example/v1"
    assert endpoint.adapter == "openai_compatible"


def test__resolve_embedding_endpoint_uses_openai_api_providers():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-openai"},
            "api_providers": {"openai": "https://openai.example/v1"},
        }
    )
    endpoint = _resolve_embedding_endpoint(
        EmbeddingRequest(provider="openai", model="text-embedding-3-small", texts=["x"]),
        settings,
    )
    assert endpoint.base_url == "https://openai.example/v1"


def test__resolve_speech_endpoint_volcengine_requires_key_and_model():
    settings = settings_from_dict(
        {
            "api_keys": {"volcengine": "sk-v"},
            "api_providers": {"volcengine": "https://ark.cn-beijing.volces.com/api/v3"},
        }
    )
    endpoint = _resolve_speech_endpoint(
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


def test__resolve_speech_endpoint_volcengine_tts_alias_uses_volcengine_adapter():
    settings = settings_from_dict(
        {
            "api_keys": {"volcengine_tts": "sk-vtts"},
            "api_providers": {"volcengine_tts": "https://openspeech.bytedance.com"},
        }
    )
    endpoint = _resolve_speech_endpoint(
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


def test__resolve_speech_endpoint_edge_tts_does_not_require_api_key():
    settings = settings_from_dict({})
    endpoint = _resolve_speech_endpoint(
        SpeechRequest(provider="edge_tts", voice="en-US-EmmaMultilingualNeural", text="hi"),
        settings,
    )
    assert endpoint.adapter == "edge_tts"
    assert endpoint.api_key is None


def test__resolve_speech_endpoint_dashscope_uses_dashscope_adapter():
    settings = settings_from_dict(
        {
            "api_keys": {"dashscope": "sk-dash"},
            "api_providers": {"dashscope": "https://dashscope.aliyuncs.com/compatible-mode"},
        }
    )
    endpoint = _resolve_speech_endpoint(
        SpeechRequest(
            provider="dashscope",
            voice="Cherry",
            text="x",
            model="qwen3-tts-flash",
        ),
        settings,
    )
    assert endpoint.provider == "dashscope"
    assert endpoint.adapter == "dashscope_tts"
    assert endpoint.api_key == "sk-dash"
    assert endpoint.base_url == "https://dashscope.aliyuncs.com/compatible-mode"
    assert endpoint.model == "qwen3-tts-flash"


def test_resolve_default_model_uses_new_schema_defaults():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_providers": {"newapi": "http://127.0.0.1:3000/v1"},
            "api_keys": {"newapi": "sk-new"},
            "model_catalog": [
                "vision-default",
                "text-default",
                "tts-default",
                "embed-default",
            ],
            "model_defaults": {
                "narration": "vision-default",
                "polish": "text-default",
                "tts": "tts-default",
                "embedding": "embed-default",
            },
        }
    )
    assert resolve_default_model("narration", settings) == "vision-default"
    assert resolve_default_model("polish", settings) == "text-default"
    assert resolve_default_model("tts", settings) == "tts-default"
    assert resolve_default_model("embedding", settings) == "embed-default"


def test_resolve_model_provider_uses_default_provider_and_catalog_whitelist():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_providers": {"newapi": "http://127.0.0.1:3000/v1"},
            "api_keys": {"newapi": "sk-new"},
            "model_catalog": ["vision-default"],
        }
    )
    assert resolve_model_provider("vision-default", settings) == "newapi"


def test_resolve_model_endpoint_for_tts_uses_newapi_openai_style_speech():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_providers": {"newapi": "http://127.0.0.1:3000/v1"},
            "api_keys": {"newapi": "sk-new"},
            "model_catalog": ["qwen3-tts-flash"],
        }
    )
    endpoint = resolve_model_endpoint("qwen3-tts-flash", "tts", settings)
    assert endpoint.provider == "newapi"
    assert endpoint.adapter == "volcengine_tts"
    assert endpoint.base_url == "http://127.0.0.1:3000/v1"
    assert endpoint.model == "qwen3-tts-flash"


def test_resolve_model_endpoint_for_tts_uses_tts_provider_override():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi", "tts_provider": "dashscope"},
            "api_providers": {
                "newapi": "http://127.0.0.1:3000/v1",
                "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            "api_keys": {"newapi": "sk-new", "dashscope": "sk-dash"},
            "model_catalog": ["qwen3-tts-flash"],
        }
    )
    endpoint = resolve_model_endpoint("qwen3-tts-flash", "tts", settings)
    assert endpoint.provider == "dashscope"
    assert endpoint.adapter == "dashscope_tts"
    assert endpoint.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert endpoint.model == "qwen3-tts-flash"


def test_resolve_capability_model_endpoint_matches_pair_for_narration():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "openai"},
            "api_keys": {"openai": "sk-x"},
            "model_defaults": {"narration": "gpt-4o-mini"},
            "model_catalog": ["gpt-4o-mini"],
        }
    )
    via = resolve_capability_model_endpoint(capability="narration", settings=settings)
    model = resolve_default_model("narration", settings)
    direct = resolve_model_endpoint(model, "narration", settings)
    assert via == direct


def test_resolve_capability_model_endpoint_tts_uses_tts_provider():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi", "tts_provider": "dashscope"},
            "api_providers": {
                "newapi": "http://127.0.0.1:3000/v1",
                "dashscope": "https://dashscope.aliyuncs.com/compatible-mode/v1",
            },
            "api_keys": {"newapi": "sk-new", "dashscope": "sk-dash"},
            "model_catalog": ["qwen3-tts-flash"],
            "model_defaults": {"tts": "qwen3-tts-flash"},
        }
    )
    ep = resolve_capability_model_endpoint(capability="tts", settings=settings)
    assert ep.provider == "dashscope"
    assert ep.adapter == "dashscope_tts"
