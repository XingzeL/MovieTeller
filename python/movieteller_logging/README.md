# movieteller_logging

Thread-safe structured logging using `logging.handlers.QueueHandler` + `QueueListener`.

- Worker threads enqueue records; a dedicated listener thread writes **JSON Lines** to stderr and/or a file.
- Configure via `movieteller_config` `logging:` block and `configure_async_logging(...)` from the pipeline entrypoint.

See `movieteller_logging.runtime` for the public API.

## Event Model

Event names are centralized in `movieteller_logging.events` and should follow:

```text
domain.action.status
```

Use `start`, `done`, `failed`, or `progress` as the final component when possible.

Examples:

```text
workflow.start
workflow.done
workflow.failed
workflow.stage.start
workflow.stage.done
workflow.stage.skipped
workflow.stage.failed
stage.group.start
segment.narration.done
gateway.chat.failed
study_card.done
```

Core fields:

```text
job_id
stage
group_index
segment_index
capability
provider
model
adapter
duration_ms
status
error_type
error_message
error_code
retryable
fatal
retry_count
completed
total
```

Temporary or feature-specific fields must use the `x_` prefix. This keeps the stable schema small while still allowing debugging fields.

Status values should be simple and stable:

```text
ok
error
skipped
warning
```

Do not log API keys, raw prompts, raw subtitles, or large model responses.

Error events should include stable classification fields. Use `classify_error(exc)` and add a layer-specific `fatal` value:

```python
emit_event(
    "gateway.chat.failed",
    status="error",
    fatal=True,
    **classify_error(exc),
)
```

Common `error_code` values include:

```text
provider_500
provider_timeout
provider_rate_limited
provider_auth_failed
provider_not_found
invalid_model_response
artifact_missing
invalid_request
internal_error
```

## Stage registry

Macro stage IDs, JSONL ``stage`` aliases, weights, and labels live in
`movieteller_logging.stage_registry`. CLI progress and `overall_progress` both
read from this module. JSONL ``stage`` ids follow ``movieteller_logging.events.FIXED_WORKFLOW_STAGES``.

## Overall progress (frontend)

Use `overall_progress(progress_from_jsonl(path))` for a single percent + label (no per-segment detail):

```python
from movieteller_logging import overall_progress, progress_from_jsonl

summary = overall_progress(progress_from_jsonl("artifacts/job-1/logs/workflow.jsonl"))
# {"status": "running", "percent": 42, "label": "生成旁白", "currentStage": "narration_group"}
```

CLI:

```bash
PYTHONPATH=python/movieteller_logging/src python -m movieteller_logging path/to/workflow.jsonl
```

## Progress Aggregation

Use `progress_from_jsonl(...)` to turn raw workflow events into a compact product-facing status object:

```python
from movieteller_logging import progress_from_jsonl

progress = progress_from_jsonl("artifacts/job-1/logs/workflow.jsonl")
print(progress.to_dict())
```

The aggregator is intentionally read-only and depends only on JSONL events, so API/job code can use it without importing pipeline internals.

## Event Reading

Use `tail_jsonl_events(...)` for API-style incremental polling:

```python
from movieteller_logging import tail_jsonl_events

page = tail_jsonl_events(
    "artifacts/job-1/logs/workflow.jsonl",
    after=0,
    limit=100,
    level="ERROR",
)
return page.to_dict()
```

The returned `next_offset` is a physical line offset. Store it client-side to request only new events on the next poll.
