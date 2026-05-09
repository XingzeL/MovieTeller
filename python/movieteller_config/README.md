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

## Tests

```bash
cd python/movieteller_config && pip install -e ".[dev]" && python -m unittest discover -s tests -v
```
