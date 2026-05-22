from __future__ import annotations

from typing import Sequence

# Words per minute style hints (used only for target length, not hard limits)
_WORDS_PER_MIN: dict[str, float] = {
    "documentary": 65.0,
    "cinematic": 50.0,
    "concise": 80.0,
    "educational": 70.0,
    "movie_commentary": 300.0
}

_DEFAULT_SYSTEM = """You are a professional film narrator. Describe what is visible in the \
provided key frames in clear, natural English. Stay faithful to the imagery; do not invent \
plot or characters that are not shown. Output plain narration only — no bullet lists, no \
meta commentary, and no frame numbers."""


def _style_system_addendum(style: str) -> str:
    s = style.strip().lower()
    if s in {"movie_commentary", "movie-commentary"}:
        return (
            " Use a movie commentary / film recap tone: vivid, flowing, and slightly dramatic, "
            "as if guiding the audience through the scene beat by beat. Keep every statement "
            "grounded in what is visually supported by the frames."
        )
    if s == "cinematic":
        return " Use a slightly dramatic, scene-setting tone; still stay literal to the frames."
    if s == "concise":
        return " Be brief: one or two short sentences unless the scene is very rich."
    if s == "educational":
        return " Emphasize concrete, teachable visual facts (objects, actions, setting)."
    if s == "documentary":
        return " Calm, observational tone; like a nature or history documentary voice-over."
    return ""


def target_word_count(duration_sec: float, prompt_style: str) -> int:
    """Heuristic caption length from segment duration and style."""
    wpm = _WORDS_PER_MIN.get(prompt_style.strip().lower(), 125.0)
    raw = duration_sec * (wpm / 60.0)
    # Keep within a sane band for short clips
    return max(12, min(420, int(round(raw))))


def build_system_message(prompt_style: str, custom_prompt: str) -> str:
    base = _DEFAULT_SYSTEM + _style_system_addendum(prompt_style)
    extra = custom_prompt.strip()
    if extra:
        return f"{base}\n\nAdditional instructions from the user:\n{extra}"
    return base


def build_user_text(
    *,
    duration_sec: float,
    prompt_style: str,
    frame_count: int,
    prev_subtitle_text: str | None = None,
    next_subtitle_text: str | None = None,
    retrieved_context_texts: Sequence[str] = (),
) -> str:
    """User message text accompanying the image batch."""
    words = target_word_count(duration_sec, prompt_style)
    parts = [
        (
        f"This segment is about {duration_sec:.2f} seconds long "
        f"(use roughly {words} words as a soft target, not a hard count), but you must generate less than {2 * words} words !!"
        f"You are given {frame_count} evenly spaced key frames from this segment. "
        "Write continuous narration that flows across the segment."
        )
    ]
    boundary_lines: list[str] = []
    prev_text = str(prev_subtitle_text or "").strip()
    next_text = str(next_subtitle_text or "").strip()
    if prev_text or next_text:
        boundary_lines.append("[Scene Boundary]")
        if prev_text:
            boundary_lines.append(f"Previous subtitle: {prev_text}")
        if next_text:
            boundary_lines.append(f"Next subtitle: {next_text}")
        boundary_lines.append(
            "Use these subtitle boundaries to maintain continuity, but stay grounded in the frames."
        )
        parts.append("\n".join(boundary_lines))
    context_items = [str(item).strip() for item in retrieved_context_texts if str(item).strip()]
    if context_items:
        context_lines = [
            "[Relevant Earlier Dialogue]",
            "The following lines are earlier context from the same video. Treat them as weak background reference only.",
        ]
        context_lines.extend(
            f"{idx}. {text}" for idx, text in enumerate(context_items, start=1)
        )
        parts.append("\n".join(context_lines))
    return "\n\n".join(parts)
