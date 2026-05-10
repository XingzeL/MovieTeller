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
                "NARRATION_IMAGE_MODEL": "gpt-4o",
                "MAX_FRAMES_PER_SEGMENT": "8",
                "NARRATION_FRAME_MAX_EDGE": "512",
                "NARRATION_PROVIDER": "modelscope",
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.openai_api_key, "sk-test")
            self.assertEqual(s.get_api_key("openai"), "sk-test")
            self.assertEqual(s.narration_image_model, "gpt-4o")
            self.assertEqual(s.max_frames_per_segment, 8)
            self.assertEqual(s.narration_frame_max_edge, 512)
            self.assertEqual(s.narration_provider, "modelscope")

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
narration_image_model: from-file
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
                        self.assertEqual(d.get("narration_image_model"), "from-file")
                        self.assertEqual(d.get("max_frames_per_segment"), 3)
        finally:
            Path(path).unlink(missing_ok=True)
            if saved_mf is not None:
                os.environ["MAX_FRAMES_PER_SEGMENT"] = saved_mf

    def test_env_beats_yaml_file(self):
        content = "narration_image_model: from-yaml\n"
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        ) as f:
            f.write(content)
            path = f.name
        try:
            with mock.patch.dict(
                os.environ,
                {"MOVIE_TELLER_CONFIG": path, "NARRATION_IMAGE_MODEL": "from-env"},
                clear=False,
            ):
                d = load_flat_dict()
                self.assertEqual(d.get("narration_image_model"), "from-env")
        finally:
            Path(path).unlink(missing_ok=True)

    def test_require_openai_raises(self):
        from movieteller_config.schema import settings_from_dict

        s = settings_from_dict({"openai_api_key": None, "narration_image_model": "gpt-4o-mini"})
        self.assertRaises(ValueError, s.require_openai)

    def test_require_api_key_custom(self):
        s = settings_from_dict(
            {
                "api_keys": {"gemini": "g-key"},
                "narration_image_model": "gpt-4o-mini",
            }
        )
        self.assertEqual(s.require_api_key("gemini"), "g-key")

    def test_videocaptioner_subtitle_defaults(self):
        s = settings_from_dict({"narration_image_model": "gpt-4o-mini"})
        self.assertEqual(s.videocaptioner_asr, "bijian")
        self.assertEqual(s.videocaptioner_language, "auto")
        self.assertIsNone(s.videocaptioner_transcribe_timeout_ms)
        self.assertFalse(s.narration_polish_enabled)
        self.assertEqual(s.narration_polish_model_index, 0)
        self.assertEqual(s.narration_polish_target_wpm, 150)
        self.assertEqual(s.narration_polish_cefr_level, "B1")
        self.assertEqual(s.narration_polish_strength, "medium")
        self.assertEqual(s.narration_polish_safety_margin_sec, 0.2)
        self.assertEqual(len(s.narration_provider_models), 0)
        self.assertEqual(len(s.narration_provider_model_catalog), 0)
        self.assertEqual(len(s.narration_polish_provider_models), 0)
        self.assertEqual(len(s.narration_polish_provider_model_catalog), 0)

    def test_videocaptioner_subtitle_overrides(self):
        s = settings_from_dict(
            {
                "narration_image_model": "gpt-4o-mini",
                "videocaptioner_asr": "whisper-api",
                "videocaptioner_language": "en",
                "videocaptioner_transcribe_timeout_ms": 120000,
            }
        )
        self.assertEqual(s.videocaptioner_asr, "whisper-api")
        self.assertEqual(s.videocaptioner_language, "en")
        self.assertEqual(s.videocaptioner_transcribe_timeout_ms, 120000)

    def test_narration_polish_overrides(self):
        s = settings_from_dict(
            {
                "narration_image_model": "gpt-4o-mini",
                "narration_provider": "volcengine",
                "narration_polish_provider_models": {"openai": "gpt-4.1-mini"},
                "narration_polish_enabled": True,
                "narration_polish_provider": "openai",
                "narration_polish_model": "gpt-4.1-nano",
                "narration_polish_target_wpm": 172,
                "narration_polish_cefr_level": "c1",
                "narration_polish_strength": "Strong",
                "narration_polish_safety_margin_sec": "0.35",
            }
        )
        self.assertTrue(s.narration_polish_enabled)
        self.assertEqual(s.polish_provider(), "openai")
        self.assertEqual(s.polish_model_for_provider(), "gpt-4.1-nano")
        self.assertEqual(s.narration_polish_target_wpm, 172)
        self.assertEqual(s.narration_polish_cefr_level, "C1")
        self.assertEqual(s.narration_polish_strength, "strong")
        self.assertEqual(s.narration_polish_safety_margin_sec, 0.35)

    def test_narration_polish_provider_catalog_and_index(self):
        s = settings_from_dict(
            {
                "narration_provider": "volcengine",
                "narration_polish_provider": "glm",
                "narration_provider_model_catalog": {
                    "volcengine": ["vision-a", "vision-b"],
                },
                "narration_polish_provider_model_catalog": {
                    "glm": ["text-a", "text-b", "text-c"],
                },
                "narration_polish_model_index": 2,
                "narration_image_model": "fallback-m",
            }
        )
        self.assertEqual(s.polish_provider(), "glm")
        self.assertEqual(s.polish_model_for_provider(), "text-c")
        self.assertEqual(s.model_for_provider("volcengine"), "vision-a")

    def test_scoped_model_pools_override_shared_catalog(self):
        s = settings_from_dict(
            {
                "narration_provider": "volcengine",
                "narration_provider_model_catalog": {"volcengine": ["vision-only"]},
                "narration_polish_provider": "volcengine",
                "narration_polish_provider_model_catalog": {
                    "volcengine": ["text-only", "text-backup"]
                },
                "narration_image_model": "fallback-m",
            }
        )
        self.assertEqual(s.model_for_provider("volcengine"), "vision-only")
        self.assertEqual(s.polish_model_for_provider(), "text-only")

    def test_settings_from_dict_coercion(self):
        s = settings_from_dict(
            {
                "narration_image_model": "x",
                "max_frames_per_segment": "12",
                "ffmpeg_path": "ff",
                "default_prompt_style": "how-to",
                "narration_frame_max_edge": "640",
            }
        )
        self.assertEqual(s.max_frames_per_segment, 12)
        self.assertEqual(s.narration_frame_max_edge, 640)
        self.assertEqual(s.narration_provider, "openai")
        self.assertEqual(len(s.api_keys), 0)
        self.assertEqual(len(s.api_base_urls), 0)
        self.assertEqual(len(s.narration_provider_models), 0)
        self.assertEqual(len(s.narration_provider_model_catalog), 0)
        self.assertEqual(len(s.narration_polish_provider_models), 0)
        self.assertEqual(len(s.narration_polish_provider_model_catalog), 0)

    def test_narration_provider_model_catalog_and_index(self):
        s = settings_from_dict(
            {
                "narration_provider": "volcengine",
                "narration_image_model": "fallback-m",
                "narration_provider_model_catalog": {
                    "volcengine": ["ep-first", "ep-second"],
                },
            }
        )
        self.assertEqual(s.model_for_provider("volcengine"), "ep-first")
        s2 = settings_from_dict(
            {
                "narration_provider": "volcengine",
                "narration_image_model": "fallback-m",
                "narration_provider_model_catalog": {"volcengine": ["a", "b"]},
                "narration_model_index": 1,
            }
        )
        self.assertEqual(s2.model_for_provider("volcengine"), "b")

    def test_narration_model_env_overrides_catalog(self):
        with mock.patch("movieteller_config.loader._load_repo_dotenv", lambda: None):
            with mock.patch.dict(
                os.environ,
                {
                    "NARRATION_PROVIDER": "volcengine",
                    "NARRATION_MODEL": "ep-explicit",
                    "NARRATION_PROVIDER_MODEL_CATALOG_JSON": '{"volcengine":["a","b"]}',
                    "NARRATION_IMAGE_MODEL": "fallback-m",
                },
                clear=True,
            ):
                s = load_settings()
                self.assertEqual(s.model_for_provider("volcengine"), "ep-explicit")

    def test_narration_provider_models_override_catalog(self):
        s = settings_from_dict(
            {
                "narration_provider": "volcengine",
                "narration_provider_models": {"volcengine": "pinned-model"},
                "narration_provider_model_catalog": {"volcengine": ["a", "b"]},
                "narration_image_model": "fallback-m",
            }
        )
        self.assertEqual(s.model_for_provider("volcengine"), "pinned-model")

    def test_other_slug_uses_catalog_index_zero(self):
        s = settings_from_dict(
            {
                "narration_provider": "volcengine",
                "narration_provider_model_catalog": {
                    "volcengine": ["v1", "v2"],
                    "modelscope": ["m1", "m2"],
                },
                "narration_model_index": 1,
                "narration_image_model": "fallback-m",
            }
        )
        self.assertEqual(s.model_for_provider("modelscope"), "m1")

    def test_provider_models_per_slug_and_fallback(self):
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-x",
                "MODELSCOPE_API_KEY": "ms-x",
                "NARRATION_PROVIDER_MODELS_JSON": '{"openai":"gpt-4o","modelscope":"qwen/Qwen-VL-Max"}',
                "NARRATION_IMAGE_MODEL": "gpt-4o-mini",
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.model_for_provider("openai"), "gpt-4o")
            self.assertEqual(s.model_for_provider("modelscope"), "qwen/Qwen-VL-Max")
            self.assertEqual(s.model_for_provider("anthropic"), "gpt-4o-mini")

    def test_settings_from_dict_narration_provider_models(self):
        s = settings_from_dict(
            {
                "narration_image_model": "fallback-m",
                "narration_provider_models": {
                    "openai": "gpt-4o",
                    "modelscope": "qwen/Qwen-VL-Max",
                },
            }
        )
        self.assertEqual(s.model_for_provider("openai"), "gpt-4o")
        self.assertEqual(s.model_for_provider("other"), "fallback-m")

    def test_modelscope_env(self):
        saved_json = os.environ.pop("API_BASE_URLS_JSON", None)
        try:
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
                            "NARRATION_IMAGE_MODEL": "qwen/Qwen-VL-Max",
                        },
                        clear=False,
                    ):
                        s = load_settings()
                        self.assertEqual(s.get_api_key("modelscope"), "ms-free-token")
                        self.assertEqual(
                            s.get_api_base_url("modelscope"),
                            "https://api-inference.modelscope.cn/v1",
                        )
                        self.assertEqual(s.narration_image_model, "qwen/Qwen-VL-Max")
        finally:
            if saved_json is not None:
                os.environ["API_BASE_URLS_JSON"] = saved_json

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

    def test_api_base_urls_json_overrides_single_env(self):
        with mock.patch.dict(
            os.environ,
            {
                "FOO_BASE_URL": "https://wrong.example",
                'API_BASE_URLS_JSON': '{"foo":"https://right.example"}',
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.get_api_base_url("foo"), "https://right.example")

    def test_narration_polish_env_overrides(self):
        with mock.patch.dict(
            os.environ,
            {
                "NARRATION_POLISH_ENABLED": "true",
                "NARRATION_POLISH_PROVIDER": "OPENAI",
                "NARRATION_POLISH_MODEL": "gpt-4.1-mini",
                "NARRATION_POLISH_MODEL_INDEX": "2",
                "NARRATION_POLISH_TARGET_WPM": "165",
                "NARRATION_POLISH_CEFR_LEVEL": "a1",
                "NARRATION_POLISH_STRENGTH": "LIGHT",
                "NARRATION_POLISH_SAFETY_MARGIN_SEC": "0.5",
            },
            clear=False,
        ):
            s = load_settings()
            self.assertTrue(s.narration_polish_enabled)
            self.assertEqual(s.narration_polish_provider, "openai")
            self.assertEqual(s.narration_polish_model, "gpt-4.1-mini")
            self.assertEqual(s.narration_polish_model_index, 2)
            self.assertEqual(s.narration_polish_target_wpm, 165)
            self.assertEqual(s.narration_polish_cefr_level, "A1")
            self.assertEqual(s.narration_polish_strength, "light")
            self.assertEqual(s.narration_polish_safety_margin_sec, 0.5)

    def test_scoped_model_catalog_env_overrides(self):
        with mock.patch("movieteller_config.loader._load_repo_dotenv", lambda: None):
            with mock.patch.dict(
                os.environ,
                {
                    "NARRATION_PROVIDER": "volcengine",
                    "NARRATION_PROVIDER_MODEL_CATALOG_JSON": '{"volcengine":["vision-a","vision-b"]}',
                    "NARRATION_POLISH_PROVIDER": "dashscope",
                    "NARRATION_POLISH_PROVIDER_MODEL_CATALOG_JSON": '{"dashscope":["text-a","text-b"]}',
                    "NARRATION_POLISH_MODEL_INDEX": "1",
                    "NARRATION_IMAGE_MODEL": "fallback-m",
                },
                clear=True,
            ):
                s = load_settings()
                self.assertEqual(s.model_for_provider("volcengine"), "vision-a")
                self.assertEqual(s.polish_provider(), "dashscope")
                self.assertEqual(s.polish_model_for_provider(), "text-b")


if __name__ == "__main__":
    unittest.main()
