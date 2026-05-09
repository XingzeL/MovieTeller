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
  normalizeProviderModelsObject,
  toPublicConfig,
} from "./schema.js";

const __dirname = path.dirname(fileURLToPath(import.meta.url));

/** Names that are not ``PREFIX_API_KEY`` but map to a slug (kept minimal). */
const LEGACY_API_KEY_ALIASES = [
  ["ELEVEN_LABS_API", "elevenlabs"],
  ["MODELSCOPE_API_KEY_FREE", "modelscope"],
];

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
  for (const [envName, provider] of LEGACY_API_KEY_ALIASES) {
    const v = process.env[envName]?.trim();
    if (v && !keys[provider]) keys[provider] = v;
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

function collectProviderModelsFromEnv() {
  const out = {};
  const rawJson = process.env.PROVIDER_MODELS_JSON?.trim();
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

function envOverrides() {
  const o = {};
  if (process.env.OPENAI_API_KEY) o.openai_api_key = process.env.OPENAI_API_KEY;
  if (process.env.OPENAI_BASE_URL) o.openai_base_url = process.env.OPENAI_BASE_URL;
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
  if (process.env.NARRATION_API_URL) o.narration_api_url = process.env.NARRATION_API_URL;
  if (process.env.NARRATION_PROVIDER)
    o.narration_provider = String(process.env.NARRATION_PROVIDER).trim().toLowerCase();

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
  merged.provider_models = normalizeProviderModelsObject({
    ...normalizeProviderModelsObject(merged.provider_models ?? {}),
    ...collectProviderModelsFromEnv(),
  });
  if (merged.openai_api_key?.trim() && !merged.api_keys.openai) {
    merged.api_keys = {
      ...merged.api_keys,
      openai: merged.openai_api_key.trim(),
    };
  }

  cached = Object.freeze(toPublicConfig(merged));
  return cached;
}

/** Resolve inference base URL for a provider (see apiBaseUrls / openaiBaseUrl). */
export function getApiBaseUrl(config, provider) {
  const id = String(provider).trim().toLowerCase();
  if (!id) return null;
  const fromMap = config.apiBaseUrls?.[id]?.trim();
  if (fromMap) return fromMap;
  if (id === "openai") return config.openaiBaseUrl?.trim() ?? null;
  return null;
}

/** Model id for a provider slug; falls back to narrationImageModel. */
export function getModelForProvider(config, provider) {
  const id = String(provider).trim().toLowerCase();
  const fallback = config.narrationImageModel ?? "gpt-4o-mini";
  if (!id) return fallback;
  const m = config.providerModels?.[id]?.trim();
  return m || fallback;
}

/** Resolve API key by provider slug (e.g. openai, anthropic). */
export function getApiKey(config, provider) {
  const id = String(provider).trim().toLowerCase();
  if (!id) return null;
  return config.apiKeys?.[id] ?? null;
}

/** Throws if OpenAI key missing — use before OpenAI-specific calls. */
export function requireOpenAIConfig(config = loadConfig()) {
  const key = config.openaiApiKey?.trim() || config.apiKeys?.openai?.trim();
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
