import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";

import dotenv from "dotenv";
import yaml from "js-yaml";

import {
  DEFAULTS,
  mergeEnvApiKeys,
  normalizeApiBaseUrlsObject,
  normalizeApiKeysObject,
  normalizeProviderModelCatalogObject,
  normalizeProviderModelsObject,
  toPublicConfig,
} from "./schema.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

function slugFromApiKeyEnv(name) {
  const suf = "_API_KEY";
  if (!name.endsWith(suf)) return null;
  const prefix = name.slice(0, -suf.length);
  return prefix ? prefix.toLowerCase() : null;
}

function slugFromBaseUrlEnv(name) {
  const suf = "_BASE_URL";
  if (!name.endsWith(suf)) return null;
  const prefix = name.slice(0, -suf.length);
  return prefix ? prefix.toLowerCase() : null;
}

/** Repository root (MovieTeller/), resolving from server/src/config/index.js */
export function getRepoRoot() {
  return path.resolve(__dirname, "../../..");
}

function deepMerge(base, override) {
  const out = { ...base };
  if (!override || typeof override !== "object") return out;
  for (const [k, v] of Object.entries(override)) {
    if (
      v &&
      typeof v === "object" &&
      !Array.isArray(v) &&
      typeof out[k] === "object" &&
      out[k] !== null &&
      !Array.isArray(out[k])
    ) {
      out[k] = deepMerge(out[k], v);
    } else if (v !== undefined) {
      out[k] = v;
    }
  }
  return out;
}

function loadYamlFile(filePath) {
  if (!fs.existsSync(filePath)) return {};
  const raw = fs.readFileSync(filePath, "utf8");
  const doc = yaml.load(raw);
  return doc && typeof doc === "object" ? doc : {};
}

function collectApiKeysFromEnv() {
  const keys = {};
  for (const envName of Object.keys(process.env).sort()) {
    const slug = slugFromApiKeyEnv(envName);
    if (!slug) continue;
    const v = process.env[envName]?.trim();
    if (v && !keys[slug]) keys[slug] = v;
  }
  const rawJson = process.env.API_KEYS_JSON?.trim();
  if (rawJson) {
    try {
      const parsed = JSON.parse(rawJson);
      if (parsed && typeof parsed === "object") {
        for (const [k, v] of Object.entries(parsed)) {
          if (v == null || String(v).trim() === "") continue;
          keys[String(k).trim().toLowerCase()] = String(v).trim();
        }
      }
    } catch {
      /* ignore */
    }
  }
  return keys;
}

function collectBaseUrlsFromEnv() {
  const urls = {};
  for (const envName of Object.keys(process.env).sort()) {
    const slug = slugFromBaseUrlEnv(envName);
    if (!slug) continue;
    const v = process.env[envName]?.trim();
    if (v && !urls[slug]) urls[slug] = v;
  }
  const rawJson = process.env.API_BASE_URLS_JSON?.trim();
  if (rawJson) {
    try {
      const parsed = JSON.parse(rawJson);
      if (parsed && typeof parsed === "object") {
        for (const [k, v] of Object.entries(parsed)) {
          if (v == null || String(v).trim() === "") continue;
          urls[String(k).trim().toLowerCase()] = String(v).trim();
        }
      }
    } catch {
      /* ignore */
    }
  }
  return urls;
}

function collectModelMapFromEnv(envName) {
  const out = {};
  const rawJson = process.env[envName]?.trim();
  if (rawJson) {
    try {
      const parsed = JSON.parse(rawJson);
      if (parsed && typeof parsed === "object") {
        for (const [k, v] of Object.entries(parsed)) {
          if (v == null || String(v).trim() === "") continue;
          out[String(k).trim().toLowerCase()] = String(v).trim();
        }
      }
    } catch {
      /* ignore */
    }
  }
  return out;
}

function collectModelCatalogFromEnv(envName) {
  const rawJson = process.env[envName]?.trim();
  if (!rawJson) return {};
  try {
    const parsed = JSON.parse(rawJson);
    if (!parsed || typeof parsed !== "object") return {};
    const out = {};
    for (const [k, v] of Object.entries(parsed)) {
      const slug = String(k).trim().toLowerCase();
      if (!slug || !Array.isArray(v)) continue;
      const ids = [];
      for (const item of v) {
        if (item == null || String(item).trim() === "") continue;
        ids.push(String(item).trim());
      }
      if (ids.length) out[slug] = ids;
    }
    return out;
  } catch {
    return {};
  }
}

function envOverrides() {
  const o = {};
  const model = process.env.NARRATION_IMAGE_MODEL || process.env.IMAGE_MODEL;
  if (model) o.narration_image_model = model;
  if (process.env.MAX_FRAMES_PER_SEGMENT)
    o.max_frames_per_segment = parseInt(process.env.MAX_FRAMES_PER_SEGMENT, 10);
  if (process.env.NARRATION_FRAME_MAX_EDGE)
    o.narration_frame_max_edge = parseInt(process.env.NARRATION_FRAME_MAX_EDGE, 10);
  if (process.env.FFMPEG_PATH) o.ffmpeg_path = process.env.FFMPEG_PATH;
  if (process.env.DEFAULT_PROMPT_STYLE)
    o.default_prompt_style = process.env.DEFAULT_PROMPT_STYLE;
  if (process.env.VIDEOCAPTIONER_BIN) o.videocaptioner_bin = process.env.VIDEOCAPTIONER_BIN;
  if (process.env.VIDEOCAPTIONER_ASR?.trim())
    o.videocaptioner_asr = process.env.VIDEOCAPTIONER_ASR.trim().toLowerCase();
  if (process.env.VIDEOCAPTIONER_LANGUAGE?.trim())
    o.videocaptioner_language = process.env.VIDEOCAPTIONER_LANGUAGE.trim();
  if (process.env.VIDEOCAPTIONER_TRANSCRIBE_TIMEOUT_MS?.trim()) {
    const n = parseInt(process.env.VIDEOCAPTIONER_TRANSCRIBE_TIMEOUT_MS.trim(), 10);
    if (!Number.isNaN(n)) o.videocaptioner_transcribe_timeout_ms = n;
  }
  if (process.env.NARRATION_API_URL) o.narration_api_url = process.env.NARRATION_API_URL;
  if (process.env.NARRATION_PROVIDER)
    o.narration_provider = String(process.env.NARRATION_PROVIDER).trim().toLowerCase();
  if (process.env.NARRATION_MODEL?.trim()) {
    o.narration_model = process.env.NARRATION_MODEL.trim();
  }
  const rawIdx = process.env.NARRATION_MODEL_INDEX;
  if (rawIdx != null && String(rawIdx).trim() !== "") {
    const n = parseInt(String(rawIdx).trim(), 10);
    if (!Number.isNaN(n)) o.narration_model_index = Math.max(0, n);
  }
  const narrationProviderModels = collectModelMapFromEnv("NARRATION_PROVIDER_MODELS_JSON");
  if (Object.keys(narrationProviderModels).length > 0) {
    o.narration_provider_models = narrationProviderModels;
  }
  const narrationProviderCatalog = collectModelCatalogFromEnv(
    "NARRATION_PROVIDER_MODEL_CATALOG_JSON"
  );
  if (Object.keys(narrationProviderCatalog).length > 0) {
    o.narration_provider_model_catalog = narrationProviderCatalog;
  }
  if (process.env.NARRATION_POLISH_ENABLED?.trim()) {
    o.narration_polish_enabled = process.env.NARRATION_POLISH_ENABLED.trim();
  }
  if (process.env.NARRATION_POLISH_PROVIDER?.trim()) {
    o.narration_polish_provider = process.env.NARRATION_POLISH_PROVIDER.trim().toLowerCase();
  }
  if (process.env.NARRATION_POLISH_MODEL?.trim()) {
    o.narration_polish_model = process.env.NARRATION_POLISH_MODEL.trim();
  }
  if (process.env.NARRATION_POLISH_MODEL_INDEX?.trim()) {
    const n = parseInt(process.env.NARRATION_POLISH_MODEL_INDEX.trim(), 10);
    if (!Number.isNaN(n)) o.narration_polish_model_index = Math.max(0, n);
  }
  const polishProviderModels = collectModelMapFromEnv(
    "NARRATION_POLISH_PROVIDER_MODELS_JSON"
  );
  if (Object.keys(polishProviderModels).length > 0) {
    o.narration_polish_provider_models = polishProviderModels;
  }
  const polishProviderCatalog = collectModelCatalogFromEnv(
    "NARRATION_POLISH_PROVIDER_MODEL_CATALOG_JSON"
  );
  if (Object.keys(polishProviderCatalog).length > 0) {
    o.narration_polish_provider_model_catalog = polishProviderCatalog;
  }
  if (process.env.NARRATION_POLISH_TARGET_WPM?.trim()) {
    const n = parseInt(process.env.NARRATION_POLISH_TARGET_WPM.trim(), 10);
    if (!Number.isNaN(n)) o.narration_polish_target_wpm = n;
  }
  if (process.env.NARRATION_POLISH_CEFR_LEVEL?.trim()) {
    o.narration_polish_cefr_level = process.env.NARRATION_POLISH_CEFR_LEVEL.trim().toUpperCase();
  }
  if (process.env.NARRATION_POLISH_STRENGTH?.trim()) {
    o.narration_polish_strength = process.env.NARRATION_POLISH_STRENGTH.trim().toLowerCase();
  }
  if (process.env.NARRATION_POLISH_SAFETY_MARGIN_SEC?.trim()) {
    const n = Number.parseFloat(process.env.NARRATION_POLISH_SAFETY_MARGIN_SEC.trim());
    if (!Number.isNaN(n)) o.narration_polish_safety_margin_sec = n;
  }
  if (process.env.NARRATION_SPEECH_ENABLED?.trim()) {
    o.narration_speech_enabled = process.env.NARRATION_SPEECH_ENABLED.trim();
  }
  if (process.env.NARRATION_SPEECH_PROVIDER?.trim()) {
    o.narration_speech_provider = process.env.NARRATION_SPEECH_PROVIDER.trim().toLowerCase();
  }
  if (process.env.NARRATION_SPEECH_VOICE?.trim()) {
    o.narration_speech_voice = process.env.NARRATION_SPEECH_VOICE.trim();
  }
  if (process.env.NARRATION_SPEECH_RATE?.trim()) {
    o.narration_speech_rate = process.env.NARRATION_SPEECH_RATE.trim();
  }
  if (process.env.NARRATION_SPEECH_VOLUME?.trim()) {
    o.narration_speech_volume = process.env.NARRATION_SPEECH_VOLUME.trim();
  }
  if (process.env.NARRATION_SPEECH_PITCH?.trim()) {
    o.narration_speech_pitch = process.env.NARRATION_SPEECH_PITCH.trim();
  }
  if (process.env.NARRATION_SPEECH_BOUNDARY?.trim()) {
    o.narration_speech_boundary = process.env.NARRATION_SPEECH_BOUNDARY.trim();
  }
  if (process.env.NARRATION_VIDEO_BACKGROUND_AUDIO_VOLUME?.trim()) {
    const n = Number.parseFloat(process.env.NARRATION_VIDEO_BACKGROUND_AUDIO_VOLUME.trim());
    if (!Number.isNaN(n)) o.narration_video_background_audio_volume = n;
  }
  if (process.env.NARRATION_VIDEO_SPEECH_AUDIO_VOLUME?.trim()) {
    const n = Number.parseFloat(process.env.NARRATION_VIDEO_SPEECH_AUDIO_VOLUME.trim());
    if (!Number.isNaN(n)) o.narration_video_speech_audio_volume = n;
  }

  const envUrls = collectBaseUrlsFromEnv();
  if (Object.keys(envUrls).length > 0) o.api_base_urls = envUrls;

  const envKeys = collectApiKeysFromEnv();
  if (Object.keys(envKeys).length > 0) o.api_keys = envKeys;

  return o;
}

let cached = null;

/**
 * Load merged configuration (env overrides YAML overrides defaults).
 * Call early so `dotenv` loads repo-root `.env`.
 * @param {{ force?: boolean }} [opts]
 */
export function loadConfig(opts = {}) {
  if (cached && !opts.force) return cached;

  const repoRoot = getRepoRoot();
  dotenv.config({ path: path.join(repoRoot, ".env") });

  let merged = { ...DEFAULTS };

  const mt = process.env.MOVIE_TELLER_CONFIG?.trim();
  if (mt) {
    merged = deepMerge(merged, loadYamlFile(path.resolve(mt)));
  }

  const localYaml = path.join(repoRoot, "config", "local.yaml");
  merged = deepMerge(merged, loadYamlFile(localYaml));

  merged = deepMerge(merged, envOverrides());

  const envKeys = collectApiKeysFromEnv();
  merged.api_keys = normalizeApiKeysObject(
    mergeEnvApiKeys(normalizeApiKeysObject(merged.api_keys ?? {}), envKeys)
  );
  merged.api_base_urls = normalizeApiBaseUrlsObject({
    ...normalizeApiBaseUrlsObject(merged.api_base_urls ?? {}),
    ...collectBaseUrlsFromEnv(),
  });
  merged.narration_provider_models = normalizeProviderModelsObject({
    ...normalizeProviderModelsObject(merged.narration_provider_models ?? {}),
    ...collectModelMapFromEnv("NARRATION_PROVIDER_MODELS_JSON"),
  });
  merged.narration_provider_model_catalog = normalizeProviderModelCatalogObject({
    ...normalizeProviderModelCatalogObject(merged.narration_provider_model_catalog ?? {}),
    ...normalizeProviderModelCatalogObject(
      collectModelCatalogFromEnv("NARRATION_PROVIDER_MODEL_CATALOG_JSON")
    ),
  });
  merged.narration_polish_provider_models = normalizeProviderModelsObject({
    ...normalizeProviderModelsObject(merged.narration_polish_provider_models ?? {}),
    ...collectModelMapFromEnv("NARRATION_POLISH_PROVIDER_MODELS_JSON"),
  });
  merged.narration_polish_provider_model_catalog = normalizeProviderModelCatalogObject({
    ...normalizeProviderModelCatalogObject(
      merged.narration_polish_provider_model_catalog ?? {}
    ),
    ...normalizeProviderModelCatalogObject(
      collectModelCatalogFromEnv("NARRATION_POLISH_PROVIDER_MODEL_CATALOG_JSON")
    ),
  });

  cached = Object.freeze(toPublicConfig(merged));
  return cached;
}

/** Resolve inference base URL for a provider (see apiBaseUrls). */
export function getApiBaseUrl(config, provider) {
  const id = String(provider).trim().toLowerCase();
  if (!id) return null;
  return config.apiBaseUrls?.[id]?.trim() ?? null;
}

/** Model id for a provider slug (matches Python ``model_for_provider`` resolution). */
export function getModelForProvider(config, provider) {
  const id = String(provider).trim().toLowerCase();
  const fallback = config.narrationImageModel ?? "gpt-4o-mini";
  const np = String(config.narrationProvider ?? "openai").trim().toLowerCase();
  if (!id) return fallback;

  if (id === np && config.narrationModel?.trim()) {
    return config.narrationModel.trim();
  }

  const scopedPm = config.narrationProviderModels?.[id]?.trim();
  if (scopedPm) return scopedPm;

  const scopedCatalog = config.narrationProviderModelCatalog?.[id];
  if (scopedCatalog && scopedCatalog.length > 0) {
    let idx = id === np ? Number(config.narrationModelIndex ?? 0) : 0;
    if (!Number.isFinite(idx) || idx < 0) idx = 0;
    if (idx < scopedCatalog.length) return scopedCatalog[idx];
    return scopedCatalog[0];
  }

  return fallback;
}

/** Model id for narration-polish by provider slug. */
export function getPolishModelForProvider(config, provider) {
  const id = String(provider).trim().toLowerCase();
  const fallback = getModelForProvider(config, id);
  const pp = String(config.narrationPolishProvider || config.narrationProvider || "openai")
    .trim()
    .toLowerCase();
  if (!id) return fallback;

  if (id === pp && config.narrationPolishModel?.trim()) {
    return config.narrationPolishModel.trim();
  }

  const scopedPm = config.narrationPolishProviderModels?.[id]?.trim();
  if (scopedPm) return scopedPm;

  const scopedCatalog = config.narrationPolishProviderModelCatalog?.[id];
  if (scopedCatalog && scopedCatalog.length > 0) {
    let idx = id === pp ? Number(config.narrationPolishModelIndex ?? 0) : 0;
    if (!Number.isFinite(idx) || idx < 0) idx = 0;
    if (idx < scopedCatalog.length) return scopedCatalog[idx];
    return scopedCatalog[0];
  }

  return fallback;
}

/** Resolve API key by provider slug (e.g. openai, anthropic). */
export function getApiKey(config, provider) {
  const id = String(provider).trim().toLowerCase();
  if (!id) return null;
  return config.apiKeys?.[id] ?? null;
}

/** Throws if OpenAI key missing — use before OpenAI-specific calls. */
export function requireOpenAIConfig(config = loadConfig()) {
  const key = getApiKey(config, "openai")?.trim();
  if (!key) {
    throw new Error(
      "OpenAI API key is required for this operation. Set OPENAI_API_KEY, API_KEYS_JSON, or api_keys.openai in config/local.yaml."
    );
  }
  return key;
}

/** Throws if key for provider missing. */
export function requireApiKey(config, provider) {
  const k = getApiKey(config, provider);
  if (!k?.trim()) {
    throw new Error(
      `API key for '${provider}' is not configured. Use API_KEYS_JSON, PREFIX_API_KEY env vars, or api_keys in YAML.`
    );
  }
  return k.trim();
}
