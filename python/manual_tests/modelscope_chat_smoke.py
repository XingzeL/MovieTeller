#!/usr/bin/env python3
"""
手动冒烟：用与项目相同的 ``movieteller_config.load_settings()`` 读配置，
请求 ModelScope OpenAI 兼容 Chat Completions（slug: ``modelscope``）。

运行前（仓库根目录）::

    pip install -e python/movieteller_config

执行::

    PYTHONPATH=python/movieteller_config/src python3 python/manual_tests/modelscope_chat_smoke.py

或在任意目录，只要 cwd 能命中仓库 ``config/local.yaml`` / 根目录 ``.env``（与正式代码一致）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def _ensure_movieteller_config_path() -> None:
    repo_root = Path(__file__).resolve().parents[2]
    src = repo_root / "python" / "movieteller_config" / "src"
    if src.is_dir():
        sys.path.insert(0, str(src))


_ensure_movieteller_config_path()

from movieteller_config.loader import load_settings  # noqa: E402


def _chat_completions_url(base: str) -> str:
    """支持 ``.../v1``、``.../v1/chat/completions`` 或仅 host。"""
    b = base.strip().rstrip("/")
    if not b:
        raise ValueError("modelscope api_base_urls 为空")
    if b.endswith("/chat/completions"):
        return b
    if b.endswith("/v1"):
        return f"{b}/chat/completions"
    return f"{b}/v1/chat/completions"


def main() -> int:
    s = load_settings()
    key = s.require_api_key("modelscope")
    raw_base = s.get_api_base_url("modelscope")
    if not raw_base:
        print(
            "错误: 未配置 modelscope 的 Base URL（api_base_urls.modelscope 或 MODELSCOPE_BASE_URL / API_BASE_URLS_JSON）。",
            file=sys.stderr,
        )
        return 1
    model = s.model_for_provider("modelscope")
    url = _chat_completions_url(raw_base)

    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": "告诉我你如何进行视频理解？"},
        ],
        "max_tokens": 256,
    }
    data = json.dumps(body).encode("utf-8")
    req = Request(
        url,
        data=data,
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    print(f"POST {url}")
    print(f"model={model}")
    try:
        with urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
    except HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        print(f"HTTP {e.code}: {err_body}", file=sys.stderr)
        return 1
    except URLError as e:
        print(f"请求失败: {e.reason}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        print(raw)
        return 0

    # OpenAI 兼容：choices[0].message.content
    try:
        content = payload["choices"][0]["message"]["content"]
        print("--- 模型回复 ---")
        print(content)
    except (KeyError, IndexError):
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
