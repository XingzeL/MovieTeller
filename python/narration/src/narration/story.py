from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable

from model_gateway import generate_chat
from model_gateway.types import ChatRequest

if TYPE_CHECKING:
    from movieteller_config.schema import Settings


def _resolve_provider_slug(
    settings: "Settings", provider_slug: str | None
) -> str:
    slug = (provider_slug or settings.narration_provider).strip().lower()
    return slug or "openai"


def generate_narration(
    *,
    system_message: str,
    user_text: str,
    frames_base64_png: list[str],
    model: str,
    settings: "Settings",
    provider_slug: str | None = None,
    client_factory: Callable[..., Any] | None = None,
) -> str:
    """
    Call chat completions (OpenAI-compatible SDK) with text + inline PNG images.

    Provider comes from ``provider_slug`` or ``settings.narration_provider`` (must match
    ``api_keys`` / ``api_base_urls`` / ``narration_provider_models`` /
    ``narration_provider_model_catalog`` slugs in movieteller_config).
    """
    slug = _resolve_provider_slug(settings, provider_slug)
    print(
        "[narration.api] "
        f"slug={slug!r} "
        f"model={model!r} "
        f"base_url={settings.get_api_base_url(slug)!r} "
        f"frames={len(frames_base64_png)}",
        file=sys.stderr,
    )
    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for b64 in frames_base64_png:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )

    result = generate_chat(
        ChatRequest(
            provider=slug,
            model=model,
            messages=[
                {"role": "system", "content": system_message},
                {"role": "user", "content": content},
            ],
        ),
        settings=settings,
        client_factory=client_factory,
    )
    text = result.text.strip()
    if not text:
        raise RuntimeError("Model returned empty narration text")
    return text
