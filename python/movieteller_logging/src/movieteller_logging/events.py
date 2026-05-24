from __future__ import annotations

"""Structured event names used by MovieTeller logging.

Event names follow ``domain.action.status`` where the final component is usually
``start``, ``done``, ``failed``, ``progress``, or another concrete state.
"""

WORKFLOW_LOGGING_CONFIGURED = "workflow.logging.configured"
WORKFLOW_START = "workflow.start"
WORKFLOW_DONE = "workflow.done"
WORKFLOW_FAILED = "workflow.failed"

SUBTITLE_EXTRACTION_START = "subtitle_extraction.start"
SUBTITLE_EXTRACTION_DONE = "subtitle_extraction.done"
SUBTITLE_EXTRACTION_FAILED = "subtitle_extraction.failed"
FRAME_POOL_START = "frame_pool.start"
FRAME_POOL_DONE = "frame_pool.done"
FRAME_POOL_FAILED = "frame_pool.failed"
SUBTITLE_CONTEXT_START = "subtitle_context.start"
SUBTITLE_CONTEXT_DONE = "subtitle_context.done"
SUBTITLE_CONTEXT_FAILED = "subtitle_context.failed"
VIDEO_PACKAGE_START = "video_package.start"
VIDEO_PACKAGE_DONE = "video_package.done"
VIDEO_PACKAGE_FAILED = "video_package.failed"
WORKFLOW_EXPORT_START = "workflow_export.start"
WORKFLOW_EXPORT_DONE = "workflow_export.done"
WORKFLOW_EXPORT_FAILED = "workflow_export.failed"

STAGE_GROUP_START = "stage.group.start"
STAGE_GROUP_DONE = "stage.group.done"
STAGE_GROUP_FAILED = "stage.group.failed"
STAGE_GROUP_PROGRESS = "stage.group.progress"

SEGMENT_START = "segment.start"
SEGMENT_NARRATION_DONE = "segment.narration.done"
SEGMENT_POLISH_DONE = "segment.polish.done"
SEGMENT_STUDY_DONE = "segment.study.done"
SEGMENT_TTS_DONE = "segment.tts.done"
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
