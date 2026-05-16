import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from movieteller_config.loader import load_flat_dict, load_settings
from movieteller_config.schema import settings_from_dict


class TestLoader(unittest.TestCase):
    def test_env_overrides_defaults(self):
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-test",
                "MAX_FRAMES_PER_SEGMENT": "8",
                "NARRATION_FRAME_MAX_EDGE": "512",
                "FRAME_POOL_MANIFEST": "/tmp/example.frame_pool/manifest.jsonl",
                "POOL_FRAMES_PER_SHOT_MAX": "5",
                "POOL_MISS_UNIFORM_MAX_FRAMES": "9",
                "SUBTITLE_CONTEXT_TOP_K": "9",
                "GATEWAY_DEFAULT_PROVIDER": "NEWAPI",
                "API_PROVIDERS_JSON": '{"newapi":"http://127.0.0.1:3000/v1"}',
                "MODEL_DEFAULTS_JSON": '{"narration":"vision-x","polish":"text-y","tts":"tts-z","embedding":"embed-w"}',
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.openai_api_key, "sk-test")
            self.assertEqual(s.get_api_key("openai"), "sk-test")
            self.assertEqual(s.max_frames_per_segment, 8)
            self.assertEqual(s.narration_frame_max_edge, 512)
            self.assertEqual(
                s.frame_pool_manifest, "/tmp/example.frame_pool/manifest.jsonl"
            )
            self.assertEqual(s.pool_frames_per_shot_max, 5)
            self.assertEqual(s.pool_miss_uniform_max_frames, 9)
            self.assertEqual(s.subtitle_context_top_k, 9)
            self.assertEqual(s.default_provider(), "newapi")
            self.assertEqual(s.default_model_for_capability("narration"), "vision-x")
            self.assertEqual(s.default_model_for_capability("embedding"), "embed-w")

    def test_api_keys_json_and_anthropic_env(self):
        with mock.patch.dict(
            os.environ,
            {
                "API_KEYS_JSON": '{"openai":"sk-json","custom_vendor":"abc"}',
                "ANTHROPIC_API_KEY": "sk-ant",
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.get_api_key("openai"), "sk-json")
            self.assertEqual(s.get_api_key("anthropic"), "sk-ant")
            self.assertEqual(s.get_api_key("custom_vendor"), "abc")

    def test_movieteller_config_file_overrides_package_default(self):
        content = """
max_frames_per_segment: 3
ffmpeg_path: /usr/bin/ffmpeg
"""
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        saved_mf = os.environ.get("MAX_FRAMES_PER_SEGMENT")
        try:
            with mock.patch("movieteller_config.loader._load_repo_dotenv", lambda: None):
                with mock.patch(
                    "movieteller_config.loader._repo_root_config_paths",
                    return_value=[],
                ):
                    with mock.patch.dict(
                        os.environ, {"MOVIE_TELLER_CONFIG": path}, clear=False
                    ):
                        os.environ.pop("MAX_FRAMES_PER_SEGMENT", None)
                        d = load_flat_dict()
                        self.assertEqual(d.get("max_frames_per_segment"), 3)
                        self.assertEqual(d.get("ffmpeg_path"), "/usr/bin/ffmpeg")
        finally:
            Path(path).unlink(missing_ok=True)
            if saved_mf is not None:
                os.environ["MAX_FRAMES_PER_SEGMENT"] = saved_mf

    def test_env_beats_yaml_file(self):
        content = "max_frames_per_segment: 3\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        try:
            with mock.patch.dict(
                os.environ,
                {"MOVIE_TELLER_CONFIG": path, "MAX_FRAMES_PER_SEGMENT": "7"},
                clear=False,
            ):
                d = load_flat_dict()
                self.assertEqual(d.get("max_frames_per_segment"), 7)
        finally:
            Path(path).unlink(missing_ok=True)

    def test_require_openai_raises(self):
        s = settings_from_dict({"openai_api_key": None})
        self.assertRaises(ValueError, s.require_openai)

    def test_require_api_key_custom(self):
        s = settings_from_dict({"api_keys": {"gemini": "g-key"}})
        self.assertEqual(s.require_api_key("gemini"), "g-key")

    def test_defaults(self):
        s = settings_from_dict({})
        self.assertEqual(s.max_frames_per_segment, 24)
        self.assertEqual(s.narration_frame_max_edge, 768)
        self.assertEqual(s.ffmpeg_path, "ffmpeg")
        self.assertEqual(s.default_prompt_style, "documentary")
        self.assertIsNone(s.frame_pool_manifest)
        self.assertEqual(s.pool_frames_per_shot_min, 1)
        self.assertEqual(s.pool_frames_per_shot_max, 3)
        self.assertIsNone(s.pool_frames_per_shot_rate)
        self.assertEqual(s.pool_miss_uniform_max_frames, 24)
        self.assertEqual(s.dialogue_overlap_threshold, 0.05)
        self.assertEqual(s.pyscenedetect_merge_sec, 0.25)
        self.assertEqual(s.subtitle_context_chunk_cue_count, 5)
        self.assertEqual(s.subtitle_context_chunk_stride, 3)
        self.assertEqual(s.subtitle_context_history_window_sec, 600.0)
        self.assertEqual(s.subtitle_context_top_k, 6)
        self.assertFalse(s.subtitle_context_summary_enabled)
        self.assertEqual(s.videocaptioner_asr, "bijian")
        self.assertEqual(s.videocaptioner_language, "auto")
        self.assertIsNone(s.videocaptioner_transcribe_timeout_ms)
        self.assertFalse(s.narration_polish_enabled)
        self.assertFalse(s.narration_tts_enabled)
        self.assertEqual(s.narration_polish_target_wpm, 150)
        self.assertEqual(s.narration_polish_cefr_level, "B1")
        self.assertEqual(s.narration_polish_strength, "medium")
        self.assertEqual(s.narration_polish_safety_margin_sec, 0.2)
        self.assertEqual(s.default_provider(), "newapi")
        self.assertEqual(dict(s.api_providers), {})
        self.assertEqual(tuple(s.model_catalog), ())
        self.assertEqual(dict(s.model_defaults), {})
        self.assertEqual(s.default_tts_voice(), "en-US-EmmaMultilingualNeural")
        self.assertEqual(s.default_tts_rate(), "+0%")
        self.assertEqual(s.default_tts_volume(), "+0%")
        self.assertEqual(s.default_tts_pitch(), "+0Hz")
        self.assertEqual(s.default_tts_boundary(), "SentenceBoundary")
        self.assertEqual(s.video_default_background_audio_volume, 0.35)
        self.assertEqual(s.video_default_speech_audio_volume, 1.0)
        self.assertEqual(s.narration_video_background_audio_volume, 0.35)
        self.assertEqual(s.narration_video_speech_audio_volume, 1.0)

    def test_videocaptioner_subtitle_overrides(self):
        s = settings_from_dict(
            {
                "videocaptioner_asr": "whisper-api",
                "videocaptioner_language": "en",
                "videocaptioner_transcribe_timeout_ms": 120000,
            }
        )
        self.assertEqual(s.videocaptioner_asr, "whisper-api")
        self.assertEqual(s.videocaptioner_language, "en")
        self.assertEqual(s.videocaptioner_transcribe_timeout_ms, 120000)

    def test_settings_from_dict_coercion(self):
        s = settings_from_dict(
            {
                "max_frames_per_segment": "12",
                "ffmpeg_path": "ff",
                "default_prompt_style": "how-to",
                "narration_frame_max_edge": "640",
                "pool_frames_per_shot_min": "2",
                "pool_frames_per_shot_max": "6",
                "pool_frames_per_shot_rate": "0.5",
                "pool_miss_uniform_max_frames": "10",
                "dialogue_overlap_threshold": "0.1",
                "pyscenedetect_merge_sec": "0.5",
                "subtitle_context_chunk_cue_count": "4",
                "subtitle_context_chunk_stride": "2",
                "subtitle_context_history_window_sec": "480",
                "subtitle_context_top_k": "8",
                "subtitle_context_summary_enabled": "true",
            }
        )
        self.assertEqual(s.max_frames_per_segment, 12)
        self.assertEqual(s.narration_frame_max_edge, 640)
        self.assertEqual(s.pool_frames_per_shot_min, 2)
        self.assertEqual(s.pool_frames_per_shot_max, 6)
        self.assertEqual(s.pool_frames_per_shot_rate, 0.5)
        self.assertEqual(s.pool_miss_uniform_max_frames, 10)
        self.assertEqual(s.dialogue_overlap_threshold, 0.1)
        self.assertEqual(s.pyscenedetect_merge_sec, 0.5)
        self.assertEqual(s.subtitle_context_chunk_cue_count, 4)
        self.assertEqual(s.subtitle_context_chunk_stride, 2)
        self.assertEqual(s.subtitle_context_history_window_sec, 480.0)
        self.assertEqual(s.subtitle_context_top_k, 8)
        self.assertTrue(s.subtitle_context_summary_enabled)

    def test_modelscope_env(self):
        with mock.patch("movieteller_config.loader._load_repo_dotenv", lambda: None):
            with mock.patch(
                "movieteller_config.loader._repo_root_config_paths",
                return_value=[],
            ):
                with mock.patch.dict(
                    os.environ,
                    {
                        "MODELSCOPE_API_KEY_FREE": "ms-free-token",
                        "MODELSCOPE_BASE_URL": "https://api-inference.modelscope.cn/v1",
                    },
                    clear=False,
                ):
                    s = load_settings()
                    self.assertEqual(s.get_api_key("modelscope"), "ms-free-token")
                    self.assertEqual(
                        s.get_api_base_url("modelscope"),
                        "https://api-inference.modelscope.cn/v1",
                    )

    def test_api_keys_json_placeholder_indirection(self):
        with mock.patch.dict(
            os.environ,
            {
                "MODELSCOPE_API_KEY_FREE": "resolved-ms",
                "API_KEYS_JSON": '{"modelscope":"$MODELSCOPE_API_KEY_FREE","openai":"${OPENAI_API_KEY}"}',
                "OPENAI_API_KEY": "resolved-openai",
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.get_api_key("modelscope"), "resolved-ms")
            self.assertEqual(s.get_api_key("openai"), "resolved-openai")

    def test_generic_prefix_api_key_env(self):
        with mock.patch.dict(os.environ, {"MY_PROVIDER_API_KEY": "secret-a"}, clear=False):
            s = load_settings()
            self.assertEqual(s.get_api_key("my_provider"), "secret-a")

    def test_api_providers_json_overrides_single_env(self):
        with mock.patch.dict(
            os.environ,
            {
                "FOO_BASE_URL": "https://wrong.example",
                'API_PROVIDERS_JSON': '{"foo":"https://right.example"}',
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.get_api_base_url("foo"), "https://right.example")

    def test_new_gateway_schema_defaults_are_available(self):
        s = settings_from_dict(
            {
                "gateway": {"default_provider": "newapi", "tts_provider": "dashscope"},
                "api_providers": {"newapi": "http://127.0.0.1:3000/v1"},
                "api_keys": {"newapi": "sk-new"},
                "model_catalog": [
                    "Qwen/Qwen3-VL-30B-A3B-Instruct",
                    "qwen2.5-7b-instruct",
                    "qwen3-tts-flash",
                    "text-embedding-v4",
                ],
                "model_defaults": {
                    "narration": "Qwen/Qwen3-VL-30B-A3B-Instruct",
                    "polish": "qwen2.5-7b-instruct",
                    "tts": "qwen3-tts-flash",
                    "embedding": "text-embedding-v4",
                },
                "tts_defaults": {
                    "voice": "Cherry",
                    "rate": "+5%",
                    "volume": "+1%",
                    "pitch": "+1Hz",
                    "boundary": "WordBoundary",
                },
                "video_defaults": {
                    "background_audio_volume": 0.2,
                    "speech_audio_volume": 1.2,
                },
            }
        )
        self.assertEqual(s.default_provider(), "newapi")
        self.assertEqual(s.get_api_base_url("newapi"), "http://127.0.0.1:3000/v1")
        self.assertEqual(s.default_model_for_capability("narration"), "Qwen/Qwen3-VL-30B-A3B-Instruct")
        self.assertEqual(s.default_model_for_capability("polish"), "qwen2.5-7b-instruct")
        self.assertEqual(s.default_model_for_capability("tts"), "qwen3-tts-flash")
        self.assertEqual(s.default_model_for_capability("embedding"), "text-embedding-v4")
        self.assertEqual(s.provider_for_capability("narration"), "newapi")
        self.assertEqual(s.provider_for_capability("tts"), "dashscope")
        self.assertEqual(s.narration_options().model, "Qwen/Qwen3-VL-30B-A3B-Instruct")
        self.assertEqual(s.narration_polish_options().model, "qwen2.5-7b-instruct")
        speech_options = s.narration_speech_options()
        self.assertEqual(speech_options.provider_slug, "dashscope")
        self.assertEqual(speech_options.model, "qwen3-tts-flash")
        self.assertEqual(speech_options.voice, "Cherry")
        self.assertEqual(speech_options.rate, "+5%")
        self.assertEqual(speech_options.volume, "+1%")
        self.assertEqual(speech_options.pitch, "+1Hz")
        self.assertEqual(speech_options.boundary, "WordBoundary")
        video_options = s.narration_video_options()
        self.assertEqual(video_options.background_audio_volume, 0.2)
        self.assertEqual(video_options.speech_audio_volume, 1.2)

    def test_new_schema_env_overrides(self):
        with mock.patch.dict(
            os.environ,
            {
                "GATEWAY_DEFAULT_PROVIDER": "NEWAPI",
                "GATEWAY_TTS_PROVIDER": "DASHSCOPE",
                "API_PROVIDERS_JSON": '{"newapi":"http://127.0.0.1:3000/v1"}',
                "MODEL_DEFAULTS_JSON": '{"narration":"vision-x","polish":"text-y","tts":"tts-z","embedding":"embed-w"}',
                "TTS_DEFAULT_VOICE": "Cherry",
                "VIDEO_DEFAULT_BACKGROUND_AUDIO_VOLUME": "0.2",
                "VIDEO_DEFAULT_SPEECH_AUDIO_VOLUME": "1.2",
                "NARRATION_TTS_ENABLED": "true",
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.default_provider(), "newapi")
            self.assertEqual(s.provider_for_capability("tts"), "dashscope")
            self.assertEqual(s.get_api_base_url("newapi"), "http://127.0.0.1:3000/v1")
            self.assertEqual(s.default_model_for_capability("narration"), "vision-x")
            self.assertEqual(s.default_model_for_capability("polish"), "text-y")
            self.assertEqual(s.default_model_for_capability("tts"), "tts-z")
            self.assertEqual(s.default_model_for_capability("embedding"), "embed-w")
            self.assertEqual(s.default_tts_voice(), "Cherry")
            self.assertEqual(s.video_default_background_audio_volume, 0.2)
            self.assertEqual(s.video_default_speech_audio_volume, 1.2)
            self.assertTrue(s.narration_tts_enabled)

    def test_missing_default_model_raises(self):
        s = settings_from_dict({})
        with self.assertRaises(ValueError):
            s.default_model_for_capability("narration")


if __name__ == "__main__":
    unittest.main()
