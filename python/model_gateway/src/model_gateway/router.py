from __future__ import annotations

from dataclasses import dataclass

from model_gateway.types import ChatRequest, EmbeddingRequest, SpeechRequest


@dataclass(frozen=True)
class ResolvedEndpoint:
    provider: str
    model: str
    base_url: str | None
    api_key: str | None
    adapter: str


def resolve_default_model(capability: str, settings) -> str:
    model = str(settings.default_model_for_capability(capability)).strip()
    if not model:
        raise ValueError(f"default model is empty for capability '{capability}'")
    return model


def resolve_model_provider(model: str, settings) -> str:
    return resolve_model_provider_for_capability(model, settings, capability=None)


def resolve_model_provider_for_capability(model: str, settings, capability: str | None) -> str:
    model_id = str(model).strip()
    if not model_id:
        raise ValueError("model is empty")
    catalog = getattr(settings, "model_catalog", {})
    if catalog and model_id not in catalog:
        raise ValueError(f"model '{model_id}' is not in model_catalog")
    if capability is not None and hasattr(settings, "provider_for_capability"):
        provider = str(settings.provider_for_capability(capability)).strip().lower()
    else:
        provider = str(settings.default_provider()).strip().lower()
    if not provider:
        raise ValueError("default provider is empty")
    return provider


def resolve_model_endpoint(model: str, capability: str, settings) -> ResolvedEndpoint:
    provider = resolve_model_provider_for_capability(model, settings, capability)
    adapter = _resolve_capability_adapter(capability, provider)
    base_url = _resolve_base_url(settings, provider)
    if adapter == "edge_tts":
        api_key = settings.get_api_key(provider) if hasattr(settings, "get_api_key") else None
    else:
        api_key = settings.require_api_key(provider)
    return ResolvedEndpoint(
        provider=provider,
        model=str(model).strip(),
        base_url=base_url,
        api_key=api_key,
        adapter=adapter,
    )


def _resolve_base_url(settings, provider: str) -> str | None:
    base_url = settings.get_api_base_url(provider)
    if provider == "openai" and not base_url:
        return settings.openai_base_url
    return base_url


def _resolve_adapter(provider: str) -> str:
    if provider == "edge_tts":
        return "edge_tts"
    return "openai_compatible"


def _resolve_speech_adapter(provider: str) -> str:
    if provider == "edge_tts":
        return "edge_tts"
    if provider in {"dashscope", "dashscope_tts"}:
        return "dashscope_tts"
    if provider in {"volcengine", "volcengine_tts", "newapi", "openai"}:
        return "volcengine_tts"
    return "unsupported_speech"


def _resolve_capability_adapter(capability: str, provider: str) -> str:
    cap = str(capability or "").strip().lower()
    if cap in {"narration", "polish", "chat"}:
        return _resolve_adapter(provider)
    if cap in {"embedding", "embed"}:
        return _resolve_adapter(provider)
    if cap in {"tts", "speech"}:
        return _resolve_speech_adapter(provider)
    raise ValueError(f"unsupported capability '{capability}'")


def resolve_chat_endpoint(request: ChatRequest, settings) -> ResolvedEndpoint:
    provider = str(request.provider).strip().lower() or "openai"
    model = str(request.model).strip()
    api_key = settings.require_api_key(provider)
    return ResolvedEndpoint(
        provider=provider,
        model=model,
        base_url=_resolve_base_url(settings, provider),
        api_key=api_key,
        adapter=_resolve_adapter(provider),
    )


def resolve_embedding_endpoint(request: EmbeddingRequest, settings) -> ResolvedEndpoint:
    provider = str(request.provider).strip().lower() or "openai"
    model = str(request.model).strip()
    api_key = settings.require_api_key(provider)
    return ResolvedEndpoint(
        provider=provider,
        model=model,
        base_url=_resolve_base_url(settings, provider),
        api_key=api_key,
        adapter=_resolve_adapter(provider),
    )


def resolve_speech_endpoint(request: SpeechRequest, settings) -> ResolvedEndpoint:
    provider = str(request.provider).strip().lower() or "edge_tts"
    adapter = _resolve_speech_adapter(provider)
    model = str(getattr(request, "model", None) or "").strip()
    base_url = _resolve_base_url(settings, provider)
    if adapter == "edge_tts":
        api_key = settings.get_api_key(provider) if hasattr(settings, "get_api_key") else None
    else:
        api_key = settings.require_api_key(provider)
    return ResolvedEndpoint(
        provider=provider,
        model=model,
        base_url=base_url,
        api_key=api_key,
        adapter=adapter,
    )
