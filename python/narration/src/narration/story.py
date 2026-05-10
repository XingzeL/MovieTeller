from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable

if TYPE_CHECKING:
    from movieteller_config.schema import Settings


def _openai_sdk_client_factory(api_key: str, base_url: str | None) -> Any:
    """OpenAI Python SDK (works with any OpenAI-compatible HTTP API)."""
    from openai import OpenAI

    kwargs: dict[str, Any] = {"api_key": api_key}
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def _resolve_provider_slug(
    settings: "Settings", provider_slug: str | None
) -> str:
    slug = (provider_slug or settings.narration_provider).strip().lower()
    return slug or "openai"


def _resolve_base_url(settings: "Settings", slug: str) -> str | None:
    base_url = settings.get_api_base_url(slug)
    if slug == "openai" and not base_url:
        return settings.openai_base_url
    return base_url


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
    api_key = settings.require_api_key(slug)
    base_url = _resolve_base_url(settings, slug)
    print(
        f"[narration] slug={slug!r} model={model!r} base_url={base_url!r}",
        file=sys.stderr,
    )
    factory = client_factory or _openai_sdk_client_factory
    client = factory(api_key, base_url)

    content: list[dict[str, Any]] = [{"type": "text", "text": user_text}]
    for b64 in frames_base64_png:
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"},
            }
        )

    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_message},
            {"role": "user", "content": content},
        ],
    )
    choice = resp.choices[0]
    text = (choice.message.content or "").strip()
    if not text:
        raise RuntimeError("Model returned empty narration text")
    return text
