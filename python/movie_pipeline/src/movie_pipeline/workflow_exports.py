from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from movieteller_logging import classify_error, emit_event
from movieteller_logging import events as log_events
from movie_pipeline.types import ArtifactPaths


def export_workflow_artifacts(
    *,
    payload: dict[str, Any],
    paths: ArtifactPaths,
    output_root: Path,
) -> dict[str, Any]:
    start = time.perf_counter()
    emit_event(log_events.WORKFLOW_EXPORT_START, stage="workflow_export")
    try:
        workflow_artifacts = dict(payload.get("workflowArtifacts") or {})
        workflow_artifacts.update(_export_study_cards(payload, paths=paths, output_root=output_root))
        payload["workflowArtifacts"] = workflow_artifacts
        emit_event(
            log_events.WORKFLOW_EXPORT_DONE,
            stage="workflow_export",
            duration_ms=int((time.perf_counter() - start) * 1000),
            status="ok",
            x_output_root=str(output_root),
        )
        return payload
    except Exception as exc:
        emit_event(
            log_events.WORKFLOW_EXPORT_FAILED,
            level=logging.ERROR,
            stage="workflow_export",
            duration_ms=int((time.perf_counter() - start) * 1000),
            status="error",
            fatal=True,
            **classify_error(exc),
        )
        raise


def _export_study_cards(
    payload: dict[str, Any],
    *,
    paths: ArtifactPaths,
    output_root: Path,
) -> dict[str, str | None]:
    study_html_path = output_root / f"{paths.stem}.study_cards.html"
    try:
        from movie_pipeline.study_cards_export import export_study_cards_artifact

        export_study_cards_artifact(
            payload=payload,
            pool_root=Path(paths.frame_pool_dir),
            output_html=study_html_path,
            page_title=f"{paths.stem} · 图文学习卡",
            embed_images=True,
        )
        return {
            "studyCardsHtmlPath": str(study_html_path.resolve()),
            "studyCardsHtmlError": None,
        }
    except Exception as exc:
        emit_event(
            log_events.STUDY_CARD_EXPORT_FAILED,
            level=logging.WARNING,
            stage="workflow_export",
            status="warning",
            fatal=False,
            **classify_error(exc, default_code="study_card_export_failed"),
        )
        return {
            "studyCardsHtmlPath": None,
            "studyCardsHtmlError": str(exc),
        }
