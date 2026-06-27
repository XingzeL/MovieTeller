import os

import pytest

from video_ingest.bilibili_meta import (
    extract_bvid,
    is_bilibili_url,
    parse_bilibili_meta,
)


def test_is_bilibili_url():
    assert is_bilibili_url("https://www.bilibili.com/video/BV1Yx411578x/")
    assert not is_bilibili_url("https://www.youtube.com/watch?v=abc")


def test_extract_bvid():
    assert (
        extract_bvid("https://www.bilibili.com/video/BV1Yx411578x/?spm_id_from=333")
        == "BV1Yx411578x"
    )


def test_parse_bilibili_meta_live():
    if not os.environ.get("RUN_BILIBILI_DOWNLOAD_INTEGRATION"):
        pytest.skip("set RUN_BILIBILI_DOWNLOAD_INTEGRATION=1 for live B站 API")

    url = "https://www.bilibili.com/video/BV1Yx411578x/"
    meta = parse_bilibili_meta(url)
    assert meta["id"] == "BV1Yx411578x"
    assert "小猪佩奇" in (meta.get("title") or "")
    assert meta.get("duration") == 251
