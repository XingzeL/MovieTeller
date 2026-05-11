from __future__ import annotations

import json
import subprocess
from pathlib import Path

from movieteller_config import load_settings
from pipeline_types import SubtitleCue
from subtitle_extraction.parse_srt import parse_srt_text

from video_frame_pool.scenes import detect_shots
from video_frame_pool.storage import write_manifest, write_shots
from video_frame_pool.types import FramePoolBuildResult, FramePoolEntry, ShotSpan


def _normalize_cue_spans(cues: list[SubtitleCue]) -> list[tuple[float, float]]:
    spans = sorted(
        ((cue.start_sec, cue.end_sec) for cue in cues if cue.end_sec > cue.start_sec),
        key=lambda item: (item[0], item[1]),
    )
    if not spans:
        return []
    out: list[tuple[float, float]] = [spans[0]]
    for start, end in spans[1:]:
        prev_start, prev_end = out[-1]
        if start <= prev_end:
            out[-1] = (prev_start, max(prev_end, end))
        else:
            out.append((start, end))
    return out


def _shot_dialogue_overlap_ratio(shot: ShotSpan, cue_spans: list[tuple[float, float]]) -> float:
    total = 0.0
    for cue_start, cue_end in cue_spans:
        overlap = min(shot.end_sec, cue_end) - max(shot.start_sec, cue_start)
        if overlap > 0:
            total += overlap
    if shot.duration_sec <= 0:
        return 0.0
    return total / shot.duration_sec


def _subtract_cue_spans(
    shot: ShotSpan,
    cue_spans: list[tuple[float, float]],
) -> tuple[tuple[float, float], ...]:
    cursor = shot.start_sec
    out: list[tuple[float, float]] = []
    for cue_start, cue_end in cue_spans:
        overlap_start = max(shot.start_sec, cue_start)
        overlap_end = min(shot.end_sec, cue_end)
        if overlap_end <= overlap_start:
            continue
        if overlap_start > cursor:
            out.append((cursor, overlap_start))
        cursor = max(cursor, overlap_end)
        if cursor >= shot.end_sec:
            break
    if cursor < shot.end_sec:
        out.append((cursor, shot.end_sec))
    return tuple(
        (start_sec, end_sec)
        for start_sec, end_sec in out
        if end_sec > start_sec
    )


def _tag_dialogue_shots(
    shots: tuple[ShotSpan, ...],
    cues: list[SubtitleCue],
    *,
    threshold: float,
) -> tuple[ShotSpan, ...]:
    cue_spans = _normalize_cue_spans(cues)
    out: list[ShotSpan] = []
    for shot in shots:
        ratio = _shot_dialogue_overlap_ratio(shot, cue_spans)
        non_dialogue_ranges = _subtract_cue_spans(shot, cue_spans)
        out.append(
            ShotSpan(
                shot_id=shot.shot_id,
                start_sec=shot.start_sec,
                end_sec=shot.end_sec,
                is_dialogue=ratio > threshold,
                dialogue_overlap_ratio=ratio,
                non_dialogue_ranges=non_dialogue_ranges,
            )
        )
    return tuple(out)


def _sample_count(duration_sec: float, *, min_frames: int, max_frames: int, rate: float | None) -> int:
    lo = max(1, int(min_frames))
    hi = max(lo, int(max_frames))
    if rate is None:
        return hi
    raw = int(round(max(0.0, duration_sec) * float(rate)))
    return max(lo, min(hi, raw))


def _sample_timestamps(start_sec: float, end_sec: float, count: int) -> tuple[float, ...]:
    if count <= 0:
        return ()
    duration = end_sec - start_sec
    if count == 1:
        return (start_sec + duration / 2.0,)
    return tuple(
        start_sec + duration * ((idx + 0.5) / count)
        for idx in range(count)
    )


def _sample_timestamps_from_ranges(
    ranges: tuple[tuple[float, float], ...],
    count: int,
) -> tuple[float, ...]:
    if count <= 0 or not ranges:
        return ()
    if len(ranges) == 1:
        return _sample_timestamps(ranges[0][0], ranges[0][1], count)
    lengths = [end_sec - start_sec for start_sec, end_sec in ranges]
    total = sum(lengths)
    if total <= 0:
        return ()
    out: list[float] = []
    for idx in range(count):
        pos = total * ((idx + 0.5) / count)
        cursor = 0.0
        for (start_sec, end_sec), length in zip(ranges, lengths):
            if pos <= cursor + length:
                out.append(start_sec + (pos - cursor))
                break
            cursor += length
        else:
            start_sec, end_sec = ranges[-1]
            out.append((start_sec + end_sec) / 2.0)
    return tuple(out)


def _write_png_frame(
    video_path: str,
    *,
    t_sec: float,
    output_path: str,
    ffmpeg_bin: str,
    max_edge_pixels: int,
    subprocess_run=subprocess.run,
) -> None:
    path = Path(video_path)
    if not path.is_file():
        raise FileNotFoundError(f"Video not found: {video_path}")
    e = max(16, int(max_edge_pixels))
    vf = f"scale={e}:{e}:force_original_aspect_ratio=decrease:flags=bicubic"
    proc = subprocess_run(
        [
            ffmpeg_bin,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{max(0.0, t_sec):.6f}",
            "-i",
            str(path),
            "-vf",
            vf,
            "-frames:v",
            "1",
            str(output_path),
        ],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        err = proc.stderr.decode("utf-8", errors="replace") if proc.stderr else ""
        raise RuntimeError(f"ffmpeg failed ({proc.returncode}): {err.strip()}")


def build_frame_pool(
    *,
    video_path: str,
    srt_path: str,
    output_dir: str | None = None,
    settings: object | None = None,
    subprocess_run=subprocess.run,
) -> FramePoolBuildResult:
    cfg = settings if settings is not None else load_settings()
    out_dir = Path(output_dir or (str(Path(video_path).with_suffix("")) + ".frame_pool"))
    out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = out_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    cues = parse_srt_text(Path(srt_path).read_text(encoding="utf-8"))
    shots = detect_shots(
        video_path,
        ffmpeg_bin=str(getattr(cfg, "ffmpeg_path", "ffmpeg")),
        merge_sec=float(getattr(cfg, "pyscenedetect_merge_sec", 0.25)),
    )
    tagged = _tag_dialogue_shots(
        shots,
        cues,
        threshold=float(getattr(cfg, "dialogue_overlap_threshold", 0.05)),
    )

    entries: list[FramePoolEntry] = []
    image_counter = 0
    min_frames = int(getattr(cfg, "pool_frames_per_shot_min", 1))
    max_frames = int(getattr(cfg, "pool_frames_per_shot_max", 3))
    rate = getattr(cfg, "pool_frames_per_shot_rate", None)
    for shot in tagged:
        if not shot.non_dialogue_ranges:
            continue
        available_duration = sum(
            end_sec - start_sec for start_sec, end_sec in shot.non_dialogue_ranges
        )
        count = _sample_count(
            available_duration,
            min_frames=min_frames,
            max_frames=max_frames,
            rate=(float(rate) if rate is not None else None),
        )
        for t_sec in _sample_timestamps_from_ranges(shot.non_dialogue_ranges, count):
            image_counter += 1
            image_ref = f"images/{image_counter:06d}.png"
            output_path = out_dir / image_ref
            _write_png_frame(
                video_path,
                t_sec=t_sec,
                output_path=str(output_path),
                ffmpeg_bin=str(getattr(cfg, "ffmpeg_path", "ffmpeg")),
                max_edge_pixels=int(getattr(cfg, "narration_frame_max_edge", 768)),
                subprocess_run=subprocess_run,
            )
            entries.append(
                FramePoolEntry(
                    shot_id=shot.shot_id,
                    t_sec=t_sec,
                    image_ref=image_ref,
                    embedding_index=None,
                )
            )

    manifest_path = out_dir / "manifest.jsonl"
    shots_path = out_dir / "shots.json"
    write_manifest(manifest_path, tuple(entries))
    write_shots(shots_path, video_path=video_path, shots=tagged)
    build_config = {
        "poolFramesPerShotMin": min_frames,
        "poolFramesPerShotMax": max_frames,
        "poolFramesPerShotRate": (float(rate) if rate is not None else None),
        "dialogueOverlapThreshold": float(getattr(cfg, "dialogue_overlap_threshold", 0.05)),
        "pyscenedetectMergeSec": float(getattr(cfg, "pyscenedetect_merge_sec", 0.25)),
    }
    (out_dir / "build_config.json").write_text(
        json.dumps(build_config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return FramePoolBuildResult(
        output_dir=str(out_dir),
        manifest_path=str(manifest_path),
        shots_path=str(shots_path),
        shot_count=len(tagged),
        non_dialogue_shot_count=sum(1 for shot in tagged if shot.non_dialogue_ranges),
        frame_count=len(entries),
    )
