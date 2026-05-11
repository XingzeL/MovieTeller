from __future__ import annotations

import base64
import json
from pathlib import Path

from video_frame_pool.errors import PoolManifestError
from video_frame_pool.types import FramePoolEntry, ShotSpan

SCHEMA_VERSION = 1


def write_manifest(path: Path, entries: tuple[FramePoolEntry, ...]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for entry in entries:
            row = {
                "schemaVersion": SCHEMA_VERSION,
                "shotId": entry.shot_id,
                "tSec": entry.t_sec,
                "imageRef": entry.image_ref,
                "embeddingIndex": entry.embedding_index,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_manifest(path: str | Path) -> tuple[FramePoolEntry, ...]:
    p = Path(path)
    if not p.is_file():
        raise PoolManifestError(f"Frame-pool manifest not found: {p}")
    entries: list[FramePoolEntry] = []
    with p.open("r", encoding="utf-8") as f:
        for line_no, raw in enumerate(f, start=1):
            line = raw.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise PoolManifestError(
                    f"Invalid JSON in manifest {p}:{line_no}"
                ) from exc
            if int(row.get("schemaVersion", 0)) != SCHEMA_VERSION:
                raise PoolManifestError(
                    f"Unsupported manifest schemaVersion in {p}:{line_no}"
                )
            image_ref = str(row.get("imageRef") or "").strip()
            if not image_ref:
                raise PoolManifestError(f"Missing imageRef in {p}:{line_no}")
            entries.append(
                FramePoolEntry(
                    shot_id=int(row["shotId"]),
                    t_sec=float(row["tSec"]),
                    image_ref=image_ref,
                    embedding_index=(
                        int(row["embeddingIndex"])
                        if row.get("embeddingIndex") is not None
                        else None
                    ),
                )
            )
    return tuple(entries)


def write_shots(path: Path, *, video_path: str, shots: tuple[ShotSpan, ...]) -> None:
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "videoPath": video_path,
        "shots": [
            {
                "shotId": shot.shot_id,
                "startSec": shot.start_sec,
                "endSec": shot.end_sec,
                "isDialogue": shot.is_dialogue,
                "dialogueOverlapRatio": shot.dialogue_overlap_ratio,
                "nonDialogueRanges": [
                    {"startSec": start_sec, "endSec": end_sec}
                    for start_sec, end_sec in shot.non_dialogue_ranges
                ],
            }
            for shot in shots
        ],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def load_shots(path: str | Path) -> tuple[ShotSpan, ...]:
    p = Path(path)
    if not p.is_file():
        raise PoolManifestError(f"Frame-pool shots file not found: {p}")
    try:
        payload = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PoolManifestError(f"Invalid JSON in shots file: {p}") from exc
    if int(payload.get("schemaVersion", 0)) != SCHEMA_VERSION:
        raise PoolManifestError(f"Unsupported shots schemaVersion in {p}")
    rows = payload.get("shots")
    if not isinstance(rows, list):
        raise PoolManifestError(f"Invalid shots array in {p}")
    shots: list[ShotSpan] = []
    for row in rows:
        shots.append(
            ShotSpan(
                shot_id=int(row["shotId"]),
                start_sec=float(row["startSec"]),
                end_sec=float(row["endSec"]),
                is_dialogue=bool(row.get("isDialogue", False)),
                dialogue_overlap_ratio=float(row.get("dialogueOverlapRatio", 0.0) or 0.0),
                non_dialogue_ranges=tuple(
                    (
                        float(item["startSec"]),
                        float(item["endSec"]),
                    )
                    for item in (row.get("nonDialogueRanges") or [])
                    if isinstance(item, dict)
                ),
            )
        )
    return tuple(shots)


def sibling_shots_path(manifest_path: str | Path) -> Path:
    return Path(manifest_path).with_name("shots.json")


def load_image_base64(manifest_path: str | Path, image_ref: str) -> str:
    p = Path(manifest_path).resolve().parent / image_ref
    if not p.is_file():
        raise PoolManifestError(f"Frame-pool image not found: {p}")
    return base64.standard_b64encode(p.read_bytes()).decode("ascii")
