# subtitle_context

Subtitle semantic context index for MovieTeller.

Phase 1 scope:

- chunk subtitle cues
- embed chunk text
- store a local per-video index
- retrieve only historical chunks before a target segment start time
- rerank retrieved history with generic MMR to reduce near-duplicate context

No standalone vector database is required in phase 1.
