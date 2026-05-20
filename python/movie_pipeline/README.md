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

Use `run_pipeline_ctx(..., ctx=RunContext(settings=..., pipeline=...))` — this is
the only supported pipeline execution entry; assemble a `RunContext` once and pass
it through.

See [docs/runtime-config-architecture.md](../docs/runtime-config-architecture.md)
for diagrams and payload helpers.

`analyze_and_narrate(...)` is compatibility-only for older call sites and should not
be used for new integration code.
