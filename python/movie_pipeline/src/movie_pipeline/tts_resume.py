from __future__ import annotations

import json
from pathlib import Path


def tts_segment_is_reusable(*, audio_path: Path, metadata_path: Path) -> bool:
    if not audio_path.is_file() or audio_path.stat().st_size <= 0:
        return False
    if not metadata_path.is_file() or metadata_path.stat().st_size <= 0:
        return False
    try:
        lines = [
            line.strip()
            for line in metadata_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if not lines:
            return False
        json.loads(lines[-1])
    except (OSError, json.JSONDecodeError):
        return False
    return True
