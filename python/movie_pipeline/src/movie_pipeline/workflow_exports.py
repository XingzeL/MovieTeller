from __future__ import annotations

from pathlib import Path
from typing import Any

from movie_pipeline.types import ArtifactPaths


def export_workflow_artifacts(
    *,
    payload: dict[str, Any],
    paths: ArtifactPaths,
    output_root: Path,
) -> dict[str, Any]:
    workflow_artifacts = dict(payload.get("workflowArtifacts") or {})
    workflow_artifacts.update(_export_study_cards(payload, paths=paths, output_root=output_root))
    payload["workflowArtifacts"] = workflow_artifacts
    return payload


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
        return {
            "studyCardsHtmlPath": None,
            "studyCardsHtmlError": str(exc),
        }
