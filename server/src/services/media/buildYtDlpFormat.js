/**
 * @param {{ maxHeight?: number }} [opts]
 */
export function buildYtDlpFormatSelector(opts = {}) {
  const raw =
    process.env.YT_DLP_MAX_HEIGHT != null && String(process.env.YT_DLP_MAX_HEIGHT).trim() !== ""
      ? Number(process.env.YT_DLP_MAX_HEIGHT)
      : opts.maxHeight;
  const maxHeight =
    Number.isFinite(raw) && raw > 0 ? Math.floor(raw) : 720;
  return `bestvideo[height<=${maxHeight}]+bestaudio/best[height<=${maxHeight}]/best`;
}
