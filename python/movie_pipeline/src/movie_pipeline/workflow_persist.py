"""Merge Node-owned keys when rewriting ``workflow.json`` (stdlib only, easy to test)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_NODE_PRESERVED_WORKFLOW_KEYS = (
    "original_source",
    "video_downloaded_at",
    "video_purged_at",
    "video_state_version",
    "cancel_requested_at",
    "created_at",
)


def merge_preserved_workflow_fields(
    payload: dict[str, Any],
    path: str | Path,
) -> dict[str, Any]:
    """Keep Node-owned workflow.json keys when the pipeline rewrites the manifest."""
    manifest_path = Path(path)
    if not manifest_path.is_file():
        return payload
    try:
        existing = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return payload
    if not isinstance(existing, dict):
        return payload
    merged = dict(payload)
    for key in _NODE_PRESERVED_WORKFLOW_KEYS:
        if key in existing:
            merged[key] = existing[key]
    return merged


def write_workflow_json_payload(payload: dict[str, Any], path: str | Path) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(out)
