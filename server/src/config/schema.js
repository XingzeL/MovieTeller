/** Default values aligned with Python `movieteller_config/config/default.yaml`. */
export const DEFAULTS = {
  openai_api_key: null,
  openai_base_url: null,
  narration_image_model: "gpt-4o-mini",
  max_frames_per_segment: 24,
  narration_frame_max_edge: 768,
  ffmpeg_path: "ffmpeg",
  default_prompt_style: "documentary",
  narration_provider: "openai",
  videocaptioner_bin: null,
  narration_api_url: null,
  api_keys: {},
  api_base_urls: {},
  provider_models: {},
  provider_model_catalog: {},
  narration_model: null,
  narration_model_index: 0,
};

/**
 * Whole-string `${VAR}`, `$$VAR`, or `$VAR` → process.env[VAR]. Otherwise trimmed literal.
 */
export function expandEnvPlaceholder(v) {
  const s = String(v == null ? "" : v).trim();
  const brace = s.match(/^\$\{([A-Za-z_][A-Za-z0-9_]*)\}$/);
  const dbl = s.match(/^\$\$([A-Za-z_][A-Za-z0-9_]*)$/);
  const one = s.match(/^\$([A-Za-z_][A-Za-z0-9_]*)$/);
  const name = brace?.[1] ?? dbl?.[1] ?? one?.[1];
  if (!name) return s;
  return process.env[name]?.trim() ?? "";
}

/** Public camelCase shape returned by `loadConfig()`. */
export function toPublicConfig(s) {
  const apiKeys = normalizeApiKeysObject(s.api_keys ?? {});
  let apiBaseUrls = normalizeApiBaseUrlsObject(s.api_base_urls ?? {});
  const rawOb = s.openai_base_url;
  const ob =
    rawOb != null && String(rawOb).trim()
      ? expandEnvPlaceholder(String(rawOb))
      : "";
  if (ob && !apiBaseUrls.openai) apiBaseUrls = { ...apiBaseUrls, openai: ob };
  const rawOk = s.openai_api_key;
  const directKey =
    rawOk != null && String(rawOk).trim()
      ? expandEnvPlaceholder(String(rawOk))
      : "";
  return {
    openaiApiKey: directKey || apiKeys.openai || null,
    openaiBaseUrl: ob || apiBaseUrls.openai || null,
    narrationImageModel: s.narration_image_model ?? "gpt-4o-mini",
    maxFramesPerSegment: Number(s.max_frames_per_segment ?? 24),
    narrationFrameMaxEdge: Number(s.narration_frame_max_edge ?? 768),
    ffmpegPath: s.ffmpeg_path ?? "ffmpeg",
    defaultPromptStyle: s.default_prompt_style ?? "documentary",
    videocaptionerBin: s.videocaptioner_bin ?? null,
    narrationApiUrl: s.narration_api_url ?? null,
    narrationProvider: String(s.narration_provider ?? "openai").trim().toLowerCase() || "openai",
    apiKeys,
    apiBaseUrls,
    providerModels: normalizeProviderModelsObject(s.provider_models ?? {}),
    narrationModel:
      s.narration_model != null && String(s.narration_model).trim()
        ? expandEnvPlaceholder(String(s.narration_model))
        : null,
    narrationModelIndex: (() => {
      const n = Number(s.narration_model_index ?? 0);
      return Number.isFinite(n) && n >= 0 ? n : 0;
    })(),
    providerModelCatalog: normalizeProviderModelCatalogObject(s.provider_model_catalog ?? {}),
  };
}

/** Slug -> list of model ids (YAML ``provider_model_catalog`` / ``PROVIDER_MODEL_CATALOG_JSON``). */
export function normalizeProviderModelCatalogObject(raw) {
  const out = {};
  if (!raw || typeof raw !== "object") return out;
  for (const [k, v] of Object.entries(raw)) {
    const slug = String(k).trim().toLowerCase();
    if (!slug) continue;
    if (!Array.isArray(v)) continue;
    const ids = [];
    for (const item of v) {
      if (item == null) continue;
      const expanded = expandEnvPlaceholder(String(item));
      if (expanded) ids.push(expanded);
    }
    if (ids.length > 0) out[slug] = ids;
  }
  return out;
}

export function normalizeProviderModelsObject(raw) {
  const out = {};
  if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw)) {
      if (v == null) continue;
      const expanded = expandEnvPlaceholder(v);
      if (!expanded) continue;
      out[String(k).trim().toLowerCase()] = expanded;
    }
  }
  return out;
}

export function normalizeApiBaseUrlsObject(raw) {
  const out = {};
  if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw)) {
      if (v == null) continue;
      const expanded = expandEnvPlaceholder(v);
      if (!expanded) continue;
      out[String(k).trim().toLowerCase()] = expanded;
    }
  }
  return out;
}

export function normalizeApiKeysObject(raw) {
  const out = {};
  if (raw && typeof raw === "object") {
    for (const [k, v] of Object.entries(raw)) {
      if (v == null) continue;
      const expanded = expandEnvPlaceholder(v);
      if (!expanded) continue;
      out[String(k).trim().toLowerCase()] = expanded;
    }
  }
  return out;
}

export function mergeEnvApiKeys(keys, envApiKeys) {
  return { ...keys, ...envApiKeys };
}
