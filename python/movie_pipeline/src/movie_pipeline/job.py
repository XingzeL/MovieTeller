from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

JobStatus = Literal["queued", "running", "succeeded", "failed", "canceled"]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


@dataclass(frozen=True)
class JobRecord:
    job_id: str
    status: JobStatus
    input_video_path: str
    output_root: str
    user_id: str | None = None
    current_stage: str | None = None
    progress: dict[str, Any] = field(default_factory=dict)
    error: dict[str, Any] | None = None
    artifacts: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class JobPaths:
    job_id: str
    root: str
    input_dir: str
    logs_dir: str
    subtitles_dir: str
    analysis_dir: str
    frame_pool_dir: str
    narration_dir: str
    speech_dir: str
    speech_audio_dir: str
    render_dir: str
    study_cards_dir: str
    workflow_json_path: str
    workflow_log_path: str
    extracted_srt_path: str
    final_subtitled_srt_path: str
    subtitle_analysis_json_path: str
    frame_pool_manifest_path: str
    narration_json_path: str
    speech_video_json_path: str
    rendered_video_path: str
    study_cards_html_path: str

    @staticmethod
    def resolve(*, jobs_root: str | Path, job_id: str) -> JobPaths:
        clean_job_id = _safe_job_id(job_id)
        root = Path(jobs_root).resolve() / clean_job_id
        input_dir = root / "input"
        logs_dir = root / "logs"
        subtitles_dir = root / "subtitles"
        analysis_dir = root / "analysis"
        frame_pool_dir = root / "frame_pool"
        narration_dir = root / "narration"
        speech_dir = root / "speech"
        speech_audio_dir = speech_dir / "audio"
        render_dir = root / "render"
        study_cards_dir = root / "study_cards"
        return JobPaths(
            job_id=clean_job_id,
            root=str(root),
            input_dir=str(input_dir),
            logs_dir=str(logs_dir),
            subtitles_dir=str(subtitles_dir),
            analysis_dir=str(analysis_dir),
            frame_pool_dir=str(frame_pool_dir),
            narration_dir=str(narration_dir),
            speech_dir=str(speech_dir),
            speech_audio_dir=str(speech_audio_dir),
            render_dir=str(render_dir),
            study_cards_dir=str(study_cards_dir),
            workflow_json_path=str(root / "workflow.json"),
            workflow_log_path=str(logs_dir / "workflow.jsonl"),
            extracted_srt_path=str(subtitles_dir / "extracted.srt"),
            final_subtitled_srt_path=str(subtitles_dir / "final.subtitled.srt"),
            subtitle_analysis_json_path=str(analysis_dir / "subtitle_analysis.json"),
            frame_pool_manifest_path=str(frame_pool_dir / "manifest.jsonl"),
            narration_json_path=str(narration_dir / "narration.json"),
            speech_video_json_path=str(speech_dir / "speech_video.json"),
            rendered_video_path=str(render_dir / "narrated.mp4"),
            study_cards_html_path=str(study_cards_dir / "study_cards.html"),
        )

    def ensure_dirs(self) -> None:
        for path in (
            self.input_dir,
            self.logs_dir,
            self.subtitles_dir,
            self.analysis_dir,
            self.frame_pool_dir,
            self.narration_dir,
            self.speech_audio_dir,
            self.render_dir,
            self.study_cards_dir,
        ):
            Path(path).mkdir(parents=True, exist_ok=True)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class JobStore:
    paths: JobPaths

    @staticmethod
    def resolve(*, jobs_root: str | Path, job_id: str) -> JobStore:
        return JobStore(paths=JobPaths.resolve(jobs_root=jobs_root, job_id=job_id))

    def ensure_dirs(self) -> None:
        self.paths.ensure_dirs()

    def write(self, record: JobRecord) -> JobRecord:
        write_job_record(record, self.paths.workflow_json_path)
        return record

    def read(self) -> JobRecord:
        return read_job_record(self.paths.workflow_json_path)

    def write_initial(
        self,
        *,
        status: JobStatus,
        input_video_path: str | Path,
        user_id: str | None = None,
        current_stage: str | None = None,
    ) -> JobRecord:
        now = utc_now_iso()
        return self.write(
            JobRecord(
                job_id=self.paths.job_id,
                status=status,
                input_video_path=str(input_video_path),
                output_root=self.paths.root,
                user_id=user_id,
                current_stage=current_stage,
                created_at=now,
                updated_at=now,
            )
        )


@dataclass(frozen=True)
class WorkflowArtifacts:
    video_path: str
    srt_path: str
    frame_pool_manifest: str | None
    subtitle_context_index_dir: str | None
    output_root: str
    text_json_path: str | None = None
    speech_json_path: str | None = None
    render_json_path: str | None = None
    final_srt_path: str | None = None
    study_cards_html_path: str | None = None
    study_cards_html_error: str | None = None

    def to_payload_dict(self) -> dict[str, Any]:
        return {
            "videoPath": self.video_path,
            "srtPath": self.srt_path,
            "framePoolManifest": self.frame_pool_manifest,
            "subtitleContextIndexDir": self.subtitle_context_index_dir,
            "outputRoot": self.output_root,
            "textJsonPath": self.text_json_path,
            "speechJsonPath": self.speech_json_path,
            "renderJsonPath": self.render_json_path,
            "finalSrtPath": self.final_srt_path,
            "studyCardsHtmlPath": self.study_cards_html_path,
            "studyCardsHtmlError": self.study_cards_html_error,
        }


def workflow_artifacts_from_payload(data: dict[str, Any]) -> WorkflowArtifacts:
    return WorkflowArtifacts(
        video_path=str(data["videoPath"]),
        srt_path=str(data["srtPath"]),
        frame_pool_manifest=_optional_str(data.get("framePoolManifest")),
        subtitle_context_index_dir=_optional_str(data.get("subtitleContextIndexDir")),
        output_root=str(data["outputRoot"]),
        text_json_path=_optional_str(data.get("textJsonPath")),
        speech_json_path=_optional_str(data.get("speechJsonPath")),
        render_json_path=_optional_str(data.get("renderJsonPath")),
        final_srt_path=_optional_str(data.get("finalSrtPath")),
        study_cards_html_path=_optional_str(data.get("studyCardsHtmlPath")),
        study_cards_html_error=_optional_str(data.get("studyCardsHtmlError")),
    )


def write_job_record(record: JobRecord, path: str | Path) -> str:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(record.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return str(out)


def read_job_record(path: str | Path) -> JobRecord:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("job record JSON must be an object")
    return job_record_from_dict(data)


def job_record_from_dict(data: dict[str, Any]) -> JobRecord:
    return JobRecord(
        job_id=str(data["job_id"]),
        status=_coerce_status(data["status"]),
        input_video_path=str(data["input_video_path"]),
        output_root=str(data["output_root"]),
        user_id=_optional_str(data.get("user_id")),
        current_stage=_optional_str(data.get("current_stage")),
        progress=_dict_or_empty(data.get("progress")),
        error=_dict_or_none(data.get("error")),
        artifacts=_dict_or_empty(data.get("artifacts")),
        created_at=str(data.get("created_at") or utc_now_iso()),
        updated_at=str(data.get("updated_at") or utc_now_iso()),
    )


def _coerce_status(value: Any) -> JobStatus:
    text = str(value).strip()
    allowed = {"queued", "running", "succeeded", "failed", "canceled"}
    if text not in allowed:
        raise ValueError(f"unsupported job status: {text}")
    return text  # type: ignore[return-value]


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _dict_or_empty(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _dict_or_none(value: Any) -> dict[str, Any] | None:
    return dict(value) if isinstance(value, dict) else None


def _safe_job_id(job_id: str) -> str:
    text = str(job_id).strip()
    if not text:
        raise ValueError("job_id is required")
    if text in {".", ".."} or "/" in text or "\\" in text:
        raise ValueError(f"unsafe job_id: {job_id}")
    return text
