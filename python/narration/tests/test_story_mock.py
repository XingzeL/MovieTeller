from unittest.mock import MagicMock

from movieteller_config.schema import settings_from_dict

from narration.story import generate_narration


def test_generate_narration_uses_injected_client():
    settings = settings_from_dict(
        {
            "openai_api_key": "sk-test",
            "narration_image_model": "gpt-4o-mini",
        }
    )
    fake_client = MagicMock()
    fake_resp = MagicMock()
    fake_resp.choices = [MagicMock()]
    fake_resp.choices[0].message.content = "Narration line."
    fake_client.chat.completions.create.return_value = fake_resp

    text = generate_narration(
        system_message="sys",
        user_text="user",
        frames_base64_png=["ZmFrZQ=="],  # "fake" base64
        model="gpt-4o-mini",
        settings=settings,
        client_factory=lambda _k, _b: fake_client,
    )
    assert text == "Narration line."
    fake_client.chat.completions.create.assert_called_once()
    call_kw = fake_client.chat.completions.create.call_args
    assert call_kw.kwargs["model"] == "gpt-4o-mini"
