from pathlib import Path

from movieteller_config.schema import NarrationSpeechOptions

from narration_speech.speech import _atempo_filter_for_speed, synthesize_narration_text


class FakeCommunicate:
    def __init__(self, *args, **kwargs):
        pass

    async def save(self, audio_path, metadata_path):
        Path(audio_path).write_bytes(b"fake-audio")
        Path(metadata_path).write_text("{}", encoding="utf-8")


def test_atempo_filter_for_speed_chains_large_values():
    assert _atempo_filter_for_speed(3.0).startswith("atempo=2.0,")


def test_synthesize_narration_without_fit(monkeypatch, tmp_path):
    durations = iter([1.1, 1.1])

    def fake_probe(*args, **kwargs):
        return next(durations)

    monkeypatch.setattr("narration_speech.speech._probe_media_duration_sec", fake_probe)
    result = synthesize_narration_text(
        "hello world",
        2.0,
        output_path=str(tmp_path / "out.mp3"),
        options=NarrationSpeechOptions(
            provider_slug="edge_tts",
            voice="en-US-EmmaMultilingualNeural",
            rate="+0%",
            volume="+0%",
            pitch="+0Hz",
            boundary="SentenceBoundary",
            ffmpeg_bin="ffmpeg",
        ),
        communicator_factory=lambda *args, **kwargs: FakeCommunicate(),
    )
    assert Path(result.audio_path).is_file()
    assert result.fit_applied is False
    assert result.fits_duration is True


def test_synthesize_narration_with_fit(monkeypatch, tmp_path):
    durations = iter([2.4, 1.9])

    def fake_probe(*args, **kwargs):
        return next(durations)

    def fake_fit(input_path, output_path, **kwargs):
        Path(output_path).write_bytes(Path(input_path).read_bytes())

    monkeypatch.setattr("narration_speech.speech._probe_media_duration_sec", fake_probe)
    monkeypatch.setattr("narration_speech.speech._fit_audio_speedup", fake_fit)
    result = synthesize_narration_text(
        "hello world",
        2.0,
        output_path=str(tmp_path / "out.mp3"),
        options=NarrationSpeechOptions(
            provider_slug="edge_tts",
            voice="en-US-EmmaMultilingualNeural",
            rate="+0%",
            volume="+0%",
            pitch="+0Hz",
            boundary="SentenceBoundary",
            ffmpeg_bin="ffmpeg",
        ),
        communicator_factory=lambda *args, **kwargs: FakeCommunicate(),
    )
    assert result.fit_applied is True
    assert result.audio_duration_sec == 1.9
