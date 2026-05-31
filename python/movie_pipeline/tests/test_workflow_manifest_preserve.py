from __future__ import annotations

import json
from pathlib import Path

import importlib.util

_PERSIST_PATH = (
    Path(__file__).resolve().parents[1] / "src" / "movie_pipeline" / "workflow_persist.py"
)
_spec = importlib.util.spec_from_file_location("workflow_persist", _PERSIST_PATH)
assert _spec and _spec.loader
_persist = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_persist)
merge_preserved_workflow_fields = _persist.merge_preserved_workflow_fields
write_workflow_json_payload = _persist.write_workflow_json_payload


def test_merge_preserved_workflow_fields_keeps_original_source(tmp_path: Path) -> None:
    workflow_path = tmp_path / "workflow.json"
    workflow_path.write_text(
        json.dumps(
            {
                "job_id": "job-1",
                "status": "queued",
                "input_video_path": str(tmp_path / "input" / "source.mp4"),
                "output_root": str(tmp_path),
                "created_at": "2026-01-01T00:00:00Z",
                "original_source": {
                    "type": "local_upload",
                    "source_url": None,
                    "original_filename": "my-lecture.mp4",
                    "uploaded_at": "2026-01-01T00:00:00Z",
                },
                "video_downloaded_at": None,
                "video_purged_at": None,
                "video_state_version": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    pipeline_payload = {
        "job_id": "job-1",
        "status": "succeeded",
        "input_video_path": str(tmp_path / "input" / "source.mp4"),
        "output_root": str(tmp_path),
        "user_id": None,
        "current_stage": None,
        "progress": {},
        "error": None,
        "artifacts": {"outputRoot": str(tmp_path)},
        "created_at": "2026-05-31T00:00:00Z",
        "updated_at": "2026-05-31T00:00:00Z",
    }
    write_workflow_json_payload(
        merge_preserved_workflow_fields(pipeline_payload, workflow_path),
        workflow_path,
    )

    saved = json.loads(workflow_path.read_text(encoding="utf-8"))
    assert saved["status"] == "succeeded"
    assert saved["original_source"]["original_filename"] == "my-lecture.mp4"
    assert saved["created_at"] == "2026-01-01T00:00:00Z"
    assert saved["video_state_version"] == 0
