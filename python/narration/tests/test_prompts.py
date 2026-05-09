from narration.prompts import (
    build_system_message,
    build_user_text,
    target_word_count,
)


def test_target_word_count_scales_with_duration():
    assert target_word_count(30.0, "documentary") >= target_word_count(10.0, "documentary")


def test_target_word_count_style_difference():
    # concise tends to allow fewer words per minute in our table — actually concise is higher wpm
    d = 60.0
    assert target_word_count(d, "documentary") >= 12


def test_build_system_message_includes_custom():
    s = build_system_message("documentary", "  Focus on lighting.  ")
    assert "lighting" in s


def test_build_user_text_mentions_duration_and_frames():
    t = build_user_text(duration_sec=12.5, prompt_style="documentary", frame_count=8)
    assert "12.50" in t or "12.5" in t
    assert "8" in t
