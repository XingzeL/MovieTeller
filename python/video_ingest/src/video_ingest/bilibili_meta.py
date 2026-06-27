"""Bilibili metadata via public view API (parse only; video bytes still need yt-dlp + cookies)."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import requests

_VIEW_API = "https://api.bilibili.com/x/web-interface/view"
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.bilibili.com/",
}


def is_bilibili_url(url: str) -> bool:
    try:
        host = urlparse(url).netloc.lower()
        return "bilibili.com" in host or host == "b23.tv"
    except Exception:
        return "bilibili.com" in url.lower() or "b23.tv" in url.lower()


def extract_bvid(url: str) -> str | None:
    match = re.search(r"(BV[0-9A-Za-z]+)", url)
    return match.group(1) if match else None


def parse_bilibili_meta(url: str) -> dict[str, Any]:
    bvid = extract_bvid(url)
    if not bvid:
        raise ValueError("could not extract BV id from bilibili URL")

    resp = requests.get(
        _VIEW_API,
        params={"bvid": bvid},
        headers={**_HEADERS, "Referer": f"https://www.bilibili.com/video/{bvid}"},
        timeout=30,
    )
    resp.raise_for_status()
    payload = resp.json()
    if payload.get("code") != 0:
        raise ValueError(payload.get("message") or "bilibili view API failed")

    data = payload.get("data") or {}
    owner = data.get("owner") or {}
    duration = data.get("duration")
    return {
        "id": bvid,
        "title": data.get("title"),
        "thumbnail": data.get("pic"),
        "duration": int(duration) if duration else None,
        "platform": "bilibili",
        "uploader": owner.get("name"),
    }
