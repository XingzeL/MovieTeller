/**
 * Map server-side yt-dlp / download errors to user-facing Chinese hints.
 */
export function formatVideoDownloadError(serverError?: string | null): string {
  const detail = String(serverError || '').trim()
  if (!detail) {
    return '请检查链接是否有效、视频是否公开，或改用本地上传。'
  }

  if (/Sign in to confirm you.?re not a bot|not a bot/i.test(detail)) {
    return 'YouTube 触发了机器人验证。需在服务器配置 YT_DLP_COOKIES_FROM_BROWSER=chrome，或改用本地上传。'
  }
  if (/Private video|This video is private/i.test(detail)) {
    return '该视频为私密或需登录观看，无法下载。'
  }
  if (/Video unavailable|unavailable/i.test(detail)) {
    return '视频不可用（可能已删除、地区受限或需登录）。'
  }
  if (/Unsupported URL/i.test(detail)) {
    return '该链接格式不受支持。'
  }
  if (/HTTP Error 412|Precondition Failed/i.test(detail)) {
    if (/BiliBili|bilibili/i.test(detail)) {
      return 'B站反爬（HTTP 412）。请导出 bilibili.com 的 cookies.txt 并在服务器设置 YT_DLP_COOKIES，或改用本地上传。'
    }
    return '站点拒绝了下载（HTTP 412）。请配置服务器 Cookies 或改用本地上传。'
  }
  if (/timed out/i.test(detail)) {
    return '下载超时，请稍后重试或换用更短视频。'
  }
  if (/ENOENT|spawn/i.test(detail) && /yt-dlp/i.test(detail)) {
    return '服务器未安装 yt-dlp。'
  }

  const cleaned = detail.replace(/^yt-dlp failed \(\d+\):\s*/i, '').trim()
  if (cleaned.length > 0 && cleaned.length <= 220) {
    return cleaned
  }
  return '请检查链接是否有效、视频是否公开，或改用本地上传。'
}
