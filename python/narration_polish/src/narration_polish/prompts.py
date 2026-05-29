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


def _language_name(code: str | None) -> str:
    value = (code or "").strip().lower()
    return {
        "en": "English",
        "zh": "Chinese",
        "ja": "Japanese",
        "ko": "Korean",
        "vi": "Vietnamese",
        "fr": "French",
        "de": "German",
        "es": "Spanish",
    }.get(value, value or "English")


def build_system_message(*, cefr_level: str, strength: str, style: str | None = None, output_language: str = "en") -> str:
    style_hint = _style_hint(style)
    lang = _language_name(output_language)
    return (
        f"You rewrite short video narration in {lang} for text-to-speech. "
        f"Target language difficulty: CEFR {cefr_level}. "
        f"Rewrite strength: {strength}. "
        "Keep the meaning visually grounded, natural to read aloud, and concise. "
        f"{style_hint} "
        "The first line must start with TITLE: followed by a short Chinese scene label "
        "(at most 10 characters; no English on that line).\n"
        f"The second line must start with BODY: followed by the final {lang} narration. "
        "If the narration needs more than one line, continue on extra lines without a "
        "second TITLE: prefix."
    )


def build_user_message(
    *,
    text: str,
    segment_duration_sec: float,
    target_duration_sec: float,
    target_wpm: int,
    target_word_count: int,
    strength: str,
    output_language: str = "en",
) -> str:
    return (
        "Rewrite the narration so spoken audio fits the target duration.\n"
        "Hard constraints:\n"
        f"- Keep the final narration within about {target_duration_sec:.2f} seconds.\n"
        f"- Aim for no more than {target_word_count} words at about {target_wpm} WPM.\n"
        f"- Use plain natural {_language_name(output_language)} for voice-over.\n"
        "- Keep only visually supported facts from the original.\n"
        "- Prefer one short sentence; use two only if needed.\n"
        "- If space is tight, summarize instead of overflowing.\n"
        f"- Rewrite strength: {strength}.\n"
        f"- Original segment duration: {segment_duration_sec:.2f} seconds.\n\n"
        "Respond with exactly two lines in this shape (TITLE line then BODY line):\n"
        "TITLE:<Chinese scene label up to 10 characters>\n"
        f"BODY:<{_language_name(output_language)} narration>\n\n"
        "Original narration:\n"
        f"{text}"
    )


def build_title_only_system_message() -> str:
    return (
        "You label a short movie scene for a study card. "
        "Reply with one line only: at most 10 Chinese characters describing the scene. "
        "No English, no quotes, no numbering, no explanation."
    )


def build_title_only_user_message(
    *,
    polished_english: str,
    segment_duration_sec: float,
) -> str:
    return (
        f"Segment length about {segment_duration_sec:.2f} seconds.\n"
        "Polished English narration (for context only, do not translate it):\n"
        f"{polished_english}\n\n"
        "Give one Chinese scene title (max 10 characters)."
    )


def build_vocab_highlight_system_message(output_language: str = "en") -> str:
    lang = _language_name(output_language)
    return (
        f"You extract study-vocabulary highlights from a short {lang} narration passage. "
        "Pick words or short phrases that are useful for a learner at the CEFR level given "
        "in the user message (not trivial at that level; include useful collocations when apt). "
        "Your reply MUST be one JSON object only: no markdown, no code fences, no text before "
        "or after the JSON.\n\n"
        "Required JSON shape:\n"
        '- passage_id: string (use "seg" if you have no better id)\n'
        "- highlights_count: integer, must equal the length of data\n"
        "- data: array of objects, each with:\n"
        "  - match_text: exact substring copied from the passage (case-sensitive)\n"
        "  - word_root: lemma or stem (English)\n"
        "  - pos: short part-of-speech label (e.g. n., v., adj.)\n"
        "  - definition: concise Chinese gloss for the highlighted span\n"
        "  - note: optional short Chinese learning tip (may be \"\")\n"
        "- full_translation: fluent Chinese translation of the entire passage\n\n"
        "Rules: match_text must appear verbatim in the passage. Avoid redundant overlaps. "
        "Prefer a modest number of high-quality items (often about 3–10 for a short passage)."
    )


def build_vocab_highlight_user_message(*, passage: str, cefr_level: str, output_language: str = "en") -> str:
    level = (cefr_level or "").strip() or "B1"
    return (
        f"CEFR level for selection difficulty: {level}.\n\n"
        f"Passage ({_language_name(output_language)}):\n"
        f"{passage.rstrip()}\n\n"
        "Respond with one JSON object only, following the schema from the system message."
    )
