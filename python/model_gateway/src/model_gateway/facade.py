from __future__ import annotations

from typing import Any, Callable

from model_gateway.adapters.edge_tts import synthesize_speech as _synthesize_speech_via_edge_tts
from model_gateway.adapters.openai_compatible import (
    embed_texts as _embed_texts_via_openai_compatible,
)
from model_gateway.adapters.openai_compatible import (
    generate_chat as _generate_chat_via_openai_compatible,
)
from model_gateway.errors import GatewayConfigError, GatewayUnsupportedCapabilityError
from model_gateway.policies import execute_with_retry, limited
from model_gateway.router import (
    resolve_chat_endpoint,
    resolve_embedding_endpoint,
    resolve_speech_endpoint,
)
from model_gateway.telemetry import emit_gateway_event
from model_gateway.types import (
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    SpeechRequest,
    SpeechResult,
)


def generate_chat(
    request: ChatRequest,
    *,
    settings,
    client_factory: Callable[[str, str | None], Any] | None = None,
) -> ChatResult:
    if not str(request.model).strip():
        raise GatewayConfigError("chat model is empty")
    endpoint = resolve_chat_endpoint(request, settings)
    if endpoint.adapter != "openai_compatible":
        raise GatewayUnsupportedCapabilityError(
            f"Unsupported chat adapter '{endpoint.adapter}'"
        )
    def _run() -> ChatResult:
        with limited(endpoint.adapter):
            return _generate_chat_via_openai_compatible(
                request,
                endpoint,
                client_factory=client_factory,
            )
    result, retry_count = execute_with_retry(_run)
    result = ChatResult(
        text=result.text,
        finish_reason=result.finish_reason,
        usage=result.usage,
        meta=type(result.meta)(
            provider=result.meta.provider,
            model=result.meta.model,
            request_id=result.meta.request_id,
            retry_count=retry_count,
            latency_sec=result.meta.latency_sec,
        ),
        raw=result.raw,
    )
    emit_gateway_event(
        "chat",
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
        retry_count=retry_count,
    )
    return result


def embed_texts(
    request: EmbeddingRequest,
    *,
    settings,
    client_factory: Callable[[str, str | None], Any] | None = None,
) -> EmbeddingResult:
    if not str(request.model).strip():
        raise GatewayConfigError("embedding model is empty")
    endpoint = resolve_embedding_endpoint(request, settings)
    if endpoint.adapter != "openai_compatible":
        raise GatewayUnsupportedCapabilityError(
            f"Unsupported embedding adapter '{endpoint.adapter}'"
        )
    def _run() -> EmbeddingResult:
        with limited(endpoint.adapter):
            return _embed_texts_via_openai_compatible(
                request,
                endpoint,
                client_factory=client_factory,
            )
    result, retry_count = execute_with_retry(_run)
    result = EmbeddingResult(
        vectors=result.vectors,
        usage=result.usage,
        meta=type(result.meta)(
            provider=result.meta.provider,
            model=result.meta.model,
            request_id=result.meta.request_id,
            retry_count=retry_count,
            latency_sec=result.meta.latency_sec,
        ),
        raw=result.raw,
    )
    emit_gateway_event(
        "embedding",
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
        retry_count=retry_count,
    )
    return result


def synthesize_speech(
    request: SpeechRequest,
    *,
    settings,
    communicator_factory: Callable[..., Any] | None = None,
) -> SpeechResult:
    endpoint = resolve_speech_endpoint(request, settings)
    if endpoint.adapter != "edge_tts":
        raise GatewayUnsupportedCapabilityError(
            f"Unsupported speech adapter '{endpoint.adapter}'"
        )
    def _run() -> SpeechResult:
        with limited(endpoint.adapter):
            return _synthesize_speech_via_edge_tts(
                request,
                endpoint,
                communicator_factory_override=communicator_factory,
            )
    result, retry_count = execute_with_retry(_run)
    emit_gateway_event(
        "speech",
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
        retry_count=retry_count,
    )
    return SpeechResult(
        audio_path=result.audio_path,
        boundary_path=result.boundary_path,
        meta=(
            type(result.meta)(
                provider=result.meta.provider,
                model=result.meta.model,
                request_id=result.meta.request_id,
                retry_count=retry_count,
                latency_sec=result.meta.latency_sec,
            )
            if result.meta is not None
            else None
        ),
        raw=result.raw,
    )
