from __future__ import annotations

from pathlib import Path


class JobCanceledError(RuntimeError):
    """Raised when a job cancel.flag is present."""


def is_job_canceled(output_root: str | Path) -> bool:
    flag = Path(output_root).resolve() / "cancel.flag"
    return flag.is_file()


def job_root_from_speech_output_dir(speech_output_dir: str | Path) -> Path | None:
    speech_dir = Path(speech_output_dir).resolve()
    if speech_dir.name == "audio" and speech_dir.parent.name == "speech":
        return speech_dir.parent.parent
    return None


def ensure_not_canceled(*, speech_output_dir: str | None) -> None:
    if not speech_output_dir:
        return
    job_root = job_root_from_speech_output_dir(speech_output_dir)
    if job_root is not None and is_job_canceled(job_root):
        raise JobCanceledError(f"job canceled: {job_root}")


def ensure_not_canceled_for_output_root(output_root: str | Path) -> None:
    root = Path(output_root).resolve()
    if is_job_canceled(root):
        raise JobCanceledError(f"job canceled: {root}")
