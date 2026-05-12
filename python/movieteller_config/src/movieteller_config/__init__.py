"""MovieTeller shared configuration (YAML + environment variables)."""

from movieteller_config.loader import clear_settings_cache, load_flat_dict, load_settings
from movieteller_config.schema import (
    FramePoolBuildOptions,
    NarrationOptions,
    NarrationPolishOptions,
    NarrationSpeechOptions,
    NarrationVideoOptions,
    Settings,
    SubtitleExtractionOptions,
    SubtitleContextBuildOptions,
    SubtitleContextRetrieveOptions,
)

__all__ = [
    "Settings",
    "SubtitleExtractionOptions",
    "FramePoolBuildOptions",
    "NarrationOptions",
    "NarrationPolishOptions",
    "NarrationSpeechOptions",
    "NarrationVideoOptions",
    "SubtitleContextBuildOptions",
    "SubtitleContextRetrieveOptions",
    "load_settings",
    "load_flat_dict",
    "clear_settings_cache",
]
