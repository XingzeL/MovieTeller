# narration_video

Mix synthesized narration audio segments back into a source video with ffmpeg.

## Setup

```bash
source .venv/bin/activate
python -m pip install -e python/movieteller_config -e python/narration -e python/narration_video
```

## CLI

```bash
source .venv/bin/activate
python -m narration_video \
  --video subtitle_example.mp4 \
  --output subtitle_example.narrated.mp4 \
  --segment 0.5 3.5 /tmp/narration.mp3 \
  --json
```

`--segment START_SEC END_SEC AUDIO_PATH` may be repeated multiple times. The module
will delay each narration track to its segment start time, lower the original video
audio volume, and mix everything into a new output video.

## Config

Shared settings live in `movieteller_config`:

- `narration_video_background_audio_volume`
- `narration_video_speech_audio_volume`
