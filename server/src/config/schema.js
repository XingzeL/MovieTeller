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
  videocaptioner_asr: "bijian",
  videocaptioner_language: "auto",
  videocaptioner_transcribe_timeout_ms: null,
  narration_api_url: null,
  api_keys: {},
  api_base_urls: {},
  narration_provider_models: {},
  narration_provider_model_catalog: {},
  narration_polish_provider_models: {},
  narration_polish_provider_model_catalog: {},
  narration_model: null,
  narration_model_index: 0,
  narration_polish_enabled: false,
  narration_polish_provider: null,
  narration_polish_model: null,
  narration_polish_model_index: 0,
  narration_polish_target_wpm: 150,
  narration_polish_cefr_level: "B1",
  narration_polish_strength: "medium",
  narration_polish_safety_margin_sec: 0.2,
  narration_speech_enabled: false,
  narration_speech_provider: "edge_tts",
  narration_speech_voice: "en-US-EmmaMultilingualNeural",
  narration_speech_rate: "+0%",
  narration_speech_volume: "+0%",
  narration_speech_pitch: "+0Hz",
  narration_speech_boundary: "SentenceBoundary",
  narration_video_background_audio_volume: 0.35,
  narration_video_speech_audio_volume: 1.0,
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
    videocaptionerAsr: String(s.videocaptioner_asr ?? "bijian").trim().toLowerCase() || "bijian",
    videocaptionerLanguage: String(s.videocaptioner_language ?? "auto").trim() || "auto",
    videocaptionerTranscribeTimeoutMs:
      s.videocaptioner_transcribe_timeout_ms == null || s.videocaptioner_transcribe_timeout_ms === ""
        ? null
        : Number(s.videocaptioner_transcribe_timeout_ms),
    narrationApiUrl: s.narration_api_url ?? null,
    narrationProvider: String(s.narration_provider ?? "openai").trim().toLowerCase() || "openai",
    apiKeys,
    apiBaseUrls,
    narrationProviderModels: normalizeProviderModelsObject(s.narration_provider_models ?? {}),
    narrationModel:
      s.narration_model != null && String(s.narration_model).trim()
        ? expandEnvPlaceholder(String(s.narration_model))
        : null,
    narrationModelIndex: (() => {
      const n = Number(s.narration_model_index ?? 0);
      return Number.isFinite(n) && n >= 0 ? n : 0;
    })(),
    narrationPolishEnabled: (() => {
      const raw = String(s.narration_polish_enabled ?? "").trim().toLowerCase();
      return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
    })(),
    narrationPolishProvider:
      s.narration_polish_provider != null && String(s.narration_polish_provider).trim()
        ? String(s.narration_polish_provider).trim().toLowerCase()
        : null,
    narrationPolishModel:
      s.narration_polish_model != null && String(s.narration_polish_model).trim()
        ? expandEnvPlaceholder(String(s.narration_polish_model))
        : null,
    narrationPolishProviderModels: normalizeProviderModelsObject(
      s.narration_polish_provider_models ?? {}
    ),
    narrationPolishModelIndex: (() => {
      const n = Number(s.narration_polish_model_index ?? 0);
      return Number.isFinite(n) && n >= 0 ? n : 0;
    })(),
    narrationPolishTargetWpm: (() => {
      const n = Number(s.narration_polish_target_wpm ?? 150);
      return Number.isFinite(n) && n > 0 ? Math.floor(n) : 150;
    })(),
    narrationPolishCefrLevel:
      String(s.narration_polish_cefr_level ?? "B1").trim().toUpperCase() || "B1",
    narrationPolishStrength:
      String(s.narration_polish_strength ?? "medium").trim().toLowerCase() || "medium",
    narrationPolishSafetyMarginSec: (() => {
      const n = Number(s.narration_polish_safety_margin_sec ?? 0.2);
      return Number.isFinite(n) && n >= 0 ? n : 0.2;
    })(),
    narrationSpeechEnabled: (() => {
      const raw = String(s.narration_speech_enabled ?? "").trim().toLowerCase();
      return raw === "1" || raw === "true" || raw === "yes" || raw === "on";
    })(),
    narrationSpeechProvider:
      String(s.narration_speech_provider ?? "edge_tts").trim().toLowerCase() || "edge_tts",
    narrationSpeechVoice:
      String(s.narration_speech_voice ?? "en-US-EmmaMultilingualNeural").trim() ||
      "en-US-EmmaMultilingualNeural",
    narrationSpeechRate: String(s.narration_speech_rate ?? "+0%").trim() || "+0%",
    narrationSpeechVolume: String(s.narration_speech_volume ?? "+0%").trim() || "+0%",
    narrationSpeechPitch: String(s.narration_speech_pitch ?? "+0Hz").trim() || "+0Hz",
    narrationSpeechBoundary:
      String(s.narration_speech_boundary ?? "SentenceBoundary").trim() ||
      "SentenceBoundary",
    narrationVideoBackgroundAudioVolume: (() => {
      const n = Number(s.narration_video_background_audio_volume ?? 0.35);
      return Number.isFinite(n) && n >= 0 ? n : 0.35;
    })(),
    narrationVideoSpeechAudioVolume: (() => {
      const n = Number(s.narration_video_speech_audio_volume ?? 1.0);
      return Number.isFinite(n) && n >= 0 ? n : 1.0;
    })(),
    narrationProviderModelCatalog: normalizeProviderModelCatalogObject(
      s.narration_provider_model_catalog ?? {}
    ),
    narrationPolishProviderModelCatalog: normalizeProviderModelCatalogObject(
      s.narration_polish_provider_model_catalog ?? {}
    ),
  };
}

/** Slug -> list of model ids. */
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
