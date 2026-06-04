# movie_pipeline

Orchestrate the end-to-end MovieTeller flow:

- analyze subtitle gaps
- optionally build and retrieve subtitle context
- generate narration
- optionally polish narration
- optionally synthesize speech
- optionally embed narration audio back into video

This package owns pipeline control flow. Domain modules stay focused on their
single responsibilities.

## Setup

```bash
source .venv/bin/activate
python -m pip install -e python/movieteller_config
python -m pip install -e python/pipeline_types
python -m pip install -e python/subtitle_analysis
python -m pip install -e python/subtitle_context
python -m pip install -e python/narration
python -m pip install -e python/narration_polish
python -m pip install -e python/narration_speech
python -m pip install -e python/narration_video
python -m pip install -e python/movie_pipeline
```

## CLI

```bash
source .venv/bin/activate
python -m movie_pipeline \
  --srt subtitle_example.extracted.srt \
  --video subtitle_example.mp4 \
  --min-gap-sec 1.5 \
  --subtitle-guard-sec 0.25 \
  --build-subtitle-context \
  --polish \
  --json
```

## Responsibilities

- `python -m subtitle_analysis`: analysis only
- `python -m movie_pipeline`: full orchestration entry

## Python API

Use `run_full_workflow(resolved_context=...)` for the end-to-end workflow.

Use `run_pipeline_ctx(..., ctx=RunContext(settings=..., pipeline=...))` only when
you intentionally want the lower-level narration pipeline entry and are supplying
the subtitle/frame artifacts yourself.

See [docs/planning/archive/runtime-config-architecture.md](../../docs/planning/archive/runtime-config-architecture.md)
for diagrams and payload helpers.
