from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Callable
from urllib.request import urlopen

from model_gateway.errors import GatewayConfigError, GatewayProviderError
from model_gateway.router import ResolvedEndpoint
from model_gateway.types import GatewayResponseMeta, SpeechRequest, SpeechResult


def dashscope_client_factory(api_key: str) -> Any:
    import dashscope

    return dashscope


def synthesize_speech(
    request: SpeechRequest,
    endpoint: ResolvedEndpoint,
    *,
    client_factory: Callable[..., Any] | None = None,
) -> SpeechResult:
    if not request.output_path:
        raise GatewayConfigError("speech output_path is required")
    model = (str(request.model or "").strip() or str(endpoint.model or "").strip()).strip()
    if not model:
        raise GatewayConfigError(
            "TTS model is not configured. "
            "Set model_defaults.tts so the gateway can pass a qwen-tts model to DashScope."
        )
    voice = str(request.voice or "").strip()
    if not voice:
        raise GatewayConfigError("speech voice is empty (set tts_defaults.voice or pass voice explicitly)")

    try:
        client = (client_factory or dashscope_client_factory)(str(endpoint.api_key or ""))
        if endpoint.base_url:
            setattr(client, "base_http_api_url", str(endpoint.base_url).strip())
        response = client.audio.qwen_tts.SpeechSynthesizer.call(
            model=model,
            api_key=str(endpoint.api_key or ""),
            text=str(request.text),
            voice=voice,
        )
    except GatewayConfigError:
        raise
    except Exception as exc:  # pragma: no cover - provider/runtime-specific failures
        raise GatewayProviderError(str(exc)) from exc

    status_code = getattr(response, "status_code", None)
    if status_code is not None and int(status_code) >= 400:
        raise GatewayProviderError(
            "DashScope TTS request failed: "
            f"status_code={status_code} "
            f"code={getattr(response, 'code', None)!r} "
            f"message={getattr(response, 'message', None)!r}"
        )

    output_path = Path(request.output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    audio_bytes = _extract_audio_bytes(response)
    if audio_bytes is None:
        raise GatewayProviderError(f"DashScope TTS returned no audio payload: {response!r}")
    output_path.write_bytes(audio_bytes)

    if request.metadata_path:
        meta_path = Path(request.metadata_path)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps({"provider": endpoint.provider, "model": model, "voice": voice}),
            encoding="utf-8",
        )

    return SpeechResult(
        audio_path=str(output_path),
        boundary_path=(str(request.metadata_path) if request.metadata_path else None),
        meta=GatewayResponseMeta(
            provider=endpoint.provider,
            model=model,
        ),
        raw=response,
    )


def _extract_audio_bytes(response: Any) -> bytes | None:
    output = getattr(response, "output", None)
    data = _coerce_audio_bytes(output)
    if data is not None:
        return data
    audio_url = _extract_audio_url(output)
    if audio_url:
        with urlopen(audio_url) as resp:  # nosec - provider-supplied signed URL
            return resp.read()
    candidates = (
        getattr(response, "output_audio", None),
        getattr(response, "audio", None),
        getattr(response, "audio_data", None),
        getattr(response, "data", None),
    )
    for value in candidates:
        data = _coerce_audio_bytes(value)
        if data is not None:
            return data
    return None


def _coerce_audio_bytes(value: Any) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        return value
    if isinstance(value, bytearray):
        return bytes(value)
    if isinstance(value, memoryview):
        return value.tobytes()
    if isinstance(value, dict):
        for key in ("audio", "audio_data", "output_audio", "data"):
            if key in value:
                data = _coerce_audio_bytes(value[key])
                if data is not None:
                    return data
    return None


def _extract_audio_url(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, dict):
        audio = value.get("audio")
        if isinstance(audio, dict):
            url = audio.get("url")
            if isinstance(url, str) and url.strip():
                return url.strip()
    audio = getattr(value, "audio", None)
    if isinstance(audio, dict):
        url = audio.get("url")
        if isinstance(url, str) and url.strip():
            return url.strip()
    return None
