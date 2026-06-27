"""Map YT_DLP_* environment variables to yt-dlp options."""

from __future__ import annotations

import os
from typing import Any


def build_yt_dlp_opts(url: str = "") -> dict[str, Any]:
    opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "noplaylist": True,
    }

    cookies_file = os.environ.get("YT_DLP_COOKIES", "").strip()
    if cookies_file:
        if not os.path.isabs(cookies_file):
            repo_root = os.environ.get("MOVIE_TELLER_REPO_ROOT", "").strip()
            if repo_root:
                cookies_file = os.path.join(repo_root, cookies_file)
            else:
                cookies_file = os.path.abspath(cookies_file)
        opts["cookiefile"] = cookies_file
    else:
        from_browser = os.environ.get("YT_DLP_COOKIES_FROM_BROWSER", "").strip()
        if from_browser:
            opts["cookiesfrombrowser"] = (from_browser,)

    impersonate = os.environ.get("YT_DLP_IMPERSONATE", "").strip()
    if impersonate:
        opts["impersonate"] = impersonate

    if url and "bilibili.com" in url.lower():
        opts.setdefault("http_headers", {})
        opts["http_headers"]["Referer"] = "https://www.bilibili.com/"

    return opts
