from __future__ import annotations


def _style_hint(style: str | None) -> str:
    s = (style or "").strip().lower()
    if s in {"movie_commentary", "movie-commentary"}:
        return (
            " Preserve a movie commentary voice: flowing, scene-led, and lightly dramatic, "
            "like a film recap narrator."
        )
    if s == "documentary":
        return " Preserve a calm, observational documentary voice."
    if s == "cinematic":
        return " Preserve a cinematic, scene-setting voice."
    if s == "educational":
        return " Preserve a clear, explanatory educational voice."
    if s == "concise":
        return " Preserve a crisp, concise voice-over style."
    return ""


def build_system_message(*, cefr_level: str, strength: str, style: str | None = None) -> str:
    style_hint = _style_hint(style)
    return (
        "You rewrite short English video narration for text-to-speech. "
        f"Target language difficulty: CEFR {cefr_level}. "
        f"Rewrite strength: {strength}. "
        "Keep the meaning visually grounded, natural to read aloud, and concise. "
        f"{style_hint} "
        "Do not explain your choices. Output only the final narration text."
    )


def build_user_message(
    *,
    text: str,
    segment_duration_sec: float,
    target_duration_sec: float,
    target_wpm: int,
    target_word_count: int,
    strength: str,
) -> str:
    return (
        "Rewrite the narration so spoken audio fits the target duration.\n"
        "Hard constraints:\n"
        f"- Keep the final narration within about {target_duration_sec:.2f} seconds.\n"
        f"- Aim for no more than {target_word_count} words at about {target_wpm} WPM.\n"
        "- Use plain natural English for voice-over.\n"
        "- Keep only visually supported facts from the original.\n"
        "- Prefer one short sentence; use two only if needed.\n"
        "- If space is tight, summarize instead of overflowing.\n"
        f"- Rewrite strength: {strength}.\n"
        f"- Original segment duration: {segment_duration_sec:.2f} seconds.\n\n"
        "Original narration:\n"
        f"{text}"
    )
