from __future__ import annotations

import os
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

_ENV_REF_BRACE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_ENV_REF_DOLLAR = re.compile(r"^\$\$([A-Za-z_][A-Za-z0-9_]*)$")
_ENV_REF_SINGLE = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")


def expand_env_placeholder(value: str) -> str:
    """
    If ``value`` is exactly ``${VAR}``, ``$$VAR``, or ``$VAR``, replace with
    ``os.environ.get(VAR,'')``. Otherwise return the trimmed literal string.
    """
    s = value.strip()
    m = _ENV_REF_BRACE.match(s) or _ENV_REF_DOLLAR.match(s) or _ENV_REF_SINGLE.match(s)
    if not m:
        return s
    return os.environ.get(m.group(1), "").strip()


def _none_if_empty(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None


def _expand_optional_env_str(value: Any) -> str | None:
    if value is None:
        return None
    return _none_if_empty(expand_env_placeholder(str(value)))


@dataclass(frozen=True)
class Settings:
    """Resolved configuration for MovieTeller Python components."""

    openai_api_key: str | None
    openai_base_url: str | None
    narration_image_model: str
    max_frames_per_segment: int
    narration_frame_max_edge: int
    ffmpeg_path: str
    default_prompt_style: str
    videocaptioner_bin: str | None
    narration_api_url: str | None
    narration_provider: str
    api_keys: Mapping[str, str]
    api_base_urls: Mapping[str, str]
    # Legacy single model per slug (PROVIDER_MODELS_JSON / provider_models).
    provider_models: Mapping[str, str]
    # Slug -> multiple model ids (provider_model_catalog / PROVIDER_MODEL_CATALOG_JSON).
    provider_model_catalog: Mapping[str, tuple[str, ...]]
    # When set, overrides model for narration_provider only (NARRATION_MODEL).
    narration_model: str | None
    # Catalog index for narration_provider when narration_model unset (NARRATION_MODEL_INDEX).
    narration_model_index: int

    def get_api_key(self, provider: str) -> str | None:
        """Return key for a provider slug (e.g. \"openai\", \"anthropic\", \"gemini\")."""
        k = provider.strip().lower()
        if not k:
            return None
        v = self.api_keys.get(k)
        return v.strip() if v else None

    def require_api_key(self, provider: str) -> str:
        v = self.get_api_key(provider)
        if not v:
            raise ValueError(
                f"API key for provider '{provider}' is not configured. "
                "Use API_KEYS_JSON, OPENAI_API_KEY, ANTHROPIC_API_KEY, etc., or api_keys in YAML."
            )
        return v

    def require_openai(self) -> str:
        """Backward-compatible alias for OpenAI."""
        return self.require_api_key("openai")

    def get_api_base_url(self, provider: str) -> str | None:
        """Chat/inference base URL for a provider (e.g. OpenAI-compatible root ending in /v1)."""
        k = provider.strip().lower()
        if not k:
            return None
        v = self.api_base_urls.get(k)
        return v.strip() if v else None

    def model_for_provider(self, provider: str) -> str:
        """
        Resolve model id for ``provider``.

        Order: ``NARRATION_MODEL`` (only when ``provider`` equals ``narration_provider``),
        ``provider_models`` slug entry, first catalog entry for slug (or indexed entry for
        ``narration_provider`` via ``narration_model_index``), else ``narration_image_model``.
        """
        k = provider.strip().lower()
        np = self.narration_provider.strip().lower()
        if k:
            if k == np:
                if m := _none_if_empty(self.narration_model):
                    return m
            if m := self.provider_models.get(k):
                s = m.strip()
                if s:
                    return s
            cat = self.provider_model_catalog.get(k)
            if cat:
                idx = self.narration_model_index if k == np else 0
                if idx < 0:
                    idx = 0
                if idx < len(cat):
                    return cat[idx]
                return cat[0]
        return self.narration_image_model


def _coerce_int(value: Any, fallback: int) -> int:
    if value is None:
        return fallback
    return int(value)


def _normalize_api_keys_dict(data: dict[str, Any]) -> dict[str, str]:
    """Build lowercase provider -> secret string from yaml/env merged dict."""
    raw: dict[str, str] = {}
    nested = data.get("api_keys")
    if isinstance(nested, dict):
        for k, v in nested.items():
            if v is None:
                continue
            expanded = expand_env_placeholder(str(v))
            if not expanded:
                continue
            raw[str(k).strip().lower()] = expanded
    if v := _expand_optional_env_str(data.get("openai_api_key")):
        raw.setdefault("openai", v)
    return raw


def _normalize_api_base_urls(data: dict[str, Any]) -> dict[str, str]:
    """Provider slug -> base URL (OpenAI SDK usually expects .../v1 without /chat/completions)."""
    raw: dict[str, str] = {}
    nested = data.get("api_base_urls")
    if isinstance(nested, dict):
        for k, v in nested.items():
            if v is None:
                continue
            expanded = expand_env_placeholder(str(v))
            if not expanded:
                continue
            raw[str(k).strip().lower()] = expanded
    if v := _expand_optional_env_str(data.get("openai_base_url")):
        raw.setdefault("openai", v)
    return raw


def _normalize_provider_models(data: dict[str, Any]) -> dict[str, str]:
    """Provider slug -> model id (e.g. openai -> gpt-4o-mini, modelscope -> qwen/Qwen-VL-Max)."""
    raw: dict[str, str] = {}
    nested = data.get("provider_models")
    if isinstance(nested, dict):
        for k, v in nested.items():
            if v is None:
                continue
            expanded = expand_env_placeholder(str(v))
            if not expanded:
                continue
            raw[str(k).strip().lower()] = expanded
    return raw


def _normalize_provider_model_catalog(data: dict[str, Any]) -> dict[str, tuple[str, ...]]:
    """Provider slug -> ordered model ids (OpenAI ``model`` field values)."""
    raw: dict[str, tuple[str, ...]] = {}
    nested = data.get("provider_model_catalog")
    if isinstance(nested, dict):
        for k, v in nested.items():
            slug = str(k).strip().lower()
            if not slug:
                continue
            seq: Sequence[Any]
            if isinstance(v, list):
                seq = v
            elif isinstance(v, tuple):
                seq = v
            else:
                continue
            ids: list[str] = []
            for item in seq:
                if item is None:
                    continue
                expanded = expand_env_placeholder(str(item))
                if expanded:
                    ids.append(expanded)
            if ids:
                raw[slug] = tuple(ids)
    return raw


def settings_from_dict(data: dict[str, Any]) -> Settings:
    api_keys = _normalize_api_keys_dict(data)
    api_base_urls = _normalize_api_base_urls(data)
    provider_models = _normalize_provider_models(data)
    catalog = _normalize_provider_model_catalog(data)
    idx_raw = data.get("narration_model_index")
    try:
        narration_model_index = max(0, int(idx_raw)) if idx_raw is not None else 0
    except (TypeError, ValueError):
        narration_model_index = 0
    openai = api_keys.get("openai") or _expand_optional_env_str(data.get("openai_api_key"))
    return Settings(
        openai_api_key=openai,
        openai_base_url=_expand_optional_env_str(data.get("openai_base_url")),
        narration_image_model=str(data.get("narration_image_model") or "gpt-4o-mini"),
        max_frames_per_segment=_coerce_int(data.get("max_frames_per_segment"), 24),
        narration_frame_max_edge=_coerce_int(data.get("narration_frame_max_edge"), 768),
        ffmpeg_path=str(data.get("ffmpeg_path") or "ffmpeg"),
        default_prompt_style=str(data.get("default_prompt_style") or "documentary"),
        videocaptioner_bin=_none_if_empty(data.get("videocaptioner_bin")),
        narration_api_url=_none_if_empty(data.get("narration_api_url")),
        narration_provider=str(data.get("narration_provider") or "openai").strip().lower()
        or "openai",
        api_keys=MappingProxyType(dict(api_keys)),
        api_base_urls=MappingProxyType(dict(api_base_urls)),
        provider_models=MappingProxyType(dict(provider_models)),
        provider_model_catalog=MappingProxyType(dict(catalog)),
        narration_model=_expand_optional_env_str(data.get("narration_model")),
        narration_model_index=narration_model_index,
    )
