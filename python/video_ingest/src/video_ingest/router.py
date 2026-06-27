"""Platform router for remote video ingest."""

from __future__ import annotations

from .bilibili_meta import is_bilibili_url, parse_bilibili_meta
from .douyin import is_douyin_url, parse_douyin_video, download_douyin_video
from .downloader import VideoDownloader


def parse_video(url: str) -> dict:
    if is_douyin_url(url):
        return parse_douyin_video(url)
    if is_bilibili_url(url):
        return parse_bilibili_meta(url)
    return VideoDownloader().parse(url)


def download_video(url: str, output_dir: str, *, max_height: int = 720) -> dict:
    if is_douyin_url(url):
        return download_douyin_video(url, output_dir)
    return VideoDownloader().download(url, output_dir, max_height=max_height)
