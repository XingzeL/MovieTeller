from __future__ import annotations

import sys
from typing import TYPE_CHECKING, Any, Callable

from model_gateway import generate_narration as gateway_generate_narration

if TYPE_CHECKING:
    from movieteller_config.schema import Settings


def generate_narration(
    *,
    system_message: str,
    user_text: str,
    frames_base64_png: list[str],
    settings: "Settings",
    client_factory: Callable[..., Any] | None = None,
) -> str:
    """
    Generate narration through the gateway narration capability.
    """
    default_provider = settings.default_provider()
    default_model = settings.default_model_for_capability("narration")
    print(
        "[narration.api] "
        f"slug={default_provider!r} "
        f"model={default_model!r} "
        f"base_url={settings.get_api_base_url(default_provider)!r} "
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

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": content},
    ]
    result = gateway_generate_narration(
        messages=messages,
        settings=settings,
        client_factory=client_factory,
    )
    text = result.text.strip()
    if not text:
        raise RuntimeError("Model returned empty narration text")
    return text
