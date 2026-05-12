from __future__ import annotations

import math
from collections import defaultdict

from pipeline_types import FrameBatch

from video_frame_pool.errors import PoolWindowMiss
from video_frame_pool.storage import (
    load_image_base64,
    load_manifest,
    load_shots,
    sibling_shots_path,
)
from video_frame_pool.types import FramePoolEntry, QueryFramePoolResult, ShotSpan


def _uniform_pick(entries: list[FramePoolEntry], budget: int) -> list[FramePoolEntry]:
    if budget <= 0 or not entries:
        return []
    if budget >= len(entries):
        return list(entries)
    if budget == 1:
        return [entries[len(entries) // 2]]
    picked: list[FramePoolEntry] = []
    for idx in range(budget):
        start = math.floor(idx * len(entries) / budget)
        end = math.floor((idx + 1) * len(entries) / budget)
        pick_idx = min(len(entries) - 1, (start + max(start, end - 1)) // 2)
        picked.append(entries[pick_idx])
    dedup: list[FramePoolEntry] = []
    seen: set[tuple[int, float]] = set()
    for entry in picked:
        key = (entry.shot_id, entry.t_sec)
        if key in seen:
            continue
        seen.add(key)
        dedup.append(entry)
    if len(dedup) < budget:
        for entry in entries:
            key = (entry.shot_id, entry.t_sec)
            if key in seen:
                continue
            dedup.append(entry)
            seen.add(key)
            if len(dedup) >= budget:
                break
    return dedup[:budget]


def _allocate_budgets(
    *,
    groups: dict[int, list[FramePoolEntry]],
    shots_by_id: dict[int, ShotSpan],
    start_sec: float,
    end_sec: float,
    budget: int,
) -> dict[int, int]:
    ordered_ids = sorted(
        groups.keys(),
        key=lambda shot_id: (
            shots_by_id.get(shot_id, ShotSpan(shot_id, start_sec, end_sec)).start_sec,
            shot_id,
        ),
    )
    overlaps: dict[int, float] = {}
    capacities: dict[int, int] = {}
    for shot_id in ordered_ids:
        shot = shots_by_id.get(shot_id)
        if shot is None:
            overlap = max(0.0, end_sec - start_sec)
        else:
            overlap = max(0.0, min(shot.end_sec, end_sec) - max(shot.start_sec, start_sec))
        overlaps[shot_id] = overlap
        capacities[shot_id] = len(groups[shot_id])
    total_overlap = sum(overlaps.values()) or float(len(ordered_ids))
    alloc: dict[int, int] = {}
    remainders: dict[int, float] = {}
    target_budget = min(budget, sum(capacities.values()))
    used = 0
    for shot_id in ordered_ids:
        overlap = overlaps[shot_id]
        raw = float(target_budget) * (overlap / total_overlap) if total_overlap > 0 else 0.0
        base = min(capacities[shot_id], int(math.floor(raw)))
        alloc[shot_id] = base
        remainders[shot_id] = raw - math.floor(raw)
        used += base
    while used < target_budget:
        eligible = [shot_id for shot_id in ordered_ids if alloc[shot_id] < capacities[shot_id]]
        if not eligible:
            break
        eligible.sort(
            key=lambda shot_id: (
                remainders[shot_id],
                overlaps[shot_id],
                -shots_by_id.get(shot_id, ShotSpan(shot_id, start_sec, end_sec)).start_sec,
                -shot_id,
            ),
            reverse=True,
        )
        pick = eligible[0]
        alloc[pick] += 1
        used += 1
    return alloc


def query_frame_pool(
    *,
    manifest_path: str,
    start_sec: float,
    end_sec: float,
    budget: int,
    settings: object | None = None,
) -> QueryFramePoolResult:
    del settings
    entries = load_manifest(manifest_path)
    shots = load_shots(sibling_shots_path(manifest_path))
    shots_by_id = {shot.shot_id: shot for shot in shots}
    filtered = [entry for entry in entries if start_sec <= entry.t_sec <= end_sec]
    if not filtered:
        raise PoolWindowMiss(
            f"Frame-pool window miss for {manifest_path}: [{start_sec:.3f}, {end_sec:.3f}]"
        )
    filtered.sort(key=lambda entry: (entry.t_sec, entry.shot_id, entry.image_ref))
    if budget <= 0 or len(filtered) <= budget:
        selected = filtered
    else:
        groups: dict[int, list[FramePoolEntry]] = defaultdict(list)
        for entry in filtered:
            groups[entry.shot_id].append(entry)
        alloc = _allocate_budgets(
            groups=dict(groups),
            shots_by_id=shots_by_id,
            start_sec=start_sec,
            end_sec=end_sec,
            budget=budget,
        )
        selected = []
        for shot_id, shot_entries in groups.items():
            picked = _uniform_pick(
                sorted(shot_entries, key=lambda entry: entry.t_sec),
                alloc.get(shot_id, 0),
            )
            selected.extend(picked)
        selected.sort(key=lambda entry: (entry.t_sec, entry.shot_id, entry.image_ref))
        if len(selected) > budget:
            selected = selected[:budget]

    frames = tuple(load_image_base64(manifest_path, entry.image_ref) for entry in selected)
    return QueryFramePoolResult(
        source="pool",
        frames_base64_png=frames,
        frame_times_sec=tuple(entry.t_sec for entry in selected),
        shot_ids=tuple(entry.shot_id for entry in selected),
    )


def query_frame_pool_as_frame_batch(
    *,
    manifest_path: str,
    start_sec: float,
    end_sec: float,
    duration_sec: float,
    budget: int,
    settings: object | None = None,
) -> FrameBatch:
    result = query_frame_pool(
        manifest_path=manifest_path,
        start_sec=start_sec,
        end_sec=end_sec,
        budget=budget,
        settings=settings,
    )
    return FrameBatch(
        frames_base64_png=result.frames_base64_png,
        frame_times_sec=result.frame_times_sec,
        duration_sec=float(duration_sec),
        source="frame_pool",
        shot_ids=result.shot_ids,
    )
