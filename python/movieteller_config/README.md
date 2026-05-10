# movieteller-config

Python package: merged configuration from packaged `config/default.yaml`, optional `MOVIE_TELLER_CONFIG` / repo `config/local.yaml`, repo-root **`.env`** (via `python-dotenv`, does not override variables already set in the shell), and **environment variables** (highest priority among merged layers).

## Install (editable, from repo root)

```bash
pip install -e ./python/movieteller_config
```

## Usage

```python
from movieteller_config import load_settings

s = load_settings()
print(s.narration_image_model, s.ffmpeg_path)

# Before calling OpenAI:
key = s.require_openai()
```

## Keys

See repository root `.env.example` and comments in `src/movieteller_config/config/default.yaml`.

Narration polishing keys used before future TTS:

- `narration_provider_models`
- `narration_provider_model_catalog`
- `narration_model`
- `narration_model_index`
- `narration_polish_enabled`
- `narration_polish_provider`
- `narration_polish_model`
- `narration_polish_model_index`
- `narration_polish_provider_models`
- `narration_polish_provider_model_catalog`
- `narration_polish_target_wpm`
- `narration_polish_cefr_level`
- `narration_polish_strength`
- `narration_polish_safety_margin_sec`
- `narration_speech_enabled`
- `narration_speech_provider`
- `narration_speech_voice`
- `narration_speech_rate`
- `narration_speech_volume`
- `narration_speech_pitch`
- `narration_speech_boundary`
- `narration_video_background_audio_volume`
- `narration_video_speech_audio_volume`

## Tests

```bash
cd python/movieteller_config && pip install -e ".[dev]" && python -m unittest discover -s tests -v
```

Subtitle extraction (VideoCaptioner): `videocaptioner_bin`, `videocaptioner_asr`, `videocaptioner_language`, `videocaptioner_transcribe_timeout_ms` — see repository `config/README.md` and `python/subtitle_extraction/README.md`.
