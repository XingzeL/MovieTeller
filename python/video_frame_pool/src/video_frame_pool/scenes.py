from __future__ import annotations

from media_utils import ffprobe_path_for, probe_duration_sec

from video_frame_pool.types import ShotSpan


def _merge_short_shots(shots: list[ShotSpan], *, merge_sec: float) -> list[ShotSpan]:
    if not shots or merge_sec <= 0:
        return shots
    merged: list[ShotSpan] = []
    for shot in shots:
        if not merged:
            merged.append(shot)
            continue
        prev = merged[-1]
        if prev.duration_sec < merge_sec:
            merged[-1] = ShotSpan(
                shot_id=prev.shot_id,
                start_sec=prev.start_sec,
                end_sec=shot.end_sec,
            )
            continue
        merged.append(shot)
    if len(merged) >= 2 and merged[-1].duration_sec < merge_sec:
        last = merged.pop()
        prev = merged[-1]
        merged[-1] = ShotSpan(
            shot_id=prev.shot_id,
            start_sec=prev.start_sec,
            end_sec=last.end_sec,
        )
    out: list[ShotSpan] = []
    for idx, shot in enumerate(merged):
        out.append(ShotSpan(shot_id=idx, start_sec=shot.start_sec, end_sec=shot.end_sec))
    return out


def detect_shots(
    video_path: str,
    *,
    ffmpeg_bin: str = "ffmpeg",
    merge_sec: float = 0.25,
) -> tuple[ShotSpan, ...]:
    try:
        from scenedetect import SceneManager, open_video
        from scenedetect.detectors import ContentDetector
    except ImportError as exc:
        raise RuntimeError(
            "PySceneDetect is required for frame-pool build. Install 'scenedetect'."
        ) from exc

    duration_sec = probe_duration_sec(
        video_path,
        ffprobe_bin=ffprobe_path_for(ffmpeg_bin),
    )
    video = open_video(video_path)
    scene_manager = SceneManager()
    scene_manager.add_detector(ContentDetector())
    scene_manager.detect_scenes(video)
    scene_list = scene_manager.get_scene_list()

    raw: list[ShotSpan] = []
    if scene_list:
        for idx, (start_tc, end_tc) in enumerate(scene_list):
            raw.append(
                ShotSpan(
                    shot_id=idx,
                    start_sec=max(0.0, float(start_tc.get_seconds())),
                    end_sec=min(duration_sec, float(end_tc.get_seconds())),
                )
            )
    else:
        raw.append(ShotSpan(shot_id=0, start_sec=0.0, end_sec=duration_sec))

    normalized = [shot for shot in raw if shot.end_sec > shot.start_sec]
    return tuple(_merge_short_shots(normalized, merge_sec=merge_sec))
