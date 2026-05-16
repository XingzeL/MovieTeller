from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence


@dataclass(frozen=True)
class RequestMeta:
    module: str
    capability: str
    job_id: str | None = None
    chunk_id: str | None = None
    segment_id: str | None = None
    user_id: str | None = None
    trace_id: str | None = None
    extra: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MessagePart:
    type: str
    text: str | None = None
    image_url: str | None = None
    media_type: str | None = None


@dataclass(frozen=True)
class ChatMessage:
    role: str
    content: str | Sequence[MessagePart]


@dataclass(frozen=True)
class ChatRequest:
    provider: str
    model: str
    messages: Sequence[ChatMessage | Mapping[str, Any]]
    temperature: float | None = None
    max_tokens: int | None = None
    timeout_sec: float | None = None
    response_format: str | None = None
    meta: RequestMeta | None = None


@dataclass(frozen=True)
class EmbeddingRequest:
    provider: str
    model: str
    texts: Sequence[str]
    batch_size: int | None = None
    timeout_sec: float | None = None
    meta: RequestMeta | None = None


@dataclass(frozen=True)
class SpeechRequest:
    provider: str
    voice: str
    text: str
    """TTS model id for OpenAI-compatible ``audio.speech`` (e.g. Ark). Ignored by edge-tts."""
    model: str | None = None
    rate: str | None = None
    volume: str | None = None
    pitch: str | None = None
    boundary: str | None = None
    output_path: str | None = None
    metadata_path: str | None = None
    timeout_sec: float | None = None
    meta: RequestMeta | None = None


@dataclass(frozen=True)
class UsageInfo:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost: float | None = None


@dataclass(frozen=True)
class GatewayResponseMeta:
    provider: str
    model: str
    request_id: str | None = None
    retry_count: int = 0
    latency_sec: float | None = None


@dataclass(frozen=True)
class ChatResult:
    text: str
    finish_reason: str | None
    usage: UsageInfo | None
    meta: GatewayResponseMeta
    raw: object | None = None


@dataclass(frozen=True)
class EmbeddingResult:
    vectors: tuple[tuple[float, ...], ...]
    usage: UsageInfo | None
    meta: GatewayResponseMeta
    raw: object | None = None


@dataclass(frozen=True)
class SpeechResult:
    audio_path: str
    boundary_path: str | None = None
    meta: GatewayResponseMeta | None = None
    raw: object | None = None
