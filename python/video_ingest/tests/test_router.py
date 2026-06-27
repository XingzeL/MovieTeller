import pytest

from video_ingest.douyin import is_douyin_url
from video_ingest.router import parse_video


def test_is_douyin_url():
    assert is_douyin_url("https://v.douyin.com/abc/")
    assert not is_douyin_url("https://www.youtube.com/watch?v=abc")


def test_parse_video_delegates_to_downloader(monkeypatch):
    called = {"url": None}

    class FakeDownloader:
        def parse(self, url: str) -> dict:
            called["url"] = url
            return {"title": "t", "duration": 12, "platform": "generic"}

    monkeypatch.setattr("video_ingest.router.VideoDownloader", FakeDownloader)
    result = parse_video("https://example.com/v")
    assert called["url"] == "https://example.com/v"
    assert result["duration"] == 12
