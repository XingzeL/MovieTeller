from __future__ import annotations

import os
import re
from dataclasses import dataclass
from types import MappingProxyType
from typing import Any, Literal, Mapping

_ENV_REF_BRACE = re.compile(r"^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$")
_ENV_REF_DOLLAR = re.compile(r"^\$\$([A-Za-z_][A-Za-z0-9_]*)$")
_ENV_REF_SINGLE = re.compile(r"^\$([A-Za-z_][A-Za-z0-9_]*)$")
_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


def expand_env_placeholder(value: str) -> str:
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


def _looks_like_explicit_nested_tts_defaults(data: dict[str, Any]) -> bool:
    cfg = data.get("tts_defaults")
    if not isinstance(cfg, dict):
        return False
    return any(cfg.get(key) is not None for key in ("voice", "rate", "volume", "pitch", "boundary"))


def _looks_like_explicit_nested_video_defaults(data: dict[str, Any]) -> bool:
    cfg = data.get("video_defaults")
    if not isinstance(cfg, dict):
        return False
    return any(cfg.get(key) is not None for key in ("background_audio_volume", "speech_audio_volume"))


def _coerce_int(value: Any, fallback: int) -> int:
    if value is None or str(value).strip() == "":
        return fallback
    return int(value)


def _coerce_float(value: Any, fallback: float) -> float:
    if value is None or str(value).strip() == "":
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


@dataclass(frozen=True)
class NarrationOptions:
    """Prompt-only options; narration model/provider come from gateway ``settings``."""

    prompt_style: str
    custom_prompt: str = ""


@dataclass(frozen=True)
class NarrationPolishOptions:
    model: str
    prompt_style: str
    target_wpm: int
    cefr_level: str
    strength: str
    safety_margin_sec: float


@dataclass(frozen=True)
class NarrationSpeechOptions:
    voice: str
    model: str
    rate: str
    volume: str
    pitch: str
    boundary: str
    ffmpeg_bin: str


@dataclass(frozen=True)
class NarrationVideoOptions:
    ffmpeg_bin: str
    background_audio_volume: float
    speech_audio_volume: float
    """How final packaged video carries subtitles: soft mux, burn-in, or both."""
    subtitle_output_mode: Literal["soft_mux", "burn_in", "both"] = "soft_mux"


@dataclass(frozen=True)
class SubtitleContextBuildOptions:
    chunk_cue_count: int
    chunk_stride: int


@dataclass(frozen=True)
class SubtitleContextRetrieveOptions:
    history_window_sec: float
    top_k: int


@dataclass(frozen=True)
class SubtitleExtractionOptions:
    videocaptioner_bin: str | None  # 抽字幕可执行文件路径，None表示不覆盖
    asr: str  # 抽字幕ASR模型，None表示不覆盖
    language: str  # 抽字幕语言，None表示不覆盖
    timeout_sec: float | None  # 抽字幕超时时间，None表示不覆盖


@dataclass(frozen=True)
class FramePoolBuildOptions:
    ffmpeg_bin: str
    max_edge_pixels: int
    min_frames_per_shot: int
    max_frames_per_shot: int
    frames_per_shot_rate: float | None
    dialogue_overlap_threshold: float
    pyscenedetect_merge_sec: float


@dataclass(frozen=True)
class Settings:
    max_frames_per_segment: int
    narration_frame_max_edge: int
    ffmpeg_path: str
    default_prompt_style: str
    frame_pool_manifest: str | None
    pool_frames_per_shot_min: int
    pool_frames_per_shot_max: int
    pool_frames_per_shot_rate: float | None
    pool_miss_uniform_max_frames: int
    dialogue_overlap_threshold: float
    pyscenedetect_merge_sec: float
    subtitle_context_chunk_cue_count: int
    subtitle_context_chunk_stride: int
    subtitle_context_history_window_sec: float
    subtitle_context_top_k: int
    subtitle_context_summary_enabled: bool
    videocaptioner_bin: str | None
    videocaptioner_asr: str
    videocaptioner_language: str
    videocaptioner_transcribe_timeout_ms: int | None
    api_keys: Mapping[str, str]
    api_providers: Mapping[str, str]
    gateway_default_provider: str
    gateway_tts_provider: str | None
    model_catalog: tuple[str, ...]
    model_defaults: Mapping[str, str]
    narration_polish_enabled: bool
    narration_tts_enabled: bool
    narration_polish_target_wpm: int
    narration_polish_cefr_level: str
    narration_polish_strength: str
    narration_polish_safety_margin_sec: float
    tts_default_voice: str
    tts_default_rate: str
    tts_default_volume: str
    tts_default_pitch: str
    tts_default_boundary: str
    video_default_background_audio_volume: float
    video_default_speech_audio_volume: float
    narration_video_background_audio_volume: float
    narration_video_speech_audio_volume: float

    def get_api_key(self, provider: str) -> str | None:
        key = str(provider or "").strip().lower()
        if not key:
            return None
        value = self.api_keys.get(key)
        return value.strip() if value else None

    def require_api_key(self, provider: str) -> str:
        value = self.get_api_key(provider)
        if not value:
            raise ValueError(
                f"API key for provider '{provider}' is not configured. "
                "Use API_KEYS_JSON, OPENAI_API_KEY, ANTHROPIC_API_KEY, etc., or api_keys in YAML."
            )
        return value

    def get_api_base_url(self, provider: str) -> str | None:
        key = str(provider or "").strip().lower()
        if not key:
            return None
        value = self.api_providers.get(key)
        if value:
            return value.strip()
        return None

    def default_provider(self) -> str:
        slug = _none_if_empty(self.gateway_default_provider)
        if not slug:
            raise ValueError(
                "gateway_default_provider is empty; set gateway.default_provider in YAML "
                "or GATEWAY_DEFAULT_PROVIDER."
            )
        return slug.strip().lower()

    def provider_for_capability(self, capability: str) -> str:
        cap = str(capability or "").strip().lower()
        if not cap:
            raise ValueError("capability is empty")
        if cap in {"tts", "speech"}:
            slug = _none_if_empty(self.gateway_tts_provider)
            if slug:
                return slug.strip().lower()
        return self.default_provider()

    def default_model_for_capability(self, capability: str) -> str:
        cap = str(capability or "").strip().lower()
        if not cap:
            raise ValueError("capability is empty")
        value = self.model_defaults.get(cap)
        if value and value.strip():
            return value.strip()
        raise ValueError(
            f"default model for capability '{cap}' is not configured. "
            "Set model_defaults in YAML or MODEL_DEFAULTS_JSON."
        )

    def default_tts_voice(self) -> str:
        return self.tts_default_voice.strip() or "en-US-EmmaMultilingualNeural"

    def default_tts_rate(self) -> str:
        return self.tts_default_rate.strip() or "+0%"

    def default_tts_volume(self) -> str:
        return self.tts_default_volume.strip() or "+0%"

    def default_tts_pitch(self) -> str:
        return self.tts_default_pitch.strip() or "+0Hz"

    def default_tts_boundary(self) -> str:
        return self.tts_default_boundary.strip() or "SentenceBoundary"

    def narration_options(
        self,
        *,
        prompt_style: str | None = None,
        custom_prompt: str = "",
    ) -> NarrationOptions:
        from movieteller_config import runtime_options

        return runtime_options.build_narration_options(
            self, prompt_style=prompt_style, custom_prompt=custom_prompt
        )

    def narration_polish_options(
        self,
        *,
        model: str | None = None,
        prompt_style: str | None = None,
        target_wpm: int | None = None,
        cefr_level: str | None = None,
        strength: str | None = None,
        safety_margin_sec: float | None = None,
    ) -> NarrationPolishOptions:
        from movieteller_config import runtime_options

        return runtime_options.build_narration_polish_options(
            self,
            model=model,
            prompt_style=prompt_style,
            target_wpm=target_wpm,
            cefr_level=cefr_level,
            strength=strength,
            safety_margin_sec=safety_margin_sec,
        )

    def narration_speech_options(
        self,
        *,
        voice: str | None = None,
        rate: str | None = None,
        volume: str | None = None,
        pitch: str | None = None,
        boundary: str | None = None,
    ) -> NarrationSpeechOptions:
        from movieteller_config import runtime_options

        return runtime_options.build_narration_speech_options(
            self,
            voice=voice,
            rate=rate,
            volume=volume,
            pitch=pitch,
            boundary=boundary,
        )

    def narration_video_options(
        self,
        *,
        background_audio_volume: float | None = None,
        speech_audio_volume: float | None = None,
        ffmpeg_bin: str | None = None,
    ) -> NarrationVideoOptions:
        from movieteller_config import runtime_options

        return runtime_options.build_narration_video_options(
            self,
            background_audio_volume=background_audio_volume,
            speech_audio_volume=speech_audio_volume,
            ffmpeg_bin=ffmpeg_bin,
        )

    def subtitle_context_build_options(
        self,
        *,
        chunk_cue_count: int | None = None,
        chunk_stride: int | None = None,
    ) -> SubtitleContextBuildOptions:
        from movieteller_config import runtime_options

        return runtime_options.build_subtitle_context_build_options(
            self, chunk_cue_count=chunk_cue_count, chunk_stride=chunk_stride
        )

    def subtitle_context_retrieve_options(
        self,
        *,
        history_window_sec: float | None = None,
        top_k: int | None = None,
    ) -> SubtitleContextRetrieveOptions:
        from movieteller_config import runtime_options

        return runtime_options.build_subtitle_context_retrieve_options(
            self, history_window_sec=history_window_sec, top_k=top_k
        )

    def subtitle_extraction_options(
        self,
        *,
        videocaptioner_bin: str | None = None,
        asr: str | None = None,
        language: str | None = None,
        timeout_sec: float | None = None,
    ) -> SubtitleExtractionOptions:
        from movieteller_config import runtime_options

        return runtime_options.build_subtitle_extraction_options(
            self,
            videocaptioner_bin=videocaptioner_bin,
            asr=asr,
            language=language,
            timeout_sec=timeout_sec,
        )

    def frame_pool_build_options(
        self,
        *,
        ffmpeg_bin: str | None = None,
        max_edge_pixels: int | None = None,
        min_frames_per_shot: int | None = None,
        max_frames_per_shot: int | None = None,
        frames_per_shot_rate: float | None = None,
        dialogue_overlap_threshold: float | None = None,
        pyscenedetect_merge_sec: float | None = None,
    ) -> FramePoolBuildOptions:
        from movieteller_config import runtime_options

        return runtime_options.build_frame_pool_build_options(
            self,
            ffmpeg_bin=ffmpeg_bin,
            max_edge_pixels=max_edge_pixels,
            min_frames_per_shot=min_frames_per_shot,
            max_frames_per_shot=max_frames_per_shot,
            frames_per_shot_rate=frames_per_shot_rate,
            dialogue_overlap_threshold=dialogue_overlap_threshold,
            pyscenedetect_merge_sec=pyscenedetect_merge_sec,
        )


def _normalize_api_keys_dict(data: dict[str, Any]) -> dict[str, str]:
    raw: dict[str, str] = {}
    nested = data.get("api_keys")
    if isinstance(nested, dict):
        for k, v in nested.items():
            if v is None:
                continue
            expanded = expand_env_placeholder(str(v))
            if expanded:
                raw[str(k).strip().lower()] = expanded
    return raw


def _normalize_api_providers(data: dict[str, Any]) -> dict[str, str]:
    raw: dict[str, str] = {}
    nested = data.get("api_providers")
    if isinstance(nested, dict):
        for k, v in nested.items():
            if v is None:
                continue
            expanded = expand_env_placeholder(str(v))
            if expanded:
                raw[str(k).strip().lower()] = expanded
    return raw


def _normalize_model_catalog(data: dict[str, Any]) -> tuple[str, ...]:
    raw: list[str] = []
    seen: set[str] = set()
    nested = data.get("model_catalog")
    if isinstance(nested, (list, tuple)):
        for item in nested:
            if item is None:
                continue
            model = expand_env_placeholder(str(item))
            if model and model not in seen:
                raw.append(model)
                seen.add(model)
    return tuple(raw)


def _normalize_model_defaults(data: dict[str, Any]) -> dict[str, str]:
    raw: dict[str, str] = {}
    nested = data.get("model_defaults")
    if isinstance(nested, dict):
        for k, v in nested.items():
            if v is None:
                continue
            expanded = expand_env_placeholder(str(v))
            if expanded:
                raw[str(k).strip().lower()] = expanded
    return raw


def settings_from_dict(data: dict[str, Any]) -> Settings:
    gateway_cfg = data.get("gateway") if isinstance(data.get("gateway"), dict) else {}
    tts_defaults_cfg = (
        data.get("tts_defaults") if isinstance(data.get("tts_defaults"), dict) else {}
    )
    video_defaults_cfg = (
        data.get("video_defaults") if isinstance(data.get("video_defaults"), dict) else {}
    )
    api_keys = _normalize_api_keys_dict(data)
    api_providers = _normalize_api_providers(data)
    gateway_default_provider = str(
        data.get("gateway_default_provider")
        or gateway_cfg.get("default_provider")
        or ""
    ).strip().lower()
    gateway_tts_provider = _none_if_empty(
        str(
            data.get("gateway_tts_provider")
            or gateway_cfg.get("tts_provider")
            or ""
        ).strip().lower()
    )
    model_catalog = _normalize_model_catalog(data)
    model_defaults = _normalize_model_defaults(data)
    explicit_nested_tts_defaults = _looks_like_explicit_nested_tts_defaults(data)
    explicit_nested_video_defaults = _looks_like_explicit_nested_video_defaults(data)
    pool_min = max(1, _coerce_int(data.get("pool_frames_per_shot_min"), 1))
    pool_max = max(pool_min, _coerce_int(data.get("pool_frames_per_shot_max"), 3))
    return Settings(
        max_frames_per_segment=_coerce_int(data.get("max_frames_per_segment"), 24),
        narration_frame_max_edge=_coerce_int(data.get("narration_frame_max_edge"), 768),
        ffmpeg_path=str(data.get("ffmpeg_path") or "ffmpeg"),
        default_prompt_style=str(data.get("default_prompt_style") or "documentary"),
        frame_pool_manifest=_none_if_empty(
            _expand_optional_env_str(data.get("frame_pool_manifest"))
        ),
        pool_frames_per_shot_min=pool_min,
        pool_frames_per_shot_max=pool_max,
        pool_frames_per_shot_rate=(
            max(0.0, _coerce_float(data.get("pool_frames_per_shot_rate"), 0.0))
            if data.get("pool_frames_per_shot_rate") is not None
            and str(data.get("pool_frames_per_shot_rate")).strip() != ""
            else None
        ),
        pool_miss_uniform_max_frames=max(
            1, _coerce_int(data.get("pool_miss_uniform_max_frames"), 24)
        ),
        dialogue_overlap_threshold=max(
            0.0, _coerce_float(data.get("dialogue_overlap_threshold"), 0.05)
        ),
        pyscenedetect_merge_sec=max(
            0.0, _coerce_float(data.get("pyscenedetect_merge_sec"), 0.25)
        ),
        subtitle_context_chunk_cue_count=max(
            1, _coerce_int(data.get("subtitle_context_chunk_cue_count"), 5)
        ),
        subtitle_context_chunk_stride=max(
            1, _coerce_int(data.get("subtitle_context_chunk_stride"), 3)
        ),
        subtitle_context_history_window_sec=max(
            0.0, _coerce_float(data.get("subtitle_context_history_window_sec"), 600.0)
        ),
        subtitle_context_top_k=max(
            1, _coerce_int(data.get("subtitle_context_top_k"), 6)
        ),
        subtitle_context_summary_enabled=_coerce_bool(
            data.get("subtitle_context_summary_enabled"), False
        ),
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
        api_keys=MappingProxyType(dict(api_keys)),
        api_providers=MappingProxyType(dict(api_providers)),
        gateway_default_provider=gateway_default_provider,
        gateway_tts_provider=gateway_tts_provider,
        model_catalog=tuple(model_catalog),
        model_defaults=MappingProxyType(dict(model_defaults)),
        narration_polish_enabled=_coerce_bool(
            data.get("narration_polish_enabled"), False
        ),
        narration_tts_enabled=_coerce_bool(
            data.get("narration_tts_enabled"), False
        ),
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
        tts_default_voice=(
            str(
                (
                    tts_defaults_cfg.get("voice")
                    if explicit_nested_tts_defaults
                    else data.get("tts_default_voice")
                )
                or (
                    data.get("tts_default_voice")
                    if explicit_nested_tts_defaults
                    else tts_defaults_cfg.get("voice")
                )
                or "en-US-EmmaMultilingualNeural"
            ).strip()
            or "en-US-EmmaMultilingualNeural"
        ),
        tts_default_rate=(
            str(
                (
                    tts_defaults_cfg.get("rate")
                    if explicit_nested_tts_defaults
                    else data.get("tts_default_rate")
                )
                or (
                    data.get("tts_default_rate")
                    if explicit_nested_tts_defaults
                    else tts_defaults_cfg.get("rate")
                )
                or "+0%"
            ).strip()
            or "+0%"
        ),
        tts_default_volume=(
            str(
                (
                    tts_defaults_cfg.get("volume")
                    if explicit_nested_tts_defaults
                    else data.get("tts_default_volume")
                )
                or (
                    data.get("tts_default_volume")
                    if explicit_nested_tts_defaults
                    else tts_defaults_cfg.get("volume")
                )
                or "+0%"
            ).strip()
            or "+0%"
        ),
        tts_default_pitch=(
            str(
                (
                    tts_defaults_cfg.get("pitch")
                    if explicit_nested_tts_defaults
                    else data.get("tts_default_pitch")
                )
                or (
                    data.get("tts_default_pitch")
                    if explicit_nested_tts_defaults
                    else tts_defaults_cfg.get("pitch")
                )
                or "+0Hz"
            ).strip()
            or "+0Hz"
        ),
        tts_default_boundary=(
            str(
                (
                    tts_defaults_cfg.get("boundary")
                    if explicit_nested_tts_defaults
                    else data.get("tts_default_boundary")
                )
                or (
                    data.get("tts_default_boundary")
                    if explicit_nested_tts_defaults
                    else tts_defaults_cfg.get("boundary")
                )
                or "SentenceBoundary"
            ).strip()
            or "SentenceBoundary"
        ),
        video_default_background_audio_volume=max(
            0.0,
            _coerce_float(
                (
                    video_defaults_cfg.get("background_audio_volume")
                    if explicit_nested_video_defaults
                    else data.get("video_default_background_audio_volume")
                )
                if (
                    (
                        video_defaults_cfg.get("background_audio_volume")
                        if explicit_nested_video_defaults
                        else data.get("video_default_background_audio_volume")
                    )
                    is not None
                )
                else (
                    data.get("video_default_background_audio_volume")
                    if explicit_nested_video_defaults
                    else video_defaults_cfg.get("background_audio_volume")
                ),
                0.35,
            ),
        ),
        video_default_speech_audio_volume=max(
            0.0,
            _coerce_float(
                (
                    video_defaults_cfg.get("speech_audio_volume")
                    if explicit_nested_video_defaults
                    else data.get("video_default_speech_audio_volume")
                )
                if (
                    (
                        video_defaults_cfg.get("speech_audio_volume")
                        if explicit_nested_video_defaults
                        else data.get("video_default_speech_audio_volume")
                    )
                    is not None
                )
                else (
                    data.get("video_default_speech_audio_volume")
                    if explicit_nested_video_defaults
                    else video_defaults_cfg.get("speech_audio_volume")
                ),
                1.0,
            ),
        ),
        narration_video_background_audio_volume=max(
            0.0,
            _coerce_float(
                data.get("narration_video_background_audio_volume"),
                _coerce_float(
                    data.get("video_default_background_audio_volume")
                    if data.get("video_default_background_audio_volume") is not None
                    else video_defaults_cfg.get("background_audio_volume"),
                    0.35,
                ),
            ),
        ),
        narration_video_speech_audio_volume=max(
            0.0,
            _coerce_float(
                data.get("narration_video_speech_audio_volume"),
                _coerce_float(
                    data.get("video_default_speech_audio_volume")
                    if data.get("video_default_speech_audio_volume") is not None
                    else video_defaults_cfg.get("speech_audio_volume"),
                    1.0,
                ),
            ),
        ),
    )
