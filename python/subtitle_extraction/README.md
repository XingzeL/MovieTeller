# subtitle_extraction

Speech-to-subtitles via **VideoCaptioner** CLI (`videocaptioner transcribe`): subprocess only; parses `.srt` into structured cues.

## Setup

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e python/movieteller_config
python -m pip install -e python/subtitle_extraction
```

Install VideoCaptioner CLI into the same venv (`python -m pip install videocaptioner`) or set `VIDEOCAPTIONER_BIN`.

## CLI

From repo root (loads `config/local.yaml` via movieteller_config):

```bash
source .venv/bin/activate
PYTHONPATH=python/movieteller_config/src:python/subtitle_extraction/src \
  python -m subtitle_extraction --video /path/to/file.mp4 --json
```

## Library

```python
from subtitle_extraction import extract_subtitles, parse_srt_text

result = extract_subtitles(
    "/path/to/video.mp4",
    videocaptioner_bin=None,  # PATH videocaptioner
    output_srt_path="/tmp/out.srt",
    asr="bijian",
    language="auto",
    timeout_sec=600,
)
# result.subtitle_path, result.cues
```

## Configuration

See repository `config/local.yaml.example`: `videocaptioner_bin`, `videocaptioner_asr`, `videocaptioner_language`, `videocaptioner_transcribe_timeout_ms`.
