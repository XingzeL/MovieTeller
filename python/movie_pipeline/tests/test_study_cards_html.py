from __future__ import annotations

from pathlib import Path

from movie_pipeline.study_cards_frames import (
    data_urls_for_selected,
    select_frames_for_segment,
)
from movie_pipeline.study_cards_export import build_study_cards_document
from movie_pipeline.study_cards_html import (
    _annotate_narration_html,
    export_study_cards_html,
    format_media_timestamp,
)
from movie_pipeline.types import StudyCardsDocument, StudyCardSegment
from video_frame_pool.types import FramePoolEntry


def test_format_media_timestamp():
    assert format_media_timestamp(0) == "0:00.000"
    assert format_media_timestamp(29.48) == "0:29.480"


def test_select_frames_one_per_shot_closest_to_midpoint():
    entries = (
        FramePoolEntry(1, 1.0, "images/a.png"),
        FramePoolEntry(1, 1.5, "images/b.png"),
        FramePoolEntry(2, 2.0, "images/c.png"),
    )
    out = select_frames_for_segment(entries, 0.8, 2.2)
    assert [e.t_sec for e in out] == [1.5, 2.0]
    assert [e.image_ref for e in out] == ["images/b.png", "images/c.png"]


def test_data_urls_for_selected(tmp_path: Path) -> None:
    pool = tmp_path / "pool"
    (pool / "images").mkdir(parents=True)
    (pool / "images" / "x.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
    picked = (FramePoolEntry(3, 1.0, "images/x.png"),)
    urls = data_urls_for_selected(pool, picked)
    assert len(urls) == 1
    assert urls[0] is not None
    assert urls[0].startswith("data:image/png;base64,")


def test_export_study_cards_html_embeds_base64_by_default(tmp_path: Path) -> None:
    pool = tmp_path / "pool"
    img_dir = pool / "images"
    img_dir.mkdir(parents=True)
    (img_dir / "a.png").write_bytes(b"x")
    (img_dir / "b.png").write_bytes(b"y")

    manifest = pool / "manifest.jsonl"
    manifest.write_text(
        '{"schemaVersion":1,"shotId":1,"tSec":1.0,"imageRef":"images/a.png"}\n'
        '{"schemaVersion":1,"shotId":2,"tSec":2.0,"imageRef":"images/b.png"}\n',
        encoding="utf-8",
    )

    pipeline = {
        "narratedSegments": [
            {
                "startSec": 0.5,
                "endSec": 2.5,
                "text": "Line one.",
                "speechText": "Line one polished.",
                "prevSubtitleText": None,
                "nextSubtitleText": "Next cue",
                "polish": {"sceneTitleZh": "双镜同框"},
            }
        ]
    }

    out_html = tmp_path / "out" / "study.html"
    document = build_study_cards_document(
        payload=pipeline,
        page_title="Test deck",
    )
    export_study_cards_html(
        document=document,
        pool_root=pool,
        output_html=out_html,
        embed_images=True,
    )

    html_text = out_html.read_text(encoding="utf-8")
    assert "双镜同框" in html_text
    assert "Line one." in html_text
    assert "Line one polished." not in html_text
    assert 'data-frame-carousel' in html_text
    assert "frame-nav-prev" in html_text
    assert html_text.count('src="data:image/png;base64,') == 2
    assert html_text.count('src="data:image/png;base64,') == 2
    assert "Base64" in html_text
    assert not (out_html.parent / "assets").exists()


def test_build_study_cards_document_passes_vocab_study_card():
    pipeline = {
        "narratedSegments": [
            {
                "startSec": 0.0,
                "endSec": 1.0,
                "text": "Hello world",
                "speechText": "Hi world",
                "prevSubtitleText": None,
                "nextSubtitleText": None,
                "studyCard": {
                    "vocab": {
                        "passage_id": "seg",
                        "highlights_count": 1,
                        "data": [{"match_text": "world", "definition": "世界"}],
                        "full_translation": "你好世界。",
                    },
                },
                "polish": {
                    "sceneTitleZh": "问候",
                },
            }
        ]
    }
    doc = build_study_cards_document(payload=pipeline, page_title="Deck")
    assert len(doc.segments) == 1
    assert doc.segments[0].vocab_study_card is not None
    assert doc.segments[0].vocab_study_card["data"][0]["match_text"] == "world"


def test_annotate_narration_html_wraps_matches_and_escapes_attributes():
    vocab = {
        "data": [
            {
                "match_text": "world",
                "word_root": "world",
                "pos": "n.",
                "definition": '"><img src=x>',
                "note": "a < b",
            }
        ]
    }
    out = _annotate_narration_html("Hello world today", vocab)
    assert "vocab-hl" in out
    assert "vocab-tooltip" in out
    assert "<strong>world</strong>" in out
    assert "vocab-tip-def" in out
    assert '<img src=x>' not in out
    assert "&lt;" in out


def test_export_study_cards_html_vocab_modal_and_translation(tmp_path: Path) -> None:
    pool = tmp_path / "poolv"
    img_dir = pool / "images"
    img_dir.mkdir(parents=True)
    (img_dir / "a.png").write_bytes(b"x")

    (pool / "manifest.jsonl").write_text(
        '{"schemaVersion":1,"shotId":1,"tSec":1.0,"imageRef":"images/a.png"}\n',
        encoding="utf-8",
    )

    pipeline = {
        "narratedSegments": [
            {
                "startSec": 0.5,
                "endSec": 2.5,
                "text": "The cat sits on the mat.",
                "speechText": "Cat on mat.",
                "prevSubtitleText": None,
                "nextSubtitleText": None,
                "studyCard": {
                    "vocab": {
                        "passage_id": "1",
                        "highlights_count": 2,
                        "data": [
                            {
                                "match_text": "The cat",
                                "word_root": "cat",
                                "pos": "n.",
                                "definition": "那只猫",
                                "note": "",
                            },
                            {
                                "match_text": "mat",
                                "word_root": "mat",
                                "pos": "n.",
                                "definition": "垫子",
                                "note": "",
                            },
                        ],
                        "full_translation": "猫坐在垫子上。",
                    },
                },
                "polish": {
                    "sceneTitleZh": "动物",
                },
            }
        ]
    }

    out_html = tmp_path / "outv" / "study.html"
    document = build_study_cards_document(
        payload=pipeline,
        page_title="Vocab deck",
    )
    export_study_cards_html(
        document=document,
        pool_root=pool,
        output_html=out_html,
        embed_images=True,
    )

    html_text = out_html.read_text(encoding="utf-8")
    assert "vocab-hl" in html_text
    assert "vocab-tooltip" in html_text
    assert "<strong>The cat</strong>" in html_text
    assert "initVocabTooltips" in html_text
    assert "vocab-modal" not in html_text
    assert "参考译文" in html_text
    assert "猫坐在垫子上" in html_text
    pool = tmp_path / "pool2"
    img_dir = pool / "images"
    img_dir.mkdir(parents=True)
    (img_dir / "a.png").write_bytes(b"z")

    (pool / "manifest.jsonl").write_text(
        '{"schemaVersion":1,"shotId":1,"tSec":1.0,"imageRef":"images/a.png"}\n',
        encoding="utf-8",
    )
    pipeline = {
        "narratedSegments": [
            {
                "startSec": 0.0,
                "endSec": 2.0,
                "text": "Hi",
                "speechText": "Hi",
                "prevSubtitleText": None,
                "nextSubtitleText": None,
                "polish": None,
            }
        ]
    }
    out_html = tmp_path / "out2" / "study.html"
    document = StudyCardsDocument(
        title="影视英语·图文学习卡",
        segments=(
            StudyCardSegment(
                start_sec=0.0,
                end_sec=2.0,
                narration_text="Hi",
                prev_subtitle_text=None,
                next_subtitle_text=None,
            ),
        ),
    )
    export_study_cards_html(
        document=document,
        pool_root=pool,
        output_html=out_html,
        embed_images=False,
    )
    html_text = out_html.read_text(encoding="utf-8")
    assert "./study_cards_assets/frames/" in html_text
    assert 'data-frame-carousel' in html_text
    assert (out_html.parent / "study_cards_assets" / "frames").is_dir()
