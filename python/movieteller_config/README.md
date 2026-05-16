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
print(s.ffmpeg_path)
print(s.default_provider(), s.default_model_for_capability("narration"))
```

## Keys

See repository root `.env.example` and comments in `src/movieteller_config/config/default.yaml`.

Recommended capability-first keys:

- `gateway.default_provider`
- `api_providers`
- `api_keys`
- `model_catalog`
- `model_defaults`
- `tts_defaults`
- `video_defaults`

## Tests

```bash
cd python/movieteller_config && pip install -e ".[dev]" && python -m unittest discover -s tests -v
```

Subtitle extraction (VideoCaptioner): `videocaptioner_bin`, `videocaptioner_asr`, `videocaptioner_language`, `videocaptioner_transcribe_timeout_ms` — see repository `config/README.md` and `python/subtitle_extraction/README.md`.
