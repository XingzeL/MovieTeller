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
        self.assertEqual(len(s.provider_models), 0)

    def test_provider_models_per_slug_and_fallback(self):
        with mock.patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "sk-x",
                "MODELSCOPE_API_KEY": "ms-x",
                "PROVIDER_MODELS_JSON": '{"openai":"gpt-4o","modelscope":"qwen/Qwen-VL-Max"}',
                "NARRATION_IMAGE_MODEL": "gpt-4o-mini",
            },
            clear=False,
        ):
            s = load_settings()
            self.assertEqual(s.model_for_provider("openai"), "gpt-4o")
            self.assertEqual(s.model_for_provider("modelscope"), "qwen/Qwen-VL-Max")
            self.assertEqual(s.model_for_provider("anthropic"), "gpt-4o-mini")

    def test_settings_from_dict_provider_models(self):
        s = settings_from_dict(
            {
                "narration_image_model": "fallback-m",
                "provider_models": {"openai": "gpt-4o", "modelscope": "qwen/Qwen-VL-Max"},
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


if __name__ == "__main__":
    unittest.main()
