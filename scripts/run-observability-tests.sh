#!/usr/bin/env bash
# Step 0 baseline + observability contract tests (B3).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

PYTHON="${MOVIE_TELLER_PYTHON:-$ROOT/.venv/bin/python3}"
if [[ ! -x "$PYTHON" ]]; then
  PYTHON="${MOVIE_TELLER_PYTHON:-python3}"
fi

export PYTHONPATH="${ROOT}/python/movieteller_config/src:${ROOT}/python/movieteller_logging/src:${ROOT}/python/pipeline_types/src:${ROOT}/python/media_utils/src:${ROOT}/python/model_gateway/src:${ROOT}/python/subtitle_extraction/src:${ROOT}/python/subtitle_analysis/src:${ROOT}/python/frame_source/src:${ROOT}/python/narration/src:${ROOT}/python/narration_polish/src:${ROOT}/python/narration_speech/src:${ROOT}/python/narration_video/src:${ROOT}/python/pipeline_transcript/src:${ROOT}/python/rerank/src:${ROOT}/python/subtitle_context/src:${ROOT}/python/video_frame_pool/src:${ROOT}/python/movie_pipeline/src${PYTHONPATH:+:$PYTHONPATH}"

echo "== observability pytest =="
"$PYTHON" -m pytest \
  python/movieteller_logging/tests/test_progress.py \
  python/movieteller_logging/tests/test_stage_registry.py \
  python/movieteller_logging/tests/test_overall_progress.py \
  python/movie_pipeline/tests/test_stage_observability.py \
  python/movie_pipeline/tests/test_workflow_stage_observability_contract.py \
  -q

echo "== B4: no legacy macro stage emits in production Python =="
LEGACY_HITS="$(
  rg -n 'emit_event\([^)]*\.(SUBTITLE_EXTRACTION|FRAME_POOL|SUBTITLE_CONTEXT|VIDEO_PACKAGE|WORKFLOW_EXPORT)_(START|DONE|FAILED)' \
    python/movie_pipeline/src python/movieteller_logging/src 2>/dev/null || true
)"
if [[ -n "$LEGACY_HITS" ]]; then
  echo "$LEGACY_HITS" >&2
  echo "legacy macro emit_event calls must not exist in src" >&2
  exit 1
fi

LEGACY_EVENT_LITERALS="$(
  rg -n '"subtitle_extraction\.(start|done|failed)"|"frame_pool\.(start|done|failed)"|"video_package\.|"workflow_export\.' \
    python/movie_pipeline/src python/movieteller_logging/src 2>/dev/null || true
)"
if [[ -n "$LEGACY_EVENT_LITERALS" ]]; then
  echo "$LEGACY_EVENT_LITERALS" >&2
  echo "legacy macro event string literals must not exist in src" >&2
  exit 1
fi

echo "observability checks passed"
