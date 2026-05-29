from __future__ import annotations

from typing import Any, Callable, Mapping

from model_gateway.errors import GatewayProviderError
from model_gateway.router import ResolvedEndpoint
from model_gateway.types import (
    ChatMessage,
    ChatRequest,
    ChatResult,
    EmbeddingRequest,
    EmbeddingResult,
    GatewayResponseMeta,
    MessagePart,
    UsageInfo,
)


def openai_sdk_client_factory(api_key: str, base_url: str | None) -> Any:
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _message_part_to_dict(part: MessagePart | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(part, Mapping):
        return dict(part)
    payload: dict[str, Any] = {"type": part.type}
    if part.text is not None:
        payload["text"] = part.text
    if part.image_url is not None:
        payload["image_url"] = {"url": part.image_url}
    if part.media_type is not None:
        payload["media_type"] = part.media_type
    return payload


def _chat_message_to_dict(message: ChatMessage | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(message, Mapping):
        return dict(message)
    content = message.content
    if isinstance(content, str):
        normalized_content: Any = content
    else:
        normalized_content = [_message_part_to_dict(part) for part in content]
    return {"role": message.role, "content": normalized_content}


def _usage_from_response(resp: object) -> UsageInfo | None:
    usage = getattr(resp, "usage", None)
    if usage is None:
        return None
    return UsageInfo(
        prompt_tokens=getattr(usage, "prompt_tokens", None),
        completion_tokens=getattr(usage, "completion_tokens", None),
        total_tokens=getattr(usage, "total_tokens", None),
    )


def generate_chat(
    request: ChatRequest,
    endpoint: ResolvedEndpoint,
    *,
    client_factory: Callable[[str, str | None], Any] | None = None,
) -> ChatResult:
    factory = client_factory or openai_sdk_client_factory
    client = factory(str(endpoint.api_key or ""), endpoint.base_url)
    kwargs: dict[str, Any] = {
        "model": endpoint.model,
        "messages": [_chat_message_to_dict(message) for message in request.messages],
    }
    if request.temperature is not None:
        kwargs["temperature"] = request.temperature
    if request.max_tokens is not None:
        kwargs["max_tokens"] = request.max_tokens
    if request.timeout_sec is not None:
        kwargs["timeout"] = request.timeout_sec
    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as exc:  # pragma: no cover - SDK-specific failures
        raise GatewayProviderError(str(exc)) from exc
    choices = getattr(resp, "choices", None) or ()
    if not choices:
        raise GatewayProviderError("Model returned no choices")
    choice = choices[0]
    content = (getattr(getattr(choice, "message", None), "content", None) or "").strip()
    return ChatResult(
        text=content,
        finish_reason=getattr(choice, "finish_reason", None),
        usage=_usage_from_response(resp),
        meta=GatewayResponseMeta(
            provider=endpoint.provider,
            model=endpoint.model,
            request_id=getattr(resp, "id", None),
        ),
        raw=resp,
    )


def embed_texts(
    request: EmbeddingRequest,
    endpoint: ResolvedEndpoint,
    *,
    client_factory: Callable[[str, str | None], Any] | None = None,
) -> EmbeddingResult:
    factory = client_factory or openai_sdk_client_factory
    client = factory(str(endpoint.api_key or ""), endpoint.base_url)
    kwargs: dict[str, Any] = {"model": endpoint.model, "input": list(request.texts)}
    if request.timeout_sec is not None:
        kwargs["timeout"] = request.timeout_sec
    try:
        resp = client.embeddings.create(**kwargs)
    except Exception as exc:  # pragma: no cover - SDK-specific failures
        raise GatewayProviderError(str(exc)) from exc
    data = getattr(resp, "data", None) or ()
    return EmbeddingResult(
        vectors=tuple(tuple(float(x) for x in row.embedding) for row in data),
        usage=_usage_from_response(resp),
        meta=GatewayResponseMeta(
            provider=endpoint.provider,
            model=endpoint.model,
            request_id=getattr(resp, "id", None),
        ),
        raw=resp,
    )
