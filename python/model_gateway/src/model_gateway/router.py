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
    if provider in {"volcengine", "volcengine_tts"}:
        return "volcengine_tts"
    return "unsupported_speech"


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
