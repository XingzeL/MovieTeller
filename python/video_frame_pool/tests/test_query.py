import json

import pytest

from video_frame_pool.errors import PoolManifestError, PoolWindowMiss
from video_frame_pool.query import query_frame_pool


def _write_png(path, label: str) -> None:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + label.encode("ascii"))


def test_query_frame_pool_respects_budget_across_shots(tmp_path):
    pool = tmp_path / "pool"
    images = pool / "images"
    images.mkdir(parents=True)
    shots = {
        "schemaVersion": 1,
        "videoPath": "demo.mp4",
        "shots": [
            {"shotId": 0, "startSec": 0.0, "endSec": 4.0, "isDialogue": False},
            {"shotId": 1, "startSec": 4.0, "endSec": 8.0, "isDialogue": False},
        ],
    }
    (pool / "shots.json").write_text(json.dumps(shots), encoding="utf-8")
    rows = []
    for idx, (shot_id, t_sec) in enumerate([(0, 1.0), (0, 2.0), (1, 5.0), (1, 6.0)], start=1):
        image_ref = f"images/{idx:06d}.png"
        _write_png(pool / image_ref, f"{shot_id}-{t_sec}")
        rows.append(
            json.dumps(
                {
                    "schemaVersion": 1,
                    "shotId": shot_id,
                    "tSec": t_sec,
                    "imageRef": image_ref,
                    "embeddingIndex": None,
                }
            )
        )
    manifest = pool / "manifest.jsonl"
    manifest.write_text("\n".join(rows) + "\n", encoding="utf-8")

    result = query_frame_pool(
        manifest_path=str(manifest),
        start_sec=0.0,
        end_sec=8.0,
        budget=2,
    )
    assert len(result.frames_base64_png) == 2
    assert set(result.shot_ids) == {0, 1}


def test_query_frame_pool_raises_on_window_miss(tmp_path):
    pool = tmp_path / "pool"
    images = pool / "images"
    images.mkdir(parents=True)
    (pool / "shots.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "videoPath": "demo.mp4",
                "shots": [
                    {"shotId": 0, "startSec": 0.0, "endSec": 2.0, "isDialogue": False},
                ],
            }
        ),
        encoding="utf-8",
    )
    _write_png(images / "000001.png", "x")
    (pool / "manifest.jsonl").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "shotId": 0,
                "tSec": 1.0,
                "imageRef": "images/000001.png",
                "embeddingIndex": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    with pytest.raises(PoolWindowMiss):
        query_frame_pool(
            manifest_path=str(pool / "manifest.jsonl"),
            start_sec=4.0,
            end_sec=5.0,
            budget=2,
        )


def test_query_frame_pool_raises_on_missing_shots_file(tmp_path):
    manifest = tmp_path / "manifest.jsonl"
    manifest.write_text("", encoding="utf-8")
    with pytest.raises(PoolManifestError):
        query_frame_pool(
            manifest_path=str(manifest),
            start_sec=0.0,
            end_sec=1.0,
            budget=1,
        )
