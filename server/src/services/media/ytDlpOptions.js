/**
 * @param {string} url
 */
function isBilibiliUrl(url) {
  try {
    const host = new URL(url).hostname.toLowerCase();
    return host === "bilibili.com" || host.endsWith(".bilibili.com");
  } catch {
    return /bilibili\.com/i.test(url);
  }
}

/**
 * Extra yt-dlp CLI flags from config / environment (cookies, site tweaks).
 * @param {{ yt_dlp_cookies_from_browser?: string | null, yt_dlp_cookies?: string | null, yt_dlp_impersonate?: string | null }} [config]
 * @param {string} [url]
 * @returns {string[]}
 */
export function buildYtDlpExtraArgs(config = {}, url = "") {
  const args = [];
  const fromBrowser =
    (process.env.YT_DLP_COOKIES_FROM_BROWSER &&
      String(process.env.YT_DLP_COOKIES_FROM_BROWSER).trim()) ||
    (config.yt_dlp_cookies_from_browser &&
      String(config.yt_dlp_cookies_from_browser).trim());
  if (fromBrowser) {
    args.push("--cookies-from-browser", fromBrowser);
  }

  const cookiesFile =
    (process.env.YT_DLP_COOKIES && String(process.env.YT_DLP_COOKIES).trim()) ||
    (config.yt_dlp_cookies && String(config.yt_dlp_cookies).trim());
  if (cookiesFile) {
    args.push("--cookies", cookiesFile);
  }

  const impersonate =
    (process.env.YT_DLP_IMPERSONATE && String(process.env.YT_DLP_IMPERSONATE).trim()) ||
    (config.yt_dlp_impersonate && String(config.yt_dlp_impersonate).trim());
  if (impersonate) {
    args.push("--impersonate", impersonate);
  }

  if (isBilibiliUrl(url)) {
    args.push("--add-header", "Referer:https://www.bilibili.com/");
  }

  return args;
}

/**
 * @param {string} message
 */
export function summarizeYtDlpFailure(message) {
  const detail = String(message || "").trim();
  if (!detail) {
    return "请检查链接是否有效、视频是否公开，或改用本地上传。";
  }

  if (/Sign in to confirm you.?re not a bot|not a bot/i.test(detail)) {
    return "YouTube 触发了机器人验证。请在服务器 .env 中设置 YT_DLP_COOKIES_FROM_BROWSER=chrome（或导出 cookies.txt），或改用本地上传。";
  }
  if (/Private video|This video is private/i.test(detail)) {
    return "该视频为私密或需登录观看，无法下载。";
  }
  if (/Video unavailable|unavailable/i.test(detail)) {
    return "视频不可用（可能已删除、地区受限或需登录）。";
  }
  if (/Unsupported URL|Unsupported url/i.test(detail)) {
    return "该链接格式不受 yt-dlp 支持。";
  }
  if (/HTTP Error 412|Precondition Failed/i.test(detail)) {
    if (/BiliBili|bilibili/i.test(detail)) {
      return "B站反爬拦截（HTTP 412）。请用浏览器打开 bilibili.com 后，用扩展导出 cookies.txt，在 .env 设置 YT_DLP_COOKIES=路径；或改用本地上传。详见 docs/reference/local-development.md";
    }
    return "站点拒绝了下载（HTTP 412）。请配置 YT_DLP_COOKIES 或 YT_DLP_COOKIES_FROM_BROWSER，或改用本地上传。";
  }
  if (/timed out/i.test(detail)) {
    return "下载超时，请稍后重试或换用更短视频。";
  }
  if (/ENOENT|spawn yt-dlp/i.test(detail)) {
    return "服务器未安装 yt-dlp。请执行 pip install yt-dlp 或 brew install yt-dlp。";
  }

  const cleaned = detail.replace(/^yt-dlp failed \(\d+\):\s*/i, "").trim();
  if (cleaned.length > 0 && cleaned.length <= 220) {
    return cleaned;
  }
  return "请检查链接是否有效、视频是否公开，或改用本地上传。";
}
