from __future__ import annotations

import os
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Mapping, Sequence

_ENV_REF_BRACE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_ENV_REF_DOLLAR = re.compile(r"^\$\$([A-Za-z_][A-Za-z0-9_]*)$")
_ENV_REF_SINGLE = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


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
    videocaptioner_asr: str
    videocaptioner_language: str
    videocaptioner_transcribe_timeout_ms: int | None
    narration_api_url: str | None
    narration_provider: str
    api_keys: Mapping[str, str]
    api_base_urls: Mapping[str, str]
    # Narration-scoped single model per slug.
    narration_provider_models: Mapping[str, str]
    # Narration-scoped slug -> ordered model ids.
    narration_provider_model_catalog: Mapping[str, tuple[str, ...]]
    # Narration-polish-scoped single model per slug.
    narration_polish_provider_models: Mapping[str, str]
    # Narration-polish-scoped slug -> ordered model ids.
    narration_polish_provider_model_catalog: Mapping[str, tuple[str, ...]]
    # When set, overrides model for narration_provider only (NARRATION_MODEL).
    narration_model: str | None
    # Catalog index for narration_provider when narration_model unset (NARRATION_MODEL_INDEX).
    narration_model_index: int
    narration_polish_enabled: bool
    narration_polish_provider: str | None
    narration_polish_model: str | None
    narration_polish_model_index: int
    narration_polish_target_wpm: int
    narration_polish_cefr_level: str
    narration_polish_strength: str
    narration_polish_safety_margin_sec: float
    narration_speech_enabled: bool
    narration_speech_provider: str
    narration_speech_voice: str
    narration_speech_rate: str
    narration_speech_volume: str
    narration_speech_pitch: str
    narration_speech_boundary: str
    narration_video_background_audio_volume: float
    narration_video_speech_audio_volume: float

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

    def _resolve_model_from_sources(
        self,
        *,
        provider: str,
        primary_model_override: str | None,
        primary_provider: str,
        primary_index: int,
        scoped_models: Mapping[str, str],
        scoped_catalog: Mapping[str, tuple[str, ...]],
    ) -> str:
        slug = provider.strip().lower()
        if not slug:
            return self.narration_image_model
        if slug == primary_provider:
            if m := _none_if_empty(primary_model_override):
                return m
        if m := scoped_models.get(slug):
            s = m.strip()
            if s:
                return s
        cat = scoped_catalog.get(slug)
        if cat:
            idx = primary_index if slug == primary_provider else 0
            if idx < 0:
                idx = 0
            if idx < len(cat):
                return cat[idx]
            return cat[0]
        return self.narration_image_model

    def model_for_provider(self, provider: str) -> str:
        """
        Resolve model id for ``provider``.

        Narration-scoped resolver.

        Order:
        1. ``NARRATION_MODEL`` when ``provider`` equals ``narration_provider``
        2. ``narration_provider_models`` / ``narration_provider_model_catalog``
        3. ``narration_image_model`` fallback
        """
        return self._resolve_model_from_sources(
            provider=provider,
            primary_model_override=self.narration_model,
            primary_provider=self.narration_provider.strip().lower() or "openai",
            primary_index=self.narration_model_index,
            scoped_models=self.narration_provider_models,
            scoped_catalog=self.narration_provider_model_catalog,
        )

    def polish_provider(self) -> str:
        slug = _none_if_empty(self.narration_polish_provider)
        if slug:
            return slug.strip().lower()
        np = self.narration_provider.strip().lower()
        return np or "openai"

    def polish_model_for_provider(self, provider: str | None = None) -> str:
        slug = (provider or self.polish_provider()).strip().lower()
        return self._resolve_model_from_sources(
            provider=slug,
            primary_model_override=self.narration_polish_model,
            primary_provider=self.polish_provider(),
            primary_index=self.narration_polish_model_index,
            scoped_models=self.narration_polish_provider_models,
            scoped_catalog=self.narration_polish_provider_model_catalog,
        )


def _coerce_int(value: Any, fallback: int) -> int:
    if value is None:
        return fallback
    return int(value)


def _coerce_float(value: Any, fallback: float) -> float:
    if value is None:
        return fallback
    return float(value)


def _coerce_bool(value: Any, fallback: bool) -> bool:
    if value is None:
        return fallback
    if isinstance(value, bool):
        return value
    s = str(value).strip().lower()
    if not s:
        return fallback
    if s in _TRUE_VALUES:
        return True
    if s in _FALSE_VALUES:
        return False
    return fallback


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
    narration_provider_models = _normalize_provider_models(
        {"provider_models": data.get("narration_provider_models")}
    )
    narration_provider_catalog = _normalize_provider_model_catalog(
        {"provider_model_catalog": data.get("narration_provider_model_catalog")}
    )
    narration_polish_provider_models = _normalize_provider_models(
        {"provider_models": data.get("narration_polish_provider_models")}
    )
    narration_polish_provider_catalog = _normalize_provider_model_catalog(
        {"provider_model_catalog": data.get("narration_polish_provider_model_catalog")}
    )
    idx_raw = data.get("narration_model_index")
    try:
        narration_model_index = max(0, int(idx_raw)) if idx_raw is not None else 0
    except (TypeError, ValueError):
        narration_model_index = 0
    polish_idx_raw = data.get("narration_polish_model_index")
    try:
        narration_polish_model_index = (
            max(0, int(polish_idx_raw)) if polish_idx_raw is not None else 0
        )
    except (TypeError, ValueError):
        narration_polish_model_index = 0
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
        videocaptioner_asr=str(data.get("videocaptioner_asr") or "bijian").strip().lower()
        or "bijian",
        videocaptioner_language=str(data.get("videocaptioner_language") or "auto").strip()
        or "auto",
        videocaptioner_transcribe_timeout_ms=(
            _coerce_int(data.get("videocaptioner_transcribe_timeout_ms"), 0)
            if data.get("videocaptioner_transcribe_timeout_ms") is not None
            and str(data.get("videocaptioner_transcribe_timeout_ms")).strip() != ""
            else None
        ),
        narration_api_url=_none_if_empty(data.get("narration_api_url")),
        narration_provider=str(data.get("narration_provider") or "openai").strip().lower()
        or "openai",
        api_keys=MappingProxyType(dict(api_keys)),
        api_base_urls=MappingProxyType(dict(api_base_urls)),
        narration_provider_models=MappingProxyType(dict(narration_provider_models)),
        narration_provider_model_catalog=MappingProxyType(
            dict(narration_provider_catalog)
        ),
        narration_polish_provider_models=MappingProxyType(
            dict(narration_polish_provider_models)
        ),
        narration_polish_provider_model_catalog=MappingProxyType(
            dict(narration_polish_provider_catalog)
        ),
        narration_model=_expand_optional_env_str(data.get("narration_model")),
        narration_model_index=narration_model_index,
        narration_polish_enabled=_coerce_bool(
            data.get("narration_polish_enabled"), False
        ),
        narration_polish_provider=_none_if_empty(
            _expand_optional_env_str(data.get("narration_polish_provider"))
        ),
        narration_polish_model=_expand_optional_env_str(
            data.get("narration_polish_model")
        ),
        narration_polish_model_index=narration_polish_model_index,
        narration_polish_target_wpm=max(
            1, _coerce_int(data.get("narration_polish_target_wpm"), 150)
        ),
        narration_polish_cefr_level=(
            str(data.get("narration_polish_cefr_level") or "B1").strip().upper()
            or "B1"
        ),
        narration_polish_strength=(
            str(data.get("narration_polish_strength") or "medium").strip().lower()
            or "medium"
        ),
        narration_polish_safety_margin_sec=max(
            0.0,
            _coerce_float(data.get("narration_polish_safety_margin_sec"), 0.2),
        ),
        narration_speech_enabled=_coerce_bool(
            data.get("narration_speech_enabled"), False
        ),
        narration_speech_provider=(
            str(data.get("narration_speech_provider") or "edge_tts").strip().lower()
            or "edge_tts"
        ),
        narration_speech_voice=(
            str(
                data.get("narration_speech_voice")
                or "en-US-EmmaMultilingualNeural"
            ).strip()
            or "en-US-EmmaMultilingualNeural"
        ),
        narration_speech_rate=(
            str(data.get("narration_speech_rate") or "+0%").strip() or "+0%"
        ),
        narration_speech_volume=(
            str(data.get("narration_speech_volume") or "+0%").strip() or "+0%"
        ),
        narration_speech_pitch=(
            str(data.get("narration_speech_pitch") or "+0Hz").strip() or "+0Hz"
        ),
        narration_speech_boundary=(
            str(data.get("narration_speech_boundary") or "SentenceBoundary").strip()
            or "SentenceBoundary"
        ),
        narration_video_background_audio_volume=max(
            0.0,
            _coerce_float(data.get("narration_video_background_audio_volume"), 0.35),
        ),
        narration_video_speech_audio_volume=max(
            0.0,
            _coerce_float(data.get("narration_video_speech_audio_volume"), 1.0),
        ),
    )
