from unittest.mock import MagicMock

from movieteller_config.schema import settings_from_dict

from narration_polish import (
    compute_target_duration_sec,
    compute_target_word_count,
    count_words,
    estimate_speech_duration_sec,
    polish_narration_text,
)


def test_word_budget_helpers():
    assert count_words("A short line.") == 3
    assert round(estimate_speech_duration_sec("one two three", 180), 2) == 1.0
    assert compute_target_duration_sec(3.0, 0.25) == 2.75
    assert compute_target_word_count(3.0, 120, 0.0) == 6


def test_polish_narration_uses_injected_client_and_enforces_budget():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_keys": {"newapi": "sk-test"},
            "api_providers": {"newapi": "https://example.test/v1"},
            "model_defaults": {"polish": "seed-vision"},
            "narration_polish_target_wpm": 120,
            "narration_polish_cefr_level": "B1",
            "narration_polish_strength": "strong",
            "narration_polish_safety_margin_sec": 0.0,
        }
    )
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message.content = (
        "A girl stands outside with a backpack while someone writes in a notebook by a desk."
    )
    fake_client.chat.completions.create.return_value = fake_resp

    options = settings.narration_polish_options()
    result = polish_narration_text(
        "A young girl in a pink dress stands outside with a backpack, crossing her arms.",
        2.5,
        options=options,
        settings=settings,
        client_factory=lambda _k, _b: fake_client,
    )
    assert result.provider == "newapi"
    assert result.model == "seed-vision"
    assert result.target_word_count == 5
    assert count_words(result.polished_text) <= result.target_word_count
    assert result.fits_duration
    fake_client.chat.completions.create.assert_called_once()


def test_polish_narration_respects_explicit_provider_and_model_overrides():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_keys": {"newapi": "sk-openai"},
            "api_providers": {"newapi": "https://example.test/v1"},
            "model_defaults": {"polish": "gpt-4.1-mini"},
        }
    )

    def fake_client_factory(_k, _b):
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "A student looks down at a letter."
        client.chat.completions.create.return_value = resp
        return client

    options = settings.narration_polish_options()
    result = polish_narration_text(
        "A student receives a letter and looks down at it in class.",
        3.0,
        options=options,
        settings=settings,
        client_factory=fake_client_factory,
    )
    assert result.provider == "newapi"
    assert result.model == "gpt-4.1-mini"


def test_polish_narration_uses_dedicated_provider_and_catalog_index():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_keys": {"newapi": "sk-new"},
            "api_providers": {"newapi": "https://newapi.example/v1"},
            "model_defaults": {"polish": "text-b"},
        }
    )

    def fake_client_factory(_k, _b):
        client = MagicMock()
        resp = MagicMock()
        resp.choices = [MagicMock()]
        resp.choices[0].message.content = "A student reads a letter."
        client.chat.completions.create.return_value = resp
        return client

    options = settings.narration_polish_options()
    result = polish_narration_text(
        "A student receives a letter and looks down at it in class.",
        3.0,
        options=options,
        settings=settings,
        client_factory=fake_client_factory,
    )
    assert result.provider == "newapi"
    assert result.model == "text-b"
