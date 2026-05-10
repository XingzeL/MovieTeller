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

# Env names that do not match ``{PREFIX}_API_KEY`` but should map to a slug (rare).
_LEGACY_API_KEY_ALIASES: tuple[tuple[str, str], ...] = (
    ("ELEVEN_LABS_API", "elevenlabs"),
    ("MODELSCOPE_API_KEY_FREE", "modelscope"),
)


def _slug_from_api_key_env(env_name: str) -> str | None:
    """``FOO_BAR_API_KEY`` -> ``foo_bar``. ``API_KEYS_JSON`` keys override these."""
    suf = "_API_KEY"
    if not env_name.endswith(suf):
        return None
    prefix = env_name[: -len(suf)]
    if not prefix:
        return None
    return prefix.lower()


def _slug_from_base_url_env(env_name: str) -> str | None:
    """``FOO_BASE_URL`` -> ``foo``. ``API_BASE_URLS_JSON`` overrides these."""
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
    """Optional repo-root config/local.yaml (MovieTeller/config/local.yaml)."""
    cwd = Path.cwd()
    candidates = [
        cwd / "config" / "local.yaml",
        cwd.parent / "config" / "local.yaml",
    ]
    return candidates


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


def _collect_base_urls_from_env() -> dict[str, str]:
    urls: dict[str, str] = {}
    for env_name in sorted(os.environ.keys()):
        slug = _slug_from_base_url_env(env_name)
        if slug and (v := os.environ.get(env_name, "").strip()):
            urls.setdefault(slug, v)
    raw_json = os.environ.get("API_BASE_URLS_JSON", "").strip()
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
    if raw_json:
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


def _collect_model_catalog_from_env(env_name: str) -> dict[str, list[str]]:
    """Env JSON: slug -> list of model ids."""
    out: dict[str, list[str]] = {}
    raw_json = os.environ.get(env_name, "").strip()
    if not raw_json:
        return out
    try:
        parsed = json.loads(raw_json)
        if isinstance(parsed, dict):
            for k, v in parsed.items():
                slug = str(k).strip().lower()
                if not slug or not isinstance(v, list):
                    continue
                ids: list[str] = []
                for item in v:
                    if item is None or str(item).strip() == "":
                        continue
                    ids.append(str(item).strip())
                if ids:
                    out[slug] = ids
    except json.JSONDecodeError:
        pass
    return out
def _load_repo_dotenv() -> None:
    """Load repo-root ``.env`` when present (same convention as Node ``loadConfig``)."""
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


def load_flat_dict() -> dict[str, Any]:
    """
    Merge priority (lowest wins last — last merge wins):
    1. packaged default.yaml
    2. MOVIE_TELLER_CONFIG file if set
    3. first existing config/local.yaml from cwd walk hints
    4. environment variables (highest priority)
    """
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
    """Map env vars to flat keys used in YAML/settings."""
    out: dict[str, Any] = {}
    if v := os.environ.get("OPENAI_API_KEY"):
        out["openai_api_key"] = v
    if v := os.environ.get("OPENAI_BASE_URL"):
        out["openai_base_url"] = v
    model = os.environ.get("NARRATION_IMAGE_MODEL") or os.environ.get("IMAGE_MODEL")
    if model:
        out["narration_image_model"] = model
    if v := os.environ.get("MAX_FRAMES_PER_SEGMENT"):
        out["max_frames_per_segment"] = int(v)
    if v := os.environ.get("NARRATION_FRAME_MAX_EDGE"):
        out["narration_frame_max_edge"] = int(v)
    if v := os.environ.get("FFMPEG_PATH"):
        out["ffmpeg_path"] = v
    if v := os.environ.get("DEFAULT_PROMPT_STYLE"):
        out["default_prompt_style"] = v
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
    if v := os.environ.get("NARRATION_API_URL"):
        out["narration_api_url"] = v
    if v := os.environ.get("NARRATION_PROVIDER"):
        out["narration_provider"] = str(v).strip().lower()
    if v := os.environ.get("NARRATION_MODEL", "").strip():
        out["narration_model"] = v
    if (idx_raw := os.environ.get("NARRATION_MODEL_INDEX", "").strip()):
        try:
            out["narration_model_index"] = max(0, int(idx_raw))
        except ValueError:
            pass
    narration_pm = _collect_model_map_from_env("NARRATION_PROVIDER_MODELS_JSON")
    if narration_pm:
        out["narration_provider_models"] = narration_pm
    narration_cat = _collect_model_catalog_from_env(
        "NARRATION_PROVIDER_MODEL_CATALOG_JSON"
    )
    if narration_cat:
        out["narration_provider_model_catalog"] = narration_cat
    if v := os.environ.get("NARRATION_POLISH_ENABLED", "").strip():
        out["narration_polish_enabled"] = v
    if v := os.environ.get("NARRATION_POLISH_PROVIDER", "").strip():
        out["narration_polish_provider"] = v.lower()
    if v := os.environ.get("NARRATION_POLISH_MODEL", "").strip():
        out["narration_polish_model"] = v
    if (idx_raw := os.environ.get("NARRATION_POLISH_MODEL_INDEX", "").strip()):
        try:
            out["narration_polish_model_index"] = max(0, int(idx_raw))
        except ValueError:
            pass
    polish_pm = _collect_model_map_from_env("NARRATION_POLISH_PROVIDER_MODELS_JSON")
    if polish_pm:
        out["narration_polish_provider_models"] = polish_pm
    polish_cat = _collect_model_catalog_from_env(
        "NARRATION_POLISH_PROVIDER_MODEL_CATALOG_JSON"
    )
    if polish_cat:
        out["narration_polish_provider_model_catalog"] = polish_cat
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

    url_patch = _collect_base_urls_from_env()
    if url_patch:
        existing_urls = out.get("api_base_urls")
        if isinstance(existing_urls, dict):
            out["api_base_urls"] = {**existing_urls, **url_patch}
        else:
            out["api_base_urls"] = url_patch

    env_keys = _collect_api_keys_from_env()
    if env_keys:
        existing = out.get("api_keys")
        if isinstance(existing, dict):
            merged_keys = {**existing, **env_keys}
        else:
            merged_keys = dict(env_keys)
        out["api_keys"] = merged_keys

    narration_pm_patch = _collect_model_map_from_env("NARRATION_PROVIDER_MODELS_JSON")
    if narration_pm_patch:
        existing = out.get("narration_provider_models")
        if isinstance(existing, dict):
            out["narration_provider_models"] = {**existing, **narration_pm_patch}
        else:
            out["narration_provider_models"] = narration_pm_patch

    narration_cat_patch = _collect_model_catalog_from_env(
        "NARRATION_PROVIDER_MODEL_CATALOG_JSON"
    )
    if narration_cat_patch:
        existing = out.get("narration_provider_model_catalog")
        if isinstance(existing, dict):
            out["narration_provider_model_catalog"] = {
                **existing,
                **narration_cat_patch,
            }
        else:
            out["narration_provider_model_catalog"] = narration_cat_patch

    polish_pm_patch = _collect_model_map_from_env(
        "NARRATION_POLISH_PROVIDER_MODELS_JSON"
    )
    if polish_pm_patch:
        existing = out.get("narration_polish_provider_models")
        if isinstance(existing, dict):
            out["narration_polish_provider_models"] = {**existing, **polish_pm_patch}
        else:
            out["narration_polish_provider_models"] = polish_pm_patch

    polish_cat_patch = _collect_model_catalog_from_env(
        "NARRATION_POLISH_PROVIDER_MODEL_CATALOG_JSON"
    )
    if polish_cat_patch:
        existing = out.get("narration_polish_provider_model_catalog")
        if isinstance(existing, dict):
            out["narration_polish_provider_model_catalog"] = {
                **existing,
                **polish_cat_patch,
            }
        else:
            out["narration_polish_provider_model_catalog"] = polish_cat_patch

    return out


def load_settings(
    *, require_openai: bool = False, require_narration: bool = False
) -> Settings:
    """
    Load merged Settings.

    - ``require_openai``: raises when the ``openai`` provider key is missing (legacy).
    - ``require_narration``: raises when the key for ``narration_provider`` is missing
      (any slug in ``api_keys``, e.g. ``openai``, ``modelscope``).
    """
    data = load_flat_dict()
    settings = settings_from_dict(data)
    if require_openai:
        settings.require_openai()
    if require_narration:
        settings.require_api_key(settings.narration_provider)
    return settings


def clear_settings_cache() -> None:
    """Reserved for future caching; no-op for now."""
    return None
