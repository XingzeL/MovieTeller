from __future__ import annotations

import asyncio
from typing import Any, Callable

from edge_tts import Communicate

from model_gateway.errors import GatewayProviderError
from model_gateway.router import ResolvedEndpoint
from model_gateway.types import GatewayResponseMeta, SpeechRequest, SpeechResult


def communicator_factory(
    text: str,
    voice: str,
    *,
    rate: str,
    volume: str,
    pitch: str,
    boundary: str,
) -> Any:
    return Communicate(
        text,
        voice,
        rate=rate,
        volume=volume,
        pitch=pitch,
        boundary=boundary,
    )


def synthesize_speech(
    request: SpeechRequest,
    endpoint: ResolvedEndpoint,
    *,
    communicator_factory_override: Callable[..., Any] | None = None,
) -> SpeechResult:
    factory = communicator_factory_override or communicator_factory
    communicate = factory(
        request.text,
        request.voice,
        rate=str(request.rate or "+0%"),
        volume=str(request.volume or "+0%"),
        pitch=str(request.pitch or "+0Hz"),
        boundary=str(request.boundary or "SentenceBoundary"),
    )
    if not request.output_path:
        raise GatewayProviderError("speech output_path is required")
    async def _save() -> None:
        await communicate.save(
            str(request.output_path),
            str(request.metadata_path) if request.metadata_path else None,
        )

    try:
        if request.timeout_sec is not None:
            asyncio.run(asyncio.wait_for(_save(), timeout=float(request.timeout_sec)))
        else:
            asyncio.run(_save())
    except TimeoutError as exc:
        raise GatewayProviderError(f"TTS timed out after {request.timeout_sec}s") from exc
    except Exception as exc:  # pragma: no cover - provider/runtime-specific failures
        raise GatewayProviderError(str(exc)) from exc
    return SpeechResult(
        audio_path=str(request.output_path),
        boundary_path=(str(request.metadata_path) if request.metadata_path else None),
        meta=GatewayResponseMeta(
            provider=endpoint.provider,
            model=endpoint.model,
        ),
        raw=None,
    )
