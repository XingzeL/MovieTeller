# movieteller_logging

Thread-safe structured logging using `logging.handlers.QueueHandler` + `QueueListener`.

- Worker threads enqueue records; a dedicated listener thread writes **JSON Lines** to stderr and/or a file.
- Configure via `movieteller_config` `logging:` block and `configure_async_logging(...)` from the pipeline entrypoint.

See `movieteller_logging.runtime` for the public API.
