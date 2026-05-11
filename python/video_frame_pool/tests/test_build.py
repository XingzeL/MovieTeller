import json
from pathlib import Path

from movieteller_config.schema import settings_from_dict

from video_frame_pool.build import build_frame_pool
from video_frame_pool.types import ShotSpan


def test_build_frame_pool_crops_dialogue_intervals_and_samples_remaining_ranges(
    monkeypatch, tmp_path
):
    video = tmp_path / "demo.mp4"
    srt = tmp_path / "demo.srt"
    video.write_bytes(b"x")
    srt.write_text(
        """1
00:00:02,100 --> 00:00:02,400
hello
""",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "video_frame_pool.build.detect_shots",
        lambda *args, **kwargs: (
            ShotSpan(shot_id=0, start_sec=0.0, end_sec=2.0),
            ShotSpan(shot_id=1, start_sec=2.0, end_sec=4.0),
        ),
    )

    def fake_write_png_frame(video_path, *, t_sec, output_path, **kwargs):
        del video_path, kwargs
        Path(output_path).write_bytes(b"\x89PNG\r\n\x1a\nframe" + str(t_sec).encode("ascii"))

    monkeypatch.setattr("video_frame_pool.build._write_png_frame", fake_write_png_frame)

    settings = settings_from_dict(
        {
            "narration_image_model": "x",
            "pool_frames_per_shot_min": 1,
            "pool_frames_per_shot_max": 2,
            "dialogue_overlap_threshold": 0.05,
        }
    )
    result = build_frame_pool(
        video_path=str(video),
        srt_path=str(srt),
        output_dir=str(tmp_path / "pool"),
        settings=settings,
    )
    assert result.shot_count == 2
    assert result.non_dialogue_shot_count == 2
    assert result.frame_count == 4

    manifest_lines = (tmp_path / "pool" / "manifest.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(manifest_lines) == 4
    manifest_rows = [json.loads(line) for line in manifest_lines]
    assert {row["shotId"] for row in manifest_rows} == {0, 1}
    shot1_times = [row["tSec"] for row in manifest_rows if row["shotId"] == 1]
    assert len(shot1_times) == 2
    assert all((2.0 <= t <= 2.1) or (2.4 <= t <= 4.0) for t in shot1_times)
    assert all(not (2.1 < t < 2.4) for t in shot1_times)

    shots = json.loads((tmp_path / "pool" / "shots.json").read_text(encoding="utf-8"))
    assert shots["shots"][0]["isDialogue"] is False
    assert shots["shots"][1]["isDialogue"] is True
    assert shots["shots"][1]["dialogueOverlapRatio"] > 0.05
    assert len(shots["shots"][1]["nonDialogueRanges"]) == 2
