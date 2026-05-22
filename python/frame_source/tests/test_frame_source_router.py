import json
from unittest.mock import MagicMock

import pytest

from frame_source import FrameRequest, FrameSourceOptions, get_frames_for_segment
from pipeline_types import FrameBatch


def _write_png(path, label: str) -> None:
    path.write_bytes(b"\x89PNG\r\n\x1a\n" + label.encode("ascii"))


def test_get_frames_for_segment_uniform(fake_concat_png_stdout, tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
    calls = []

    def fake_run(cmd, capture_output, check):
        calls.append(cmd)
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = fake_concat_png_stdout
        proc.stderr = b""
        return proc

    batch = get_frames_for_segment(
        FrameRequest(
            video_path=str(video),
            start_sec=1.0,
            end_sec=5.0,
            duration_sec=4.0,
            strategy="uniform",
        ),
        options=FrameSourceOptions(
            ffmpeg_bin="ffmpeg",
            max_frames_per_segment=8,
            max_edge_pixels=512,
        ),
        subprocess_run=fake_run,
    )
    assert isinstance(batch, FrameBatch)
    assert batch.source == "uniform"
    assert len(batch.frames_base64_png) == 2
    assert len(batch.frame_times_sec) == 2
    assert "-ss" in calls[0]


def test_get_frames_for_segment_frame_pool(tmp_path):
    pool = tmp_path / "pool"
    images = pool / "images"
    images.mkdir(parents=True)
    (pool / "shots.json").write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "videoPath": "demo.mp4",
                "shots": [
                    {"shotId": 0, "startSec": 0.0, "endSec": 4.0, "isDialogue": False},
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

    batch = get_frames_for_segment(
        FrameRequest(
            video_path="demo.mp4",
            start_sec=0.0,
            end_sec=2.0,
            duration_sec=2.0,
            strategy="frame_pool",
            frame_pool_manifest=str(pool / "manifest.jsonl"),
        ),
        options=FrameSourceOptions(
            ffmpeg_bin="ffmpeg",
            max_frames_per_segment=4,
            max_edge_pixels=512,
        ),
    )
    assert batch.source == "frame_pool"
    assert batch.shot_ids == (0,)


def test_get_frames_for_segment_pool_falls_back_to_uniform(
    fake_concat_png_stdout, tmp_path
):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"x")
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

    def fake_run(cmd, capture_output, check):
        proc = MagicMock()
        proc.returncode = 0
        proc.stdout = fake_concat_png_stdout
        proc.stderr = b""
        return proc

    batch = get_frames_for_segment(
        FrameRequest(
            video_path=str(video),
            start_sec=4.0,
            end_sec=5.0,
            duration_sec=1.0,
            strategy="frame_pool",
            frame_pool_manifest=str(pool / "manifest.jsonl"),
        ),
        options=FrameSourceOptions(
            ffmpeg_bin="ffmpeg",
            max_frames_per_segment=4,
            max_edge_pixels=512,
            pool_miss_uniform_max_frames=2,
        ),
        subprocess_run=fake_run,
    )
    assert batch.source == "uniform_fallback"
    assert len(batch.frames_base64_png) == 2


def test_get_frames_for_segment_pool_requires_manifest():
    with pytest.raises(ValueError):
        get_frames_for_segment(
            FrameRequest(
                video_path="demo.mp4",
                start_sec=0.0,
                end_sec=1.0,
                duration_sec=1.0,
                strategy="frame_pool",
                frame_pool_manifest=None,
            ),
            options=FrameSourceOptions(
                ffmpeg_bin="ffmpeg",
                max_frames_per_segment=4,
                max_edge_pixels=512,
            ),
        )
