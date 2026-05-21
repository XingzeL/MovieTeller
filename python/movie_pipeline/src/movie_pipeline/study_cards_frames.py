from __future__ import annotations

import base64
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from video_frame_pool.storage import load_manifest
from video_frame_pool.types import FramePoolEntry


def select_frames_for_segment(
    entries: Sequence[FramePoolEntry],
    start_sec: float,
    end_sec: float,
) -> tuple[FramePoolEntry, ...]:
    """Pick at most one manifest row per shot inside ``[start_sec, end_sec]``.

    For each shot, keep the frame whose ``t_sec`` is closest to the segment midpoint.
    Results are ordered by ``t_sec``.
    """
    lo = float(start_sec)
    hi = float(end_sec)
    if hi < lo:
        lo, hi = hi, lo
    mid = (lo + hi) / 2.0
    in_window = [e for e in entries if lo <= e.t_sec <= hi]
    by_shot: dict[int, list[FramePoolEntry]] = defaultdict(list)
    for ent in in_window:
        by_shot[ent.shot_id].append(ent)
    chosen: list[FramePoolEntry] = []
    for shot_id in sorted(by_shot):
        group = by_shot[shot_id]
        best = min(group, key=lambda e: abs(e.t_sec - mid))
        chosen.append(best)
    chosen.sort(key=lambda e: e.t_sec)
    return tuple(chosen)


def load_manifest_from_pool_dir(pool_root: str | Path) -> tuple[FramePoolEntry, ...]:
    root = Path(pool_root)
    return load_manifest(root / "manifest.jsonl")


def _guess_image_mime(image_ref: str) -> str:
    suf = Path(image_ref).suffix.lower()
    if suf in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suf == ".webp":
        return "image/webp"
    if suf == ".gif":
        return "image/gif"
    return "image/png"


def data_urls_for_selected(
    pool_root: Path,
    selected: Sequence[FramePoolEntry],
) -> tuple[str | None, ...]:
    """Return one ``data:image/...;base64,...`` URL per selected entry, or ``None`` if file missing."""
    root = pool_root.resolve()
    out: list[str | None] = []
    for ent in selected:
        src = root / ent.image_ref
        if not src.is_file():
            out.append(None)
            continue
        raw = src.read_bytes()
        mime = _guess_image_mime(str(ent.image_ref))
        b64 = base64.standard_b64encode(raw).decode("ascii")
        out.append(f"data:{mime};base64,{b64}")
    return tuple(out)


def copy_selected_frames(
    *,
    pool_root: Path,
    selected: Sequence[FramePoolEntry],
    frames_dest_dir: Path,
) -> tuple[str | None, ...]:
    """Copy images into *frames_dest_dir*.

    Returns one entry per *selected* row: a browser href such as
    ``./study_cards_assets/frames/00001_foo.png``, or ``None`` if the source file is missing.
    """
    frames_dest_dir.mkdir(parents=True, exist_ok=True)
    hrefs: list[str | None] = []
    used_names: set[str] = set()
    for ent in selected:
        src = pool_root / ent.image_ref
        base = Path(ent.image_ref).name
        dest_name = f"{ent.shot_id:05d}_{base}"
        while dest_name in used_names:
            dest_name = f"dup_{dest_name}"
        used_names.add(dest_name)
        dest_path = frames_dest_dir / dest_name
        if src.is_file():
            shutil.copy2(src, dest_path)
            hrefs.append(f"./study_cards_assets/frames/{dest_name}")
        else:
            hrefs.append(None)
    return tuple(hrefs)
