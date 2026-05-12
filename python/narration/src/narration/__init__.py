"""Video segment narration: ffmpeg frames + multimodal LLM."""

from narration.narrate import narrate_from_frames, narrate_segment, narrate_segment_with_duration

__all__ = ["narrate_from_frames", "narrate_segment", "narrate_segment_with_duration"]
