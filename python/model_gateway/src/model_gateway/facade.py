from __future__ import annotations

import logging
import time
from dataclasses import replace
from typing import Any, Callable

from movieteller_logging import classify_error, emit_event
from movieteller_logging import events as log_events

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
    _resolve_chat_endpoint,
    _resolve_embedding_endpoint,
    _resolve_speech_endpoint,
    resolve_capability_model_endpoint,
)
from model_gateway.types import (
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    SpeechRequest,
    SpeechResult,
)


def _generate_chat(
    request: ChatRequest,
    *,
    settings,
    client_factory: Callable[[str, str | None], Any] | None = None,
    capability: str = "chat",
) -> ChatResult:
    if not str(request.model).strip():
        raise GatewayConfigError("chat model is empty")
    endpoint = _resolve_chat_endpoint(request, settings)
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

    emit_event(
        log_events.GATEWAY_CHAT_START,
        capability=capability,
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
    )
    timeout_sec = request.timeout_sec
    if timeout_sec is None and settings is not None:
        timeout_sec = settings.capability_timeout_sec(capability)
    if timeout_sec is not None and request.timeout_sec is None:
        request = replace(request, timeout_sec=timeout_sec)
    max_attempts = 2
    if settings is not None:
        max_attempts = settings.capability_max_attempts(capability)
    t0 = time.perf_counter()
    try:
        result, retry_count = execute_with_retry(_run, max_attempts=max_attempts)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        emit_event(
            log_events.GATEWAY_CHAT_FAILED,
            level=logging.ERROR,
            capability=capability,
            provider=endpoint.provider,
            model=endpoint.model,
            adapter=endpoint.adapter,
            duration_ms=duration_ms,
            status="error",
            fatal=True,
            **classify_error(exc),
        )
        raise
    duration_ms = int((time.perf_counter() - t0) * 1000)
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
    emit_event(
        log_events.GATEWAY_CHAT_DONE,
        capability=capability,
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
        duration_ms=duration_ms,
        status="ok",
        retry_count=retry_count,
    )
    return result


def _embed_texts(
    request: EmbeddingRequest,
    *,
    settings,
    client_factory: Callable[[str, str | None], Any] | None = None,
    capability: str = "embedding",
) -> EmbeddingResult:
    if not str(request.model).strip():
        raise GatewayConfigError("embedding model is empty")
    endpoint = _resolve_embedding_endpoint(request, settings)
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

    emit_event(
        log_events.GATEWAY_EMBEDDING_START,
        capability=capability,
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
    )
    t0 = time.perf_counter()
    try:
        result, retry_count = execute_with_retry(_run)
    except Exception as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        emit_event(
            log_events.GATEWAY_EMBEDDING_FAILED,
            level=logging.ERROR,
            capability=capability,
            provider=endpoint.provider,
            model=endpoint.model,
            adapter=endpoint.adapter,
            duration_ms=duration_ms,
            status="error",
            fatal=True,
            **classify_error(exc),
        )
        raise
    duration_ms = int((time.perf_counter() - t0) * 1000)
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
    emit_event(
        log_events.GATEWAY_EMBEDDING_DONE,
        capability=capability,
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
        duration_ms=duration_ms,
        status="ok",
        retry_count=retry_count,
    )
    return result


def _synthesize_speech(
    request: SpeechRequest,
    *,
    settings,
    communicator_factory: Callable[..., Any] | None = None,
    capability: str = "tts",
) -> SpeechResult:
    endpoint = _resolve_speech_endpoint(request, settings)
    emit_event(
        log_events.GATEWAY_SPEECH_START,
        capability=capability,
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
    )
    t0 = time.perf_counter()
    try:
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
    except Exception as exc:
        duration_ms = int((time.perf_counter() - t0) * 1000)
        emit_event(
            log_events.GATEWAY_SPEECH_FAILED,
            level=logging.ERROR,
            capability=capability,
            provider=endpoint.provider,
            model=endpoint.model,
            adapter=endpoint.adapter,
            duration_ms=duration_ms,
            status="error",
            fatal=True,
            **classify_error(exc),
        )
        raise
    duration_ms = int((time.perf_counter() - t0) * 1000)
    emit_event(
        log_events.GATEWAY_SPEECH_DONE,
        capability=capability,
        provider=endpoint.provider,
        model=endpoint.model,
        adapter=endpoint.adapter,
        duration_ms=duration_ms,
        status="ok",
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
    endpoint = resolve_capability_model_endpoint(capability="narration", settings=settings)
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
    return _generate_chat(
        request,
        settings=settings,
        client_factory=client_factory,
        capability="narration",
    )


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
    endpoint = resolve_capability_model_endpoint(capability="polish", settings=settings)
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
    return _generate_chat(
        request,
        settings=settings,
        client_factory=client_factory,
        capability="polish",
    )


def embed_texts_for_capability(
    *,
    texts,
    settings,
    batch_size: int | None = None,
    timeout_sec: float | None = None,
    meta=None,
    client_factory: Callable[[str, str | None], Any] | None = None,
) -> EmbeddingResult:
    endpoint = resolve_capability_model_endpoint(capability="embedding", settings=settings)
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
    return _embed_texts(request, settings=settings, client_factory=client_factory)


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
    endpoint = resolve_capability_model_endpoint(capability="tts", settings=settings)
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
    return _synthesize_speech(
        request,
        settings=settings,
        communicator_factory=communicator_factory,
    )
