"""
需仓库根目录存在 ``example.mp4`` 且系统有 ``ffmpeg``；用于本地验证前 5s 抽帧。

集成用例 ``test_example_mp4_first_5s_narration_api`` 会请求真实多模态 API（计费），
默认 **skip**；需已为 ``gateway.default_provider`` 配置 Key / Base URL，并设置 `model_defaults.narration`（见 movieteller_config）。

CI 无样例视频时会自动 skip，不失败。
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest

from frame_source import FrameSourceOptions
from narration.frames import (
    extract_frames_base64,
    ffprobe_path_for,
    segment_duration_sec,
)
from movieteller_config import load_settings
from movieteller_config.loader import load_flat_dict
from movieteller_config.schema import settings_from_dict


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _load_repo_root_dotenv() -> None:
    """保证无论从哪个 cwd 跑 pytest，都能加载仓库根目录 ``.env``（与手动在项目根执行一致）。"""
    env_file = _repo_root() / ".env"
    if not env_file.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_file, override=False)


def _example_path() -> Path:
    return _repo_root() / "example.mp4"


@pytest.fixture(scope="module")
def example_video() -> Path:
    p = _example_path()
    if not p.is_file():
        pytest.skip(f"missing {_example_path()}")
    if not shutil.which("ffmpeg") and not shutil.which("avconv"):
        pytest.skip("ffmpeg not on PATH")
    return p


def test_first_5_seconds_segment_duration(example_video: Path) -> None:
    s = load_settings()
    ffprobe = ffprobe_path_for(s.ffmpeg_path)
    d = segment_duration_sec(
        str(example_video), 0.0, 5.0, ffprobe_bin=ffprobe
    )
    assert abs(d - 5.0) < 0.05


def test_first_5_seconds_extracts_frames(example_video: Path) -> None:
    s = load_settings()
    duration = 5.0
    frames = extract_frames_base64(
        str(example_video),
        start_sec=0.0,
        end_sec=5.0,
        duration_sec=duration,
        max_frames=min(6, s.max_frames_per_segment),
        ffmpeg_bin=s.ffmpeg_path,
        max_edge_pixels=s.narration_frame_max_edge,
    )
    assert len(frames) >= 1
    assert all(isinstance(x, str) and len(x) > 10 for x in frames)


@pytest.mark.integration
def test_example_mp4_first_5s_narration_api(example_video: Path) -> None:
    """
    调用配置中的 OpenAI 兼容服务，对 ``example.mp4`` 前 5s 生成旁白（英文解说文案）。

    启用条件（缺一不可）：

    - 仓库根目录存在 ``example.mp4``（fixture 已处理）
    - ``RUN_NARRATION_API_TEST=1``（防止误跑扣费）
    - ``movieteller_config`` 能为 ``gateway.default_provider`` 解析出 API Key

    运行示例::

        RUN_NARRATION_API_TEST=1 PYTHONPATH=python/movieteller_config/src:python/narration/src \\
          python3 -m pytest python/narration/tests/test_example_mp4_local.py -v -m integration
    """
    flag = os.environ.get("RUN_NARRATION_API_TEST", "").strip().lower()
    if flag not in ("1", "true", "yes"):
        pytest.skip("set RUN_NARRATION_API_TEST=1 to enable paid API narration test")

    _load_repo_root_dotenv()

    env_path = _repo_root() / ".env"
    try:
        # 与业务代码一致：合并 default.yaml / local.yaml / .env 等后，检查旁白所需 slug 是否配有 Key
        load_settings(require_narration=True)
    except ValueError as e:
        pytest.skip(
            f"{e} — 检查 `{env_path}` 与 gateway.default_provider、model_defaults.narration、API_KEYS_JSON、*_API_KEY；"
            f" Base URL：API_PROVIDERS_JSON / *_BASE_URL。cwd={os.getcwd()}"
        )

    # 复用同一份合并结果，只把「每段最多抽几帧」压到 8，省一点调用费用（不改密钥与其它项）
    flat = load_flat_dict()
    flat["max_frames_per_segment"] = min(int(flat.get("max_frames_per_segment") or 24), 8)
    settings_lite = settings_from_dict(flat)

    from narration import narrate_segment

    narration_options = settings_lite.narration_options()
    frame_source_options = FrameSourceOptions(
        ffmpeg_bin=settings_lite.ffmpeg_path,
        max_frames_per_segment=settings_lite.max_frames_per_segment,
        max_edge_pixels=settings_lite.narration_frame_max_edge,
        pool_miss_uniform_max_frames=settings_lite.pool_miss_uniform_max_frames,
    )

    text = narrate_segment(
        str(example_video),
        0.0,
        5.0,
        options=narration_options,
        frame_source_options=frame_source_options,
        settings=settings_lite,
    )
    assert isinstance(text, str)
    assert len(text.strip()) >= 15
