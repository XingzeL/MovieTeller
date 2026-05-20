from unittest.mock import MagicMock

from frame_source import FrameSourceOptions
from pipeline_types import FrameBatch, NarrationContext
from movieteller_config.schema import settings_from_dict

from narration.narrate import narrate_from_frames, narrate_segment_with_duration


def make_settings(**overrides):
    base = {
        "gateway": {"default_provider": "newapi"},
        "api_keys": {"newapi": "sk-test"},
        "api_providers": {"newapi": "https://example.test/v1"},
        "model_defaults": {"narration": "gpt-4o-mini"},
        "max_frames_per_segment": 4,
        "ffmpeg_path": "/bin/ffmpeg",
    }
    base.update(overrides)
    return settings_from_dict(base)


def test_narrate_segment_with_duration_end_to_end_mocked(
    tmp_path, fake_concat_png_stdout
):
    settings = make_settings()
    vid = tmp_path / "seg.mp4"
    vid.write_bytes(b"x")

    def fake_run(cmd, capture_output, check):
        m = MagicMock()
        m.returncode = 0
        m.stdout = fake_concat_png_stdout
        m.stderr = b""
        return m

    def fake_client_factory(_k, _b):
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "Unified narration."
        client.chat.completions.create.return_value = resp
        return client

    options = settings.narration_options(prompt_style="documentary")
    frame_source_options = FrameSourceOptions(
        ffmpeg_bin=settings.ffmpeg_path,
        max_frames_per_segment=settings.max_frames_per_segment,
        max_edge_pixels=settings.narration_frame_max_edge,
        pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
    )
    text, dur = narrate_segment_with_duration(
        str(vid),
        0.0,
        1.0,
        options=options,
        frame_source_options=frame_source_options,
        settings=settings,
        subprocess_run=fake_run,
        client_factory=fake_client_factory,
    )
    assert text == "Unified narration."
    assert dur == 1.0


def test_narrate_segment_uses_frame_pool_when_manifest_configured(tmp_path):
    settings = make_settings(frame_pool_manifest=str(tmp_path / "pool" / "manifest.jsonl"))
    pool = tmp_path / "pool"
    images = pool / "images"
    images.mkdir(parents=True)
    (pool / "shots.json").write_text(
        '{"schemaVersion":1,"videoPath":"seg.mp4","shots":[{"shotId":0,"startSec":0.0,"endSec":1.0,"isDialogue":false}]}',
        encoding="utf-8",
    )
    (images / "000001.png").write_bytes(b"\x89PNG\r\n\x1a\npool")
    (pool / "manifest.jsonl").write_text(
        '{"schemaVersion":1,"shotId":0,"tSec":0.5,"imageRef":"images/000001.png","embeddingIndex":null}\n',
        encoding="utf-8",
    )
    vid = tmp_path / "seg.mp4"
    vid.write_bytes(b"x")

    def fake_run(*args, **kwargs):
        raise AssertionError("uniform frame extraction should not run when pool hits")

    def fake_client_factory(_k, _b):
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "From frame pool."
        client.chat.completions.create.return_value = resp
        return client

    options = settings.narration_options()
    frame_source_options = FrameSourceOptions(
        ffmpeg_bin=settings.ffmpeg_path,
        max_frames_per_segment=settings.max_frames_per_segment,
        max_edge_pixels=settings.narration_frame_max_edge,
        pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
    )
    timings = {}
    text, dur = narrate_segment_with_duration(
        str(vid),
        0.0,
        1.0,
        options=options,
        frame_source_options=frame_source_options,
        settings=settings,
        subprocess_run=fake_run,
        client_factory=fake_client_factory,
        timings_out=timings,
    )
    assert text == "From frame pool."
    assert dur == 1.0
    assert timings["frame_source"] == "frame_pool"
    assert timings["frame_count"] == 1


def test_narrate_segment_falls_back_to_uniform_on_pool_window_miss(
    tmp_path, fake_concat_png_stdout
):
    settings = make_settings(
        pool_miss_uniform_max_frames=2,
        frame_pool_manifest=str(tmp_path / "pool" / "manifest.jsonl"),
    )
    pool = tmp_path / "pool"
    images = pool / "images"
    images.mkdir(parents=True)
    (pool / "shots.json").write_text(
        '{"schemaVersion":1,"videoPath":"seg.mp4","shots":[{"shotId":0,"startSec":0.0,"endSec":1.0,"isDialogue":false}]}',
        encoding="utf-8",
    )
    (images / "000001.png").write_bytes(b"\x89PNG\r\n\x1a\npool")
    (pool / "manifest.jsonl").write_text(
        '{"schemaVersion":1,"shotId":0,"tSec":0.1,"imageRef":"images/000001.png","embeddingIndex":null}\n',
        encoding="utf-8",
    )
    vid = tmp_path / "seg.mp4"
    vid.write_bytes(b"x")
    calls = []

    def fake_run(cmd, capture_output, check):
        calls.append(list(cmd))
        m = MagicMock()
        m.returncode = 0
        m.stdout = fake_concat_png_stdout
        m.stderr = b""
        return m

    def fake_client_factory(_k, _b):
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "Fallback narration."
        client.chat.completions.create.return_value = resp
        return client

    options = settings.narration_options()
    frame_source_options = FrameSourceOptions(
        ffmpeg_bin=settings.ffmpeg_path,
        max_frames_per_segment=settings.max_frames_per_segment,
        max_edge_pixels=settings.narration_frame_max_edge,
        pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
    )
    timings = {}
    text, _dur = narrate_segment_with_duration(
        str(vid),
        2.0,
        3.0,
        options=options,
        frame_source_options=frame_source_options,
        settings=settings,
        subprocess_run=fake_run,
        client_factory=fake_client_factory,
        timings_out=timings,
    )
    assert text == "Fallback narration."
    assert timings["frame_source"] == "uniform_fallback"
    assert "-frames:v" in calls[0]


def test_narrate_segment_includes_subtitle_context_in_prompt(
    tmp_path, fake_concat_png_stdout
):
    settings = make_settings()
    vid = tmp_path / "seg.mp4"
    vid.write_bytes(b"x")
    captured: dict[str, object] = {}

    def fake_run(cmd, capture_output, check):
        m = MagicMock()
        m.returncode = 0
        m.stdout = fake_concat_png_stdout
        m.stderr = b""
        return m

    def fake_client_factory(_k, _b):
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "Narration with context."
        def _create(**kwargs):
            captured["chat_kwargs"] = kwargs
            return resp

        client.chat.completions.create.side_effect = _create
        return client

    options = settings.narration_options(prompt_style="movie_commentary")
    frame_source_options = FrameSourceOptions(
        ffmpeg_bin=settings.ffmpeg_path,
        max_frames_per_segment=settings.max_frames_per_segment,
        max_edge_pixels=settings.narration_frame_max_edge,
        pool_miss_uniform_max_frames=settings.pool_miss_uniform_max_frames,
    )
    text, dur = narrate_segment_with_duration(
        str(vid),
        5.0,
        8.0,
        options=options,
        frame_source_options=frame_source_options,
        settings=settings,
        subprocess_run=fake_run,
        client_factory=fake_client_factory,
        narration_context=NarrationContext(
            segment_start_sec=5.0,
            segment_end_sec=8.0,
            prev_subtitle_text="你为什么不给我送信了",
            next_subtitle_text="这是给你的，快收下",
            retrieved_context_texts=(
                "他们之前因为信件起了争执",
                "后来她一直保留着那些信",
            ),
        ),
    )
    assert text == "Narration with context."
    assert dur == 3.0
    user_text = captured["chat_kwargs"]["messages"][1]["content"][0]["text"]
    assert "Previous subtitle: 你为什么不给我送信了" in user_text
    assert "Next subtitle: 这是给你的，快收下" in user_text
    assert "他们之前因为信件起了争执" in user_text


def test_narrate_from_frames_is_pure_generation_interface():
    settings = make_settings()
    captured: dict[str, object] = {}

    def fake_client_factory(_k, _b):
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "Pure frame narration."

        def _create(**kwargs):
            captured["chat_kwargs"] = kwargs
            return resp

        client.chat.completions.create.side_effect = _create
        return client

    result = narrate_from_frames(
        frames=FrameBatch(
            frames_base64_png=("abc", "def"),
            frame_times_sec=(1.0, 2.0),
            duration_sec=3.0,
            source="uniform",
            shot_ids=None,
        ),
        context=NarrationContext(
            segment_start_sec=0.0,
            segment_end_sec=3.0,
            prev_subtitle_text="prev",
            next_subtitle_text="next",
            retrieved_context_texts=("ctx1",),
        ),
        options=settings.narration_options(),
        settings=settings,
        client_factory=fake_client_factory,
    )
    assert result.text == "Pure frame narration."
    assert result.frame_source == "uniform"
    assert result.frame_count == 2
    user_text = captured["chat_kwargs"]["messages"][1]["content"][0]["text"]
    assert "Previous subtitle: prev" in user_text
    assert "ctx1" in user_text
