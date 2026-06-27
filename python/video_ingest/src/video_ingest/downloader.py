"""yt-dlp based parse/download."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yt_dlp

from .cookies import build_yt_dlp_opts


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/*?:"<>|]', "_", name).strip() or "video"


def _normalize_parse(info: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "thumbnail": info.get("thumbnail"),
        "duration": info.get("duration"),
        "platform": info.get("extractor") or info.get("extractor_key"),
        "uploader": info.get("uploader") or info.get("channel"),
    }


class VideoDownloader:
    def parse(self, url: str) -> dict[str, Any]:
        ydl_opts = {
            **build_yt_dlp_opts(url),
            "skip_download": True,
            # yt-dlp 2026.06+ may raise "Requested format is not available" during metadata-only extract.
            "ignore_no_formats_error": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
        if not info:
            raise ValueError("无法解析该链接")
        return _normalize_parse(info)

    def download(self, url: str, output_dir: str, *, max_height: int = 720) -> dict[str, Any]:
        os.makedirs(output_dir, exist_ok=True)
        outtmpl = str(Path(output_dir) / "source.%(ext)s")
        fmt = (
            f"bestvideo[height<={max_height}]+bestaudio/"
            f"best[height<={max_height}]/best"
        )
        ydl_opts = {
            **build_yt_dlp_opts(url),
            "format": fmt,
            "outtmpl": outtmpl,
            "merge_output_format": "mp4",
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            if not info:
                raise ValueError("下载失败")
            filepath = ydl.prepare_filename(info)

        if not os.path.exists(filepath):
            candidates = list(Path(output_dir).glob("source.*"))
            if not candidates:
                raise ValueError("下载完成但未找到输出文件")
            filepath = str(candidates[0])

        title = _sanitize_filename(str(info.get("title") or "video"))
        ext = Path(filepath).suffix or ".mp4"
        size = os.path.getsize(filepath)
        return {
            "path": filepath,
            "filename": os.path.basename(filepath),
            "originalname": f"{title}{ext}",
            "mimetype": "video/mp4",
            "size": size,
            "title": info.get("title"),
            "duration": info.get("duration"),
        }
