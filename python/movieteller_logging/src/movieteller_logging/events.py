from __future__ import annotations

"""Structured event names used by MovieTeller logging.

Event names follow ``domain.action.status`` where the final component is usually
``start``, ``done``, ``failed``, ``progress``, or another concrete state.
"""

WORKFLOW_LOGGING_CONFIGURED = "workflow.logging.configured"
WORKFLOW_START = "workflow.start"
WORKFLOW_DONE = "workflow.done"
WORKFLOW_FAILED = "workflow.failed"

WORKFLOW_STAGE_START = "workflow.stage.start"
WORKFLOW_STAGE_DONE = "workflow.stage.done"
WORKFLOW_STAGE_FAILED = "workflow.stage.failed"
WORKFLOW_STAGE_SKIPPED = "workflow.stage.skipped"

FIXED_WORKFLOW_STAGES = (
    "ingest",
    "subtitle_extraction",
    "subtitle_analysis",
    "frame_pool",
    "subtitle_context",
    "narration",
    "polish",
    "study_enrichment",
    "tts",
    "subtitle_merge",
    "render",
    "export",
)

WORKFLOW_STAGE_EVENTS = (
    WORKFLOW_STAGE_START,
    WORKFLOW_STAGE_DONE,
    WORKFLOW_STAGE_FAILED,
    WORKFLOW_STAGE_SKIPPED,
)

STAGE_GROUP_START = "stage.group.start"
STAGE_GROUP_DONE = "stage.group.done"
STAGE_GROUP_FAILED = "stage.group.failed"
STAGE_GROUP_PROGRESS = "stage.group.progress"

SEGMENT_START = "segment.start"
SEGMENT_NARRATION_DONE = "segment.narration.done"
SEGMENT_POLISH_DONE = "segment.polish.done"
SEGMENT_STUDY_DONE = "segment.study.done"
SEGMENT_TTS_START = "segment.tts.start"
SEGMENT_TTS_DONE = "segment.tts.done"
SEGMENT_TTS_FAILED = "segment.tts.failed"
SEGMENT_DONE = "segment.done"
SEGMENT_FAILED = "segment.failed"

NARRATION_FRAMES_SELECTED = "narration.frames.selected"

GATEWAY_CHAT_PREPARE = "gateway.chat.prepare"
GATEWAY_CHAT_START = "gateway.chat.start"
GATEWAY_CHAT_DONE = "gateway.chat.done"
GATEWAY_CHAT_FAILED = "gateway.chat.failed"
GATEWAY_EMBEDDING_START = "gateway.embedding.start"
GATEWAY_EMBEDDING_DONE = "gateway.embedding.done"
GATEWAY_EMBEDDING_FAILED = "gateway.embedding.failed"
GATEWAY_SPEECH_START = "gateway.speech.start"
GATEWAY_SPEECH_DONE = "gateway.speech.done"
GATEWAY_SPEECH_FAILED = "gateway.speech.failed"

STUDY_CARD_START = "study_card.start"
STUDY_CARD_DONE = "study_card.done"
STUDY_CARD_FAILED = "study_card.failed"
STUDY_CARD_EXPORT_FAILED = "study_card.export.failed"
