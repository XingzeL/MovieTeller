from __future__ import annotations

from typing import Any, Callable

from model_gateway.adapters.edge_tts import synthesize_speech as _synthesize_speech_via_edge_tts
from model_gateway.adapters.openai_compatible import (
    embed_texts as _embed_texts_via_openai_compatible,
)
from model_gateway.adapters.openai_compatible import (
    generate_chat as _generate_chat_via_openai_compatible,
)
from model_gateway.adapters.dashscope_tts import (
    synthesize_speech as _synthesize_speech_via_dashscope,
)
from model_gateway.adapters.volcengine_tts import (
    synthesize_speech as _synthesize_speech_via_volcengine,
)
from model_gateway.errors import GatewayConfigError, GatewayUnsupportedCapabilityError
from model_gateway.policies import execute_with_retry, limited
from model_gateway.router import (
    resolve_default_model,
    resolve_chat_endpoint,
    resolve_embedding_endpoint,
    resolve_model_endpoint,
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
    if endpoint.adapter == "edge_tts":

        def _run_edge() -> SpeechResult:
            with limited(endpoint.adapter):
                return _synthesize_speech_via_edge_tts(
                    request,
                    endpoint,
                    communicator_factory_override=communicator_factory,
                )

        result, retry_count = execute_with_retry(_run_edge)
    elif endpoint.adapter == "dashscope_tts":

        def _run_dashscope() -> SpeechResult:
            with limited(endpoint.adapter):
                return _synthesize_speech_via_dashscope(
                    request,
                    endpoint,
                    client_factory=communicator_factory,
                )

        result, retry_count = execute_with_retry(_run_dashscope)
    elif endpoint.adapter == "volcengine_tts":

        def _run_volc() -> SpeechResult:
            with limited(endpoint.adapter):
                return _synthesize_speech_via_volcengine(
                    request,
                    endpoint,
                    client_factory=communicator_factory,
                )

        result, retry_count = execute_with_retry(_run_volc)
    else:
        raise GatewayUnsupportedCapabilityError(
            f"Unsupported speech provider '{endpoint.provider}' via adapter '{endpoint.adapter}'"
        )
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


def generate_narration(
    *,
    messages,
    settings,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_sec: float | None = None,
    response_format: str | None = None,
    meta=None,
    client_factory: Callable[[str, str | None], Any] | None = None,
) -> ChatResult:
    model = resolve_default_model("narration", settings)
    endpoint = resolve_model_endpoint(model, "narration", settings)
    if endpoint.adapter != "openai_compatible":
        raise GatewayUnsupportedCapabilityError(
            f"Unsupported narration adapter '{endpoint.adapter}'"
        )
    request = ChatRequest(
        provider=endpoint.provider,
        model=endpoint.model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        response_format=response_format,
        meta=meta,
    )
    return generate_chat(request, settings=settings, client_factory=client_factory)


def polish_text(
    *,
    messages,
    settings,
    temperature: float | None = None,
    max_tokens: int | None = None,
    timeout_sec: float | None = None,
    response_format: str | None = None,
    meta=None,
    client_factory: Callable[[str, str | None], Any] | None = None,
) -> ChatResult:
    model = resolve_default_model("polish", settings)
    endpoint = resolve_model_endpoint(model, "polish", settings)
    if endpoint.adapter != "openai_compatible":
        raise GatewayUnsupportedCapabilityError(
            f"Unsupported polish adapter '{endpoint.adapter}'"
        )
    request = ChatRequest(
        provider=endpoint.provider,
        model=endpoint.model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_sec=timeout_sec,
        response_format=response_format,
        meta=meta,
    )
    return generate_chat(request, settings=settings, client_factory=client_factory)


def embed_texts_for_capability(
    *,
    texts,
    settings,
    batch_size: int | None = None,
    timeout_sec: float | None = None,
    meta=None,
    client_factory: Callable[[str, str | None], Any] | None = None,
) -> EmbeddingResult:
    model = resolve_default_model("embedding", settings)
    endpoint = resolve_model_endpoint(model, "embedding", settings)
    if endpoint.adapter != "openai_compatible":
        raise GatewayUnsupportedCapabilityError(
            f"Unsupported embedding adapter '{endpoint.adapter}'"
        )
    request = EmbeddingRequest(
        provider=endpoint.provider,
        model=endpoint.model,
        texts=texts,
        batch_size=batch_size,
        timeout_sec=timeout_sec,
        meta=meta,
    )
    return embed_texts(request, settings=settings, client_factory=client_factory)


def synthesize_speech_for_capability(
    *,
    text: str,
    settings,
    voice: str,
    output_path: str | None = None,
    metadata_path: str | None = None,
    rate: str | None = None,
    volume: str | None = None,
    pitch: str | None = None,
    boundary: str | None = None,
    timeout_sec: float | None = None,
    meta=None,
    communicator_factory: Callable[..., Any] | None = None,
) -> SpeechResult:
    model = resolve_default_model("tts", settings)
    endpoint = resolve_model_endpoint(model, "tts", settings)
    request = SpeechRequest(
        provider=endpoint.provider,
        voice=voice,
        text=text,
        model=endpoint.model,
        rate=rate,
        volume=volume,
        pitch=pitch,
        boundary=boundary,
        output_path=output_path,
        metadata_path=metadata_path,
        timeout_sec=timeout_sec,
        meta=meta,
    )
    return synthesize_speech(
        request,
        settings=settings,
        communicator_factory=communicator_factory,
    )
