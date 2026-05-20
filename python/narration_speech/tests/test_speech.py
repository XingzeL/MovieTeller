from pathlib import Path
from types import SimpleNamespace

from movieteller_config.schema import settings_from_dict
from movieteller_config.schema import NarrationSpeechOptions

from narration_speech.speech import _atempo_filter_for_speed, synthesize_narration_text


class FakeSpeechApi:
    def create(self, **kwargs):
        class Response:
            def write_to_file(self, output_path):
                Path(output_path).write_bytes(b"fake-audio")

        return Response()


class FakeTtsClient:
    def __init__(self, *args, **kwargs):
        self.audio = SimpleNamespace(speech=FakeSpeechApi())


def test_atempo_filter_for_speed_chains_large_values():
    assert _atempo_filter_for_speed(3.0).startswith("atempo=2.0,")


def test_synthesize_narration_without_fit(monkeypatch, tmp_path):
    durations = iter([1.1, 1.1])

    def fake_probe(*args, **kwargs):
        return next(durations)

    monkeypatch.setattr("narration_speech.speech._probe_media_duration_sec", fake_probe)
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_keys": {"newapi": "dummy"},
            "api_providers": {"newapi": "https://example.com/v1"},
            "model_defaults": {"tts": "qwen3-tts-flash"},
            "tts_defaults": {"voice": "en-US-EmmaMultilingualNeural"},
        }
    )
    result = synthesize_narration_text(
        "hello world",
        2.0,
        output_path=str(tmp_path / "out.mp3"),
        options=NarrationSpeechOptions(
            voice="en-US-EmmaMultilingualNeural",
            model="qwen3-tts-flash",
            rate="+0%",
            volume="+0%",
            pitch="+0Hz",
            boundary="SentenceBoundary",
            ffmpeg_bin="ffmpeg",
        ),
        settings=settings,
        communicator_factory=lambda *args, **kwargs: FakeTtsClient(),
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
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_keys": {"newapi": "dummy"},
            "api_providers": {"newapi": "https://example.com/v1"},
            "model_defaults": {"tts": "qwen3-tts-flash"},
            "tts_defaults": {"voice": "en-US-EmmaMultilingualNeural"},
        }
    )
    result = synthesize_narration_text(
        "hello world",
        2.0,
        output_path=str(tmp_path / "out.mp3"),
        options=NarrationSpeechOptions(
            voice="en-US-EmmaMultilingualNeural",
            model="qwen3-tts-flash",
            rate="+0%",
            volume="+0%",
            pitch="+0Hz",
            boundary="SentenceBoundary",
            ffmpeg_bin="ffmpeg",
        ),
        settings=settings,
        communicator_factory=lambda *args, **kwargs: FakeTtsClient(),
    )
    assert result.fit_applied is True
    assert result.audio_duration_sec == 1.9
