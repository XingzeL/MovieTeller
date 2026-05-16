# narration_speech

Generate TTS audio for MovieTeller narration text. The runtime now routes speech
through `model_gateway` TTS capability by default. It can target OpenAI-compatible
`audio.speech` backends exposed behind your configured gateway, and still keeps
`edge_tts` as a compatibility path.

## Setup

```bash
source .venv/bin/activate
python -m pip install -e python/movieteller_config -e python/narration -e python/narration_speech
```

## CLI

```bash
source .venv/bin/activate
python -m narration_speech \
  --text "A wizard walks across green hills." \
  --duration-sec 3.0 \
  --output /tmp/narration.mp3 \
  --json
```

If the generated speech slightly exceeds the target duration, the module will use
ffmpeg `atempo` to speed it up enough to fit.

## Config

Recommended shared settings in `movieteller_config`:

- `narration_tts_enabled`
- `gateway.default_provider`
- `api_providers`
- `api_keys`
- `model_defaults.tts`
- `tts_defaults.voice`
- `tts_defaults.rate`
- `tts_defaults.volume`
- `tts_defaults.pitch`
- `tts_defaults.boundary`
