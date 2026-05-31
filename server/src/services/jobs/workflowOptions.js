const BOOL_FIELDS = [
  "enableSubtitleContext",
  "enablePolish",
  "enableSpeech",
  "enableEmbedVideo",
  "forceRebuildSubtitles",
  "forceRebuildFramePool",
  "forceRebuildSubtitleContext",
];

const FLOAT_FIELDS = ["minGapSec", "subtitleGuardSec"];
const STRING_FIELDS = [
  "cefrLevel",
  "promptStyle",
  "ttsVoice",
  "ttsLanguage",
  "sourceLanguage",
  "narrationLanguage",
  "subtitleLanguage",
];

/**
 * @param {Record<string, unknown>} body multer fields are strings
 */
export function workflowOptionsFromForm(body) {
  const out = {};
  for (const key of BOOL_FIELDS) {
    if (body[key] === undefined || body[key] === "") continue;
    const raw = String(body[key]).trim().toLowerCase();
    out[key] =
      raw === "1" || raw === "true" || raw === "yes" || raw === "on";
  }
  for (const key of FLOAT_FIELDS) {
    if (body[key] === undefined || body[key] === "") continue;
    const value = Number(body[key]);
    if (!Number.isNaN(value)) out[key] = value;
  }
  for (const key of STRING_FIELDS) {
    if (body[key] === undefined || body[key] === "") continue;
    out[key] = String(body[key]).trim();
  }
  return out;
}
