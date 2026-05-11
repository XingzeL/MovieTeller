# video_frame_pool

Stage-1 frame-pool preprocessing for MovieTeller.

Build a minimal frame pool from:

- full-video shot detection
- subtitle overlap tagging
- non-dialogue shot sampling
- PNG export
- `manifest.jsonl` / `shots.json`

This package is intentionally minimal in phase 1:

- no CLIP embeddings yet
- no dedupe yet
- no MMR yet

## CLI

```bash
source .venv/bin/activate
PYTHONPATH=python/movieteller_config/src:python/subtitle_extraction/src:python/video_frame_pool/src \
  python -m video_frame_pool \
    --video /path/to/video.mp4 \
    --srt /path/to/video.extracted.srt \
    --output-dir /path/to/video.frame_pool \
    --json
```
