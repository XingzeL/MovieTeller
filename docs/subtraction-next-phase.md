# Next phase: subtraction (shrink degrees of freedom)

Strategic goal: one truth source for config, one pipeline entry, one capability
routing style, one contract per stage artifact — **delete compatibility shims**
instead of wrapping them.

Suggested implementation order (high-level):

1. **Pipeline entry** — only `RunContext` + `run_pipeline_ctx` (done: `run_pipeline`
   removed).
2. Remove `provider_slug` from feature options (`NarrationPolishOptions`,
   `NarrationSpeechOptions`) — **done**; provider comes from `Settings` /
   `provider_for_capability` / gateway `meta` only.
3. Config layer: drop legacy `openai_*` top-level fields, legacy env key aliases
   (e.g. non-``*_API_KEY`` names), `require_openai()`, and implicit ``default_provider()``
   fallbacks — **done** for Python ``movieteller_config`` / ``model_gateway`` and Node
   ``server/src/config``; use ``api_keys`` / ``api_providers`` (Python) or ``api_keys`` /
   ``api_base_urls`` (server) plus standard ``PREFIX_*_API_KEY`` / ``PREFIX_*_BASE_URL`` env only.
4. Split stage JSON schemas (`PipelineTextPayload` vs speech vs render payloads) — **done** in
   [`payload_schema.py`](../python/movie_pipeline/src/movie_pipeline/payload_schema.py)
   (`PipelineSpeechPayload`, `PipelineRenderPayload`, `RenderedVideoPayload`, stricter parsers).
5. Refactor `run_full_workflow` into a pure stage orchestrator — **done** via
   [`workflow_stages.py`](../python/movie_pipeline/src/movie_pipeline/workflow_stages.py)
   and [`ArtifactPaths`](../python/movie_pipeline/src/movie_pipeline/types.py).
6. Remove “helpful” fallbacks — **partially done**: `FrameSourceOptions.allow_uniform_fallback`
   defaults to `False` (callers that need pool-miss uniform sampling pass `True` explicitly);
   `run_pipeline_ctx` no longer invents `speech_output_dir` / `embed_output_path` (CLI and
   full workflow set them explicitly).

7. Split workflow types (`FullWorkflowPlan`, `PipelineRuntimeOptions`, `ArtifactPaths`) — **done**
   in [`types.py`](../python/movie_pipeline/src/movie_pipeline/types.py).

8. Move option factories off `Settings` — **done** via
   [`runtime_options.py`](../python/movieteller_config/src/movieteller_config/runtime_options.py)
   (`build_*` helpers); `Settings` methods delegate for backward compatibility.

See also:

- [runtime-config-dual-pass-inventory.md](runtime-config-dual-pass-inventory.md)
- [runtime-config-architecture.md](runtime-config-architecture.md)
