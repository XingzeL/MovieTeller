/**
 * Resolve `original_source` for API responses (history card titles).
 * Primary: workflow.json; fallback: request.json written at create time.
 */

/**
 * @param {Record<string, unknown>} record
 * @param {{ originalFilename?: string | null, sourceUrl?: string | null }} [requestMeta]
 * @returns {Record<string, unknown> | null}
 */
export function resolveOriginalSourceForDto(record, requestMeta = {}) {
  const existing = record.original_source;
  if (existing && typeof existing === "object" && !Array.isArray(existing)) {
    return existing;
  }

  const sourceUrl =
    typeof requestMeta.sourceUrl === "string" && requestMeta.sourceUrl.trim()
      ? requestMeta.sourceUrl.trim()
      : null;
  if (sourceUrl) {
    return {
      type: "remote_url",
      source_url: sourceUrl,
      original_filename: null,
    };
  }

  const originalFilename =
    typeof requestMeta.originalFilename === "string" &&
    requestMeta.originalFilename.trim()
      ? requestMeta.originalFilename.trim()
      : null;
  if (originalFilename) {
    return {
      type: "local_upload",
      source_url: null,
      original_filename: originalFilename,
    };
  }

  return null;
}
