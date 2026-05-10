# narration_speech

Generate TTS audio for MovieTeller narration text. The current implementation uses
`edge-tts` and is designed to run after `narration_polish`.

## Setup

```bash
source .venv/bin/activate
python -m pip install -e python/movieteller_config -e python/narration -e python/narration_speech
python -m pip install edge-tts
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

Shared settings live in `movieteller_config`:

- `narration_speech_enabled`
- `narration_speech_provider`
- `narration_speech_voice`
- `narration_speech_rate`
- `narration_speech_volume`
- `narration_speech_pitch`
- `narration_speech_boundary`
