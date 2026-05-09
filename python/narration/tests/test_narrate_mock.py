from unittest.mock import MagicMock

from movieteller_config.schema import settings_from_dict

from narration.narrate import narrate_segment_with_duration


def test_narrate_segment_with_duration_end_to_end_mocked(
    tmp_path, fake_concat_png_stdout
):
    settings = settings_from_dict(
        {
            "openai_api_key": "sk-test",
            "narration_image_model": "gpt-4o-mini",
            "max_frames_per_segment": 4,
            "ffmpeg_path": "/bin/ffmpeg",
        }
    )
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

    text, dur = narrate_segment_with_duration(
        str(vid),
        0.0,
        1.0,
        prompt_style="documentary",
        settings=settings,
        subprocess_run=fake_run,
        client_factory=fake_client_factory,
    )
    assert text == "Unified narration."
    assert dur == 1.0
