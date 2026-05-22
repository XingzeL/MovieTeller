from __future__ import annotations

from pathlib import Path
from typing import Any

from movie_pipeline.study_cards_html import export_study_cards_html
from movie_pipeline.types import StudyCardSegment, StudyCardsDocument


def build_study_cards_document(
    *,
    payload: dict[str, Any],
    page_title: str,
) -> StudyCardsDocument:
    raw_segments = payload.get("narratedSegments")
    segments: list[StudyCardSegment] = []
    if isinstance(raw_segments, list):
        for raw in raw_segments:
            if not isinstance(raw, dict):
                continue
            polish = raw.get("polish")
            scene_title_zh: str | None = None
            vocab_study_card: dict[str, Any] | None = None
            if isinstance(polish, dict):
                candidate = polish.get("sceneTitleZh")
                if isinstance(candidate, str):
                    candidate = candidate.strip()
                    scene_title_zh = candidate or None
            study_card = raw.get("studyCard")
            if isinstance(study_card, dict):
                vc = study_card.get("vocab")
                if isinstance(vc, dict):
                    vocab_study_card = vc
            segments.append(
                StudyCardSegment(
                    start_sec=float(raw["startSec"]),
                    end_sec=float(raw["endSec"]),
                    narration_text=str(raw.get("text") or "").strip(),
                    prev_subtitle_text=_optional_str(raw.get("prevSubtitleText")),
                    next_subtitle_text=_optional_str(raw.get("nextSubtitleText")),
                    scene_title_zh=scene_title_zh,
                    vocab_study_card=vocab_study_card,
                )
            )
    return StudyCardsDocument(
        title=page_title,
        segments=tuple(segments),
    )


def export_study_cards_artifact(
    *,
    payload: dict[str, Any],
    pool_root: Path,
    output_html: Path,
    page_title: str,
    embed_images: bool = True,
) -> None:
    document = build_study_cards_document(
        payload=payload,
        page_title=page_title,
    )
    export_study_cards_html(
        document=document,
        pool_root=pool_root,
        output_html=output_html,
        embed_images=embed_images,
    )


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
