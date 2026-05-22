from unittest.mock import MagicMock

from movieteller_config.schema import settings_from_dict

from narration_polish import (
    compute_target_duration_sec,
    compute_target_word_count,
    count_words,
    estimate_speech_duration_sec,
    generate_vocab_study_card,
    parse_polish_response,
    parse_vocab_study_card_json,
    polish_narration_text,
)


def test_word_budget_helpers():
    assert count_words("A short line.") == 3
    assert round(estimate_speech_duration_sec("one two three", 180), 2) == 1.0
    assert compute_target_duration_sec(3.0, 0.25) == 2.75
    assert compute_target_word_count(3.0, 120, 0.0) == 6


def test_parse_polish_response_structured_two_lines():
    raw = "TITLE:酒吧对峙\nBODY:A man looks left. Then right."
    title, body, structured = parse_polish_response(raw)
    assert structured is True
    assert title == "酒吧对峙"
    assert body == "A man looks left. Then right."


def test_parse_polish_response_structured_multiline_body():
    raw = "TITLE:短标题\nBODY:A man looks.\nSecond sentence here."
    title, body, structured = parse_polish_response(raw)
    assert structured is True
    assert title == "短标题"
    assert "Second sentence" in body


def test_parse_polish_response_title_only_then_body_lines():
    raw = "TITLE:走廊\nSome english without body prefix.\nMore text."
    title, body, structured = parse_polish_response(raw)
    assert structured is True
    assert title == "走廊"
    assert "without body prefix" in body


def test_parse_polish_response_legacy_plain():
    raw = "Just plain English narration here."
    title, body, structured = parse_polish_response(raw)
    assert structured is False
    assert title is None
    assert body == "Just plain English narration here."


def test_parse_vocab_json_plain_object():
    raw = (
        '{"passage_id":"p1","highlights_count":1,'
        '"data":[{"match_text":"hello","word_root":"hello","pos":"intj",'
        '"definition":"你好","note":""}],"full_translation":"你好世界"}'
    )
    out = parse_vocab_study_card_json(raw)
    assert out is not None
    assert out["passage_id"] == "p1"
    assert out["highlights_count"] == 1
    assert len(out["data"]) == 1
    assert out["data"][0]["match_text"] == "hello"
    assert out["full_translation"] == "你好世界"


def test_parse_vocab_json_strips_markdown_fence():
    raw = """```json
{"passage_id":"x","highlights_count":0,"data":[],"full_translation":""}
```"""
    out = parse_vocab_study_card_json(raw)
    assert out is not None
    assert out["data"] == []


def test_parse_vocab_json_invalid_returns_none():
    assert parse_vocab_study_card_json("") is None
    assert parse_vocab_study_card_json("not json") is None
    assert parse_vocab_study_card_json('{"data": "bad"}') is None


def test_generate_vocab_study_card_uses_dedicated_enrichment_call():
    settings = settings_from_dict(
        {
            "gateway": {"default_provider": "newapi"},
            "api_keys": {"newapi": "sk-test"},
            "api_providers": {"newapi": "https://example.test/v1"},
            "model_defaults": {"polish": "seed-vision"},
        }
    )
    fake_client = MagicMock()
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = (
        '{"passage_id":"seg","highlights_count":1,'
        '"data":[{"match_text":"outside","word_root":"outside","pos":"adv.",'
        '"definition":"在外面","note":""}],"full_translation":"女孩在外面。"}'
    )
    fake_client.chat.completions.create.return_value = response

    card, elapsed = generate_vocab_study_card(
        "A girl stands outside.",
        cefr_level="B1",
        settings=settings,
        client_factory=lambda _k, _b: fake_client,
    )

    assert elapsed >= 0
    assert card is not None
    assert card["data"][0]["match_text"] == "outside"
    assert fake_client.chat.completions.create.call_count == 1


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
    resp_polish = MagicMock()
    resp_polish.choices = [MagicMock()]
    resp_polish.choices[0].message.content = (
        "A girl stands outside with a backpack while someone writes in a notebook by a desk."
    )
    fake_client.chat.completions.create.return_value = resp_polish

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
    assert fake_client.chat.completions.create.call_count == 1


def test_polish_narration_structured_sets_scene_title_zh():
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
    resp_polish = MagicMock()
    resp_polish.choices = [MagicMock()]
    resp_polish.choices[0].message.content = (
        "TITLE:窗外女孩\n"
        "BODY:A girl stands outside with a backpack while someone writes in a notebook by a desk."
    )
    fake_client.chat.completions.create.return_value = resp_polish

    options = settings.narration_polish_options()
    result = polish_narration_text(
        "A young girl in a pink dress stands outside with a backpack, crossing her arms.",
        2.5,
        options=options,
        settings=settings,
        client_factory=lambda _k, _b: fake_client,
    )
    assert result.scene_title_zh == "窗外女孩"
    assert count_words(result.polished_text) <= result.target_word_count
    assert "outside" in result.polished_text.lower()
    assert fake_client.chat.completions.create.call_count == 1


def test_polish_narration_title_only_retry_when_title_too_long():
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
    resp1 = MagicMock()
    resp1.choices = [MagicMock()]
    resp1.choices[0].message.content = (
        "TITLE:这是一个超过十个汉字长度的场景标题\n"
        "BODY:A girl stands outside with a backpack while someone writes in a notebook by a desk."
    )
    resp2 = MagicMock()
    resp2.choices = [MagicMock()]
    resp2.choices[0].message.content = "窗外女孩"
    fake_client.chat.completions.create.side_effect = [resp1, resp2]

    options = settings.narration_polish_options()
    result = polish_narration_text(
        "A young girl in a pink dress stands outside with a backpack, crossing her arms.",
        2.5,
        options=options,
        settings=settings,
        client_factory=lambda _k, _b: fake_client,
    )
    assert result.scene_title_zh == "窗外女孩"
    assert fake_client.chat.completions.create.call_count == 2


def test_polish_narration_respects_explicit_model_override():
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
        resp_polish = MagicMock()
        resp_polish.choices = [MagicMock()]
        resp_polish.choices[0].message.content = "A student looks down at a letter."
        client.chat.completions.create.return_value = resp_polish
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
        resp_polish = MagicMock()
        resp_polish.choices = [MagicMock()]
        resp_polish.choices[0].message.content = "A student reads a letter."
        client.chat.completions.create.return_value = resp_polish
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
