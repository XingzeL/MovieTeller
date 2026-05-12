from pathlib import Path

import numpy as np
import pytest

from movieteller_config.schema import settings_from_dict
from subtitle_context.storage import write_chunks, write_embeddings

from subtitle_context.index import (
    build_subtitle_context_index,
    retrieve_past_subtitle_context,
    subtitle_context_index_is_complete,
)
from subtitle_context.types import SubtitleContextChunk


def test_build_subtitle_context_index_writes_local_files(tmp_path):
    srt = tmp_path / "demo.srt"
    srt.write_text(
        """1
00:00:00,000 --> 00:00:01,000
hello

2
00:00:02,000 --> 00:00:03,000
world
""",
        encoding="utf-8",
    )

    def fake_embedder(texts):
        assert texts == ["hello world"]
        return np.asarray([[1.0, 0.0]], dtype=np.float32)

    settings = settings_from_dict({"narration_image_model": "x"})
    result = build_subtitle_context_index(
        srt_path=str(srt),
        output_dir=str(tmp_path / "index"),
        settings=settings,
        embedder=fake_embedder,
    )
    assert result.chunk_count == 1
    assert result.embedding_dim == 2
    assert Path(result.chunks_path).is_file()
    assert Path(result.embeddings_path).is_file()
    assert subtitle_context_index_is_complete(tmp_path / "index")


def test_build_subtitle_context_index_does_not_leave_partial_dir_on_failure(tmp_path):
    srt = tmp_path / "demo.srt"
    srt.write_text(
        """1
00:00:00,000 --> 00:00:01,000
hello
""",
        encoding="utf-8",
    )
    output_dir = tmp_path / "index"

    def failing_embedder(_texts):
        raise RuntimeError("embedding failed")

    settings = settings_from_dict({"narration_image_model": "x"})
    with pytest.raises(RuntimeError, match="embedding failed"):
        build_subtitle_context_index(
            srt_path=str(srt),
            output_dir=str(output_dir),
            settings=settings,
            embedder=failing_embedder,
        )
    assert not output_dir.exists()


def test_retrieve_past_subtitle_context_filters_future_chunks(tmp_path):
    srt = tmp_path / "demo.srt"
    srt.write_text(
        """1
00:00:00,000 --> 00:00:01,000
harry under stairs

2
00:00:03,000 --> 00:00:04,000
letter arrives

3
00:00:08,000 --> 00:00:09,000
hagrid appears
""",
        encoding="utf-8",
    )

    mapping = {
        "harry under stairs letter arrives": [1.0, 0.0],
        "hagrid appears": [0.0, 1.0],
        "letter arrives": [1.0, 0.0],
    }

    def fake_embedder(texts):
        return np.asarray([mapping[text] for text in texts], dtype=np.float32)

    settings = settings_from_dict(
        {
            "narration_image_model": "x",
            "subtitle_context_chunk_cue_count": 2,
            "subtitle_context_chunk_stride": 2,
            "subtitle_context_history_window_sec": 10,
            "subtitle_context_top_k": 4,
        }
    )
    index_dir = tmp_path / "index"
    build_subtitle_context_index(
        srt_path=str(srt),
        output_dir=str(index_dir),
        settings=settings,
        embedder=fake_embedder,
    )
    result = retrieve_past_subtitle_context(
        index_dir=str(index_dir),
        query_text="letter arrives",
        segment_start_sec=5.0,
        settings=settings,
        embedder=fake_embedder,
    )
    assert len(result.retrieved_chunks) == 1
    assert result.retrieved_chunks[0].text == "harry under stairs letter arrives"
    assert result.retrieved_chunks[0].end_sec <= 5.0


def test_retrieve_past_subtitle_context_uses_mmr_to_reduce_duplicates(tmp_path):
    index_dir = tmp_path / "index"
    index_dir.mkdir()
    write_chunks(
        index_dir / "chunks.jsonl",
        (
            SubtitleContextChunk(
                chunk_id="000001",
                start_sec=0.0,
                end_sec=2.0,
                text="first letter conflict",
                cue_count=2,
            ),
            SubtitleContextChunk(
                chunk_id="000002",
                start_sec=3.0,
                end_sec=5.0,
                text="same letter conflict repeated",
                cue_count=2,
            ),
            SubtitleContextChunk(
                chunk_id="000003",
                start_sec=6.0,
                end_sec=8.0,
                text="different emotional beat",
                cue_count=2,
            ),
        ),
    )
    write_embeddings(
        index_dir / "embeddings.npy",
        np.asarray(
            [
                [0.95, 0.31],
                [0.94, 0.34],
                [0.80, -0.60],
            ],
            dtype=np.float32,
        ),
    )

    def fake_embedder(texts):
        assert texts == ["letter fight"]
        return np.asarray([[1.0, 0.0]], dtype=np.float32)

    settings = settings_from_dict(
        {
            "narration_image_model": "x",
            "subtitle_context_history_window_sec": 20,
            "subtitle_context_top_k": 2,
        }
    )
    result = retrieve_past_subtitle_context(
        index_dir=str(index_dir),
        query_text="letter fight",
        segment_start_sec=10.0,
        settings=settings,
        embedder=fake_embedder,
    )
    assert [row.chunk_id for row in result.retrieved_chunks] == ["000001", "000003"]
