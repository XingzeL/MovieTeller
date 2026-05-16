from __future__ import annotations

import json
import re
from urllib.parse import urlparse
from pathlib import Path
from typing import Any, Callable

from model_gateway.adapters.openai_compatible import openai_sdk_client_factory
from model_gateway.errors import GatewayConfigError, GatewayProviderError
from model_gateway.router import ResolvedEndpoint
from model_gateway.types import GatewayResponseMeta, SpeechRequest, SpeechResult


def _parse_edge_style_percent(value: str | None, *, default: float) -> float:
    """Map edge-tts style ``+12%`` / ``-5%`` to a multiplier-ish speed hint for ``audio.speech``."""
    if not value:
        return default
    s = str(value).strip()
    m = re.match(r"^([+-]?\d+(?:\.\d+)?)\s*%$", s)
    if not m:
        return default
    try:
        pct = float(m.group(1))
    except ValueError:
        return default
    return max(0.25, min(4.0, 1.0 + pct / 100.0))


def _validate_openai_compatible_tts_base_url(endpoint: ResolvedEndpoint) -> None:
    base_url = str(endpoint.base_url or "").strip()
    if not base_url:
        raise GatewayConfigError(
            f"{endpoint.provider} TTS requires an OpenAI-compatible base URL."
        )
    host = (urlparse(base_url).netloc or "").lower()
    if "openspeech.bytedance.com" in host:
        raise GatewayConfigError(
            "Configured TTS base URL points to ByteDance OpenSpeech "
            f"({base_url}), but the current '{endpoint.provider}' adapter uses "
            "OpenAI-compatible audio.speech. "
            "Use provider 'volcengine' with an Ark-compatible base URL such as "
            "'https://ark.cn-beijing.volces.com/api/v3', or switch to 'edge_tts'."
        )


def synthesize_speech(
    request: SpeechRequest,
    endpoint: ResolvedEndpoint,
    *,
    client_factory: Callable[..., Any] | None = None,
) -> SpeechResult:
    """Volcengine Ark (or compatible) OpenAI-style ``audio.speech``."""
    if not request.output_path:
        raise GatewayConfigError("speech output_path is required")
    factory = client_factory or openai_sdk_client_factory
    model = (str(request.model or "").strip() or str(endpoint.model or "").strip()).strip()
    if not model:
        raise GatewayConfigError(
            "Volcengine TTS requires narration_tts_model (YAML / env NARRATION_TTS_MODEL) "
            "so the gateway can pass ``model`` to audio.speech."
        )
    _validate_openai_compatible_tts_base_url(endpoint)
    voice = str(request.voice or "").strip()
    if not voice:
        raise GatewayConfigError("speech voice is empty (set narration_speech_voice or tts_provider_model_catalog)")

    kwargs: dict[str, Any] = {
        "model": model,
        "voice": voice,  # type: ignore[arg-type]
        "input": str(request.text),
        "response_format": "mp3",
    }
    speed = _parse_edge_style_percent(request.rate, default=1.0)
    if speed != 1.0:
        kwargs["speed"] = speed
    if request.timeout_sec is not None:
        kwargs["timeout"] = float(request.timeout_sec)

    try:
        client = factory(str(endpoint.api_key or ""), endpoint.base_url)
        response = client.audio.speech.create(**kwargs)
        Path(request.output_path).parent.mkdir(parents=True, exist_ok=True)
        response.write_to_file(str(request.output_path))
    except GatewayConfigError:
        raise
    except Exception as exc:  # pragma: no cover - provider/runtime-specific failures
        raise GatewayProviderError(str(exc)) from exc

    if request.metadata_path:
        meta_path = Path(request.metadata_path)
        meta_path.parent.mkdir(parents=True, exist_ok=True)
        meta_path.write_text(
            json.dumps({"provider": endpoint.provider, "model": model, "voice": voice}),
            encoding="utf-8",
        )

    return SpeechResult(
        audio_path=str(request.output_path),
        boundary_path=(str(request.metadata_path) if request.metadata_path else None),
        meta=GatewayResponseMeta(
            provider=endpoint.provider,
            model=model,
        ),
        raw=None,
    )
