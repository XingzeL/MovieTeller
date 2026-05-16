from __future__ import annotations

import json
import os
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

try:
    from dotenv import find_dotenv, load_dotenv
except ImportError:
    def find_dotenv(*args: Any, **kwargs: Any) -> str:
        return ""

    def load_dotenv(*args: Any, **kwargs: Any) -> bool:
        return False

from movieteller_config.schema import Settings, settings_from_dict

_LEGACY_API_KEY_ALIASES: tuple[tuple[str, str], ...] = (
    ("ELEVEN_LABS_API", "elevenlabs"),
    ("MODELSCOPE_API_KEY_FREE", "modelscope"),
)


def _slug_from_api_key_env(env_name: str) -> str | None:
    suf = "_API_KEY"
    if not env_name.endswith(suf):
        return None
    prefix = env_name[: -len(suf)]
    if not prefix:
        return None
    return prefix.lower()


def _slug_from_base_url_env(env_name: str) -> str | None:
    suf = "_BASE_URL"
    if not env_name.endswith(suf):
        return None
    prefix = env_name[: -len(suf)]
    if not prefix:
        return None
    return prefix.lower()


def _deep_merge(base: dict[str, Any], override: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(base)
    for k, v in override.items():
        if k in out and isinstance(out[k], dict) and isinstance(v, Mapping):
            out[k] = _deep_merge(out[k], dict(v))  # type: ignore[arg-type]
        else:
            out[k] = v
    return out


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return raw if isinstance(raw, dict) else {}


def _package_default_yaml() -> Path:
    return Path(__file__).resolve().parent / "config" / "default.yaml"


def _repo_root_config_paths() -> list[Path]:
    cwd = Path.cwd()
    return [
        cwd / "config" / "local.yaml",
        cwd.parent / "config" / "local.yaml",
    ]


def _load_repo_dotenv() -> None:
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


def _collect_api_keys_from_env() -> dict[str, str]:
    keys: dict[str, str] = {}
    for env_name in sorted(os.environ.keys()):
        slug = _slug_from_api_key_env(env_name)
        if slug and (v := os.environ.get(env_name, "").strip()):
            keys.setdefault(slug, v)
    for env_name, provider in _LEGACY_API_KEY_ALIASES:
        if v := os.environ.get(env_name, "").strip():
            keys.setdefault(provider, v)
    raw_json = os.environ.get("API_KEYS_JSON", "").strip()
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if v is None or str(v).strip() == "":
                        continue
                    keys[str(k).strip().lower()] = str(v).strip()
        except json.JSONDecodeError:
            pass
    return keys


def _collect_api_providers_from_env() -> dict[str, str]:
    urls: dict[str, str] = {}
    for env_name in sorted(os.environ.keys()):
        slug = _slug_from_base_url_env(env_name)
        if slug and (v := os.environ.get(env_name, "").strip()):
            urls.setdefault(slug, v)
    raw_json = os.environ.get("API_PROVIDERS_JSON", "").strip()
    if raw_json:
        try:
            parsed = json.loads(raw_json)
            if isinstance(parsed, dict):
                for k, v in parsed.items():
                    if v is None or str(v).strip() == "":
                        continue
                    urls[str(k).strip().lower()] = str(v).strip()
        except json.JSONDecodeError:
            pass
    return urls


def _collect_model_map_from_env(env_name: str) -> dict[str, str]:
    out: dict[str, str] = {}
    raw_json = os.environ.get(env_name, "").strip()
    if not raw_json:
        return out
    try:
        parsed = json.loads(raw_json)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                if v is None or str(v).strip() == "":
                    continue
                out[str(k).strip().lower()] = str(v).strip()
    except json.JSONDecodeError:
        pass
    return out


def _collect_flat_model_catalog_from_env(env_name: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    raw_json = os.environ.get(env_name, "").strip()
    if not raw_json:
        return out
    try:
        parsed = json.loads(raw_json)
        if isinstance(parsed, list):
            for item in parsed:
                if item is None or str(item).strip() == "":
                    continue
                model = str(item).strip()
                if model and model not in seen:
                    out.append(model)
                    seen.add(model)
        elif isinstance(parsed, dict):
            for k, _v in parsed.items():
                model = str(k).strip()
                if model and model not in seen:
                    out.append(model)
                    seen.add(model)
    except json.JSONDecodeError:
        pass
    return out


def load_flat_dict() -> dict[str, Any]:
    _load_repo_dotenv()
    merged: dict[str, Any] = _load_yaml_file(_package_default_yaml())

    mt_config = os.environ.get("MOVIE_TELLER_CONFIG", "").strip()
    if mt_config:
        merged = _deep_merge(merged, _load_yaml_file(Path(mt_config)))

    for p in _repo_root_config_paths():
        if p.is_file():
            merged = _deep_merge(merged, _load_yaml_file(p))
            break

    merged = _deep_merge(merged, _env_overrides())
    return merged


def _env_overrides() -> dict[str, Any]:
    out: dict[str, Any] = {}
    tts_defaults_patch: dict[str, Any] = {}
    video_defaults_patch: dict[str, Any] = {}
    if v := os.environ.get("OPENAI_API_KEY"):
        out["openai_api_key"] = v
    if v := os.environ.get("OPENAI_BASE_URL"):
        out["openai_base_url"] = v
    if v := os.environ.get("MAX_FRAMES_PER_SEGMENT"):
        out["max_frames_per_segment"] = int(v)
    if v := os.environ.get("NARRATION_FRAME_MAX_EDGE"):
        out["narration_frame_max_edge"] = int(v)
    if v := os.environ.get("FFMPEG_PATH"):
        out["ffmpeg_path"] = v
    if v := os.environ.get("DEFAULT_PROMPT_STYLE"):
        out["default_prompt_style"] = v
    if v := os.environ.get("GATEWAY_DEFAULT_PROVIDER", "").strip():
        out["gateway_default_provider"] = v.lower()
    if v := os.environ.get("GATEWAY_TTS_PROVIDER", "").strip():
        out["gateway_tts_provider"] = v.lower()
    if v := os.environ.get("FRAME_POOL_MANIFEST", "").strip():
        out["frame_pool_manifest"] = v
    if v := os.environ.get("POOL_FRAMES_PER_SHOT_MIN", "").strip():
        try:
            out["pool_frames_per_shot_min"] = int(v)
        except ValueError:
            pass
    if v := os.environ.get("POOL_FRAMES_PER_SHOT_MAX", "").strip():
        try:
            out["pool_frames_per_shot_max"] = int(v)
        except ValueError:
            pass
    if v := os.environ.get("POOL_FRAMES_PER_SHOT_RATE", "").strip():
        try:
            out["pool_frames_per_shot_rate"] = float(v)
        except ValueError:
            pass
    if v := os.environ.get("POOL_MISS_UNIFORM_MAX_FRAMES", "").strip():
        try:
            out["pool_miss_uniform_max_frames"] = int(v)
        except ValueError:
            pass
    if v := os.environ.get("DIALOGUE_OVERLAP_THRESHOLD", "").strip():
        try:
            out["dialogue_overlap_threshold"] = float(v)
        except ValueError:
            pass
    if v := os.environ.get("PYSCENEDETECT_MERGE_SEC", "").strip():
        try:
            out["pyscenedetect_merge_sec"] = float(v)
        except ValueError:
            pass
    if v := os.environ.get("SUBTITLE_CONTEXT_CHUNK_CUE_COUNT", "").strip():
        try:
            out["subtitle_context_chunk_cue_count"] = int(v)
        except ValueError:
            pass
    if v := os.environ.get("SUBTITLE_CONTEXT_CHUNK_STRIDE", "").strip():
        try:
            out["subtitle_context_chunk_stride"] = int(v)
        except ValueError:
            pass
    if v := os.environ.get("SUBTITLE_CONTEXT_HISTORY_WINDOW_SEC", "").strip():
        try:
            out["subtitle_context_history_window_sec"] = float(v)
        except ValueError:
            pass
    if v := os.environ.get("SUBTITLE_CONTEXT_TOP_K", "").strip():
        try:
            out["subtitle_context_top_k"] = int(v)
        except ValueError:
            pass
    if v := os.environ.get("SUBTITLE_CONTEXT_SUMMARY_ENABLED", "").strip():
        out["subtitle_context_summary_enabled"] = v
    if v := os.environ.get("VIDEOCAPTIONER_BIN"):
        out["videocaptioner_bin"] = v
    if v := os.environ.get("VIDEOCAPTIONER_ASR", "").strip():
        out["videocaptioner_asr"] = v
    if v := os.environ.get("VIDEOCAPTIONER_LANGUAGE", "").strip():
        out["videocaptioner_language"] = v
    if v := os.environ.get("VIDEOCAPTIONER_TRANSCRIBE_TIMEOUT_MS", "").strip():
        try:
            out["videocaptioner_transcribe_timeout_ms"] = int(v)
        except ValueError:
            pass
    if v := os.environ.get("NARRATION_POLISH_ENABLED", "").strip():
        out["narration_polish_enabled"] = v
    if v := os.environ.get("NARRATION_TTS_ENABLED", "").strip():
        out["narration_tts_enabled"] = v
    if v := os.environ.get("NARRATION_POLISH_TARGET_WPM", "").strip():
        try:
            out["narration_polish_target_wpm"] = int(v)
        except ValueError:
            pass
    if v := os.environ.get("NARRATION_POLISH_CEFR_LEVEL", "").strip():
        out["narration_polish_cefr_level"] = v.upper()
    if v := os.environ.get("NARRATION_POLISH_STRENGTH", "").strip():
        out["narration_polish_strength"] = v.lower()
    if v := os.environ.get("NARRATION_POLISH_SAFETY_MARGIN_SEC", "").strip():
        try:
            out["narration_polish_safety_margin_sec"] = float(v)
        except ValueError:
            pass
    if v := os.environ.get("TTS_DEFAULT_VOICE", "").strip():
        out["tts_default_voice"] = v
        tts_defaults_patch["voice"] = v
    if v := os.environ.get("TTS_DEFAULT_RATE", "").strip():
        out["tts_default_rate"] = v
        tts_defaults_patch["rate"] = v
    if v := os.environ.get("TTS_DEFAULT_VOLUME", "").strip():
        out["tts_default_volume"] = v
        tts_defaults_patch["volume"] = v
    if v := os.environ.get("TTS_DEFAULT_PITCH", "").strip():
        out["tts_default_pitch"] = v
        tts_defaults_patch["pitch"] = v
    if v := os.environ.get("TTS_DEFAULT_BOUNDARY", "").strip():
        out["tts_default_boundary"] = v
        tts_defaults_patch["boundary"] = v
    if v := os.environ.get("VIDEO_DEFAULT_BACKGROUND_AUDIO_VOLUME", "").strip():
        try:
            out["video_default_background_audio_volume"] = float(v)
            video_defaults_patch["background_audio_volume"] = float(v)
        except ValueError:
            pass
    if v := os.environ.get("VIDEO_DEFAULT_SPEECH_AUDIO_VOLUME", "").strip():
        try:
            out["video_default_speech_audio_volume"] = float(v)
            video_defaults_patch["speech_audio_volume"] = float(v)
        except ValueError:
            pass
    if v := os.environ.get("NARRATION_VIDEO_BACKGROUND_AUDIO_VOLUME", "").strip():
        try:
            out["narration_video_background_audio_volume"] = float(v)
        except ValueError:
            pass
    if v := os.environ.get("NARRATION_VIDEO_SPEECH_AUDIO_VOLUME", "").strip():
        try:
            out["narration_video_speech_audio_volume"] = float(v)
        except ValueError:
            pass

    provider_patch = _collect_api_providers_from_env()
    if provider_patch:
        existing_providers = out.get("api_providers")
        if isinstance(existing_providers, dict):
            out["api_providers"] = {**existing_providers, **provider_patch}
        else:
            out["api_providers"] = provider_patch

    env_keys = _collect_api_keys_from_env()
    if env_keys:
        existing = out.get("api_keys")
        if isinstance(existing, dict):
            out["api_keys"] = {**existing, **env_keys}
        else:
            out["api_keys"] = dict(env_keys)

    model_catalog_patch = _collect_flat_model_catalog_from_env("MODEL_CATALOG_JSON")
    if model_catalog_patch:
        existing = out.get("model_catalog")
        if isinstance(existing, list):
            merged: list[str] = []
            seen: set[str] = set()
            for model in [*existing, *model_catalog_patch]:
                if model not in seen:
                    merged.append(model)
                    seen.add(model)
            out["model_catalog"] = merged
        else:
            out["model_catalog"] = model_catalog_patch

    model_defaults_patch = _collect_model_map_from_env("MODEL_DEFAULTS_JSON")
    if model_defaults_patch:
        existing = out.get("model_defaults")
        if isinstance(existing, dict):
            out["model_defaults"] = {**existing, **model_defaults_patch}
        else:
            out["model_defaults"] = model_defaults_patch

    if tts_defaults_patch:
        existing = out.get("tts_defaults")
        if isinstance(existing, dict):
            out["tts_defaults"] = {**existing, **tts_defaults_patch}
        else:
            out["tts_defaults"] = dict(tts_defaults_patch)

    if video_defaults_patch:
        existing = out.get("video_defaults")
        if isinstance(existing, dict):
            out["video_defaults"] = {**existing, **video_defaults_patch}
        else:
            out["video_defaults"] = dict(video_defaults_patch)

    return out


def load_settings(
    *, require_openai: bool = False, require_narration: bool = False
) -> Settings:
    data = load_flat_dict()
    settings = settings_from_dict(data)
    if require_openai:
        settings.require_openai()
    if require_narration:
        settings.require_api_key(settings.default_provider())
    return settings


def clear_settings_cache() -> None:
    return None
