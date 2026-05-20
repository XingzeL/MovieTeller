# Runtime config: dual-pass inventory (baseline)

Orchestration sites that historically passed **both** `Settings` (or resolved
`pipeline_settings`) **and** `MoviePipelineOptions` into the same pipeline hop
are listed here for refactor tracking. Prefer **`RunContext`** +
**`run_pipeline_ctx`** for new call sites.

## Primary boundaries

| Module | Symbol | Notes |
|--------|--------|--------|
| [python/movie_pipeline/src/movie_pipeline/workflow_stages.py](../python/movie_pipeline/src/movie_pipeline/workflow_stages.py) | `stage_*` | Five-stage glue used by `run_full_workflow` (fixed paths + resume). |
| [python/movie_pipeline/src/movie_pipeline/pipeline.py](../python/movie_pipeline/src/movie_pipeline/pipeline.py) | `narrate_analysis_candidates` | Takes `ctx: RunContext` only; options live on `ctx.pipeline`. |
| [python/movie_pipeline/src/movie_pipeline/full_workflow.py](../python/movie_pipeline/src/movie_pipeline/full_workflow.py) | `run_full_workflow` | Orchestrates `workflow_stages` then `run_pipeline_ctx` (optional injectable narrators). |
| [python/movie_pipeline/src/movie_pipeline/cli.py](../python/movie_pipeline/src/movie_pipeline/cli.py) | `main` | Uses `RunContext` + `run_pipeline_ctx`. |

## Removed dual-entry pattern

The old `run_pipeline(settings=..., pipeline_options=...)` wrapper has been
removed; call sites must build a `RunContext` and invoke `run_pipeline_ctx` only.

See also: [runtime-config-architecture.md](runtime-config-architecture.md).
