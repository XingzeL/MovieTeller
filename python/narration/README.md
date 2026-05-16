# Narration（视频片段旁白）

独立 Python 包：对本地视频按 **时间区间** 用 ffmpeg 抽帧（`-ss` / `-t`），再通过 `model_gateway` 的 narration capability 生成旁白。默认路由由 `movieteller_config` 中的 `gateway.default_provider`、`model_defaults.narration`、`api_providers`、`api_keys` 决定。

## 安装

在仓库根目录执行（需先装配置包）：

```bash
source .venv/bin/activate
python -m pip install -e ./python/movieteller_config
python -m pip install -e "./python/narration[dev]"
```

依赖：`openai`、已安装的 `movieteller-config`。系统需可用 **ffmpeg**（及同目录下的 **ffprobe**，或由 `ffmpeg` 路径推导）。

## 环境变量

与 MovieTeller 共用约定，见仓库根目录 [.env.example](../../.env.example)。当前推荐配置：

- `GATEWAY_DEFAULT_PROVIDER`
- `API_PROVIDERS_JSON`
- `API_KEYS_JSON`
- `MODEL_DEFAULTS_JSON` 中的 `narration`
- `MODEL_CATALOG_JSON`（模型白名单）
- `MAX_FRAMES_PER_SEGMENT`
- `NARRATION_FRAME_MAX_EDGE`（抽帧后缩放：画面装进「边长为该值的正方形」内，横竖屏通用）
- `FFMPEG_PATH`
- `DEFAULT_PROMPT_STYLE`

## 用法

### Python API

```python
from narration import narrate_segment

text = narrate_segment("/path/to/clip.mp4", 12.5, 45.0)
```

整段文件（已是短片段）可不传起止时间：

```python
text = narrate_segment("/path/to/short.mp4")
```

### CLI

```bash
python -m narration --video /path/to.mp4 --start 12.5 --end 45 --json
```

stdout 为 JSON：`{"text": "...", "duration_sec": 32.5}`。

## 测试

```bash
cd python/narration
PYTHONPATH=src:../movieteller_config/src pytest tests -v
```

（若已 `pip install -e` 两条包，可直接在该目录 `pytest`。）

仓库根目录放置 ``example.mp4`` 时，会多跑本地集成用例 ``tests/test_example_mp4_local.py``（校验 **0s–5s** 片段时长与抽帧）。

手动冒烟（同样针对根目录 ``example.mp4`` 前 5 秒，默认只抽帧、不调模型）::

```bash
PYTHONPATH=python/movieteller_config/src:python/narration/src \\
  python python/manual_tests/narration_example_first_5s_smoke.py
python python/manual_tests/narration_example_first_5s_smoke.py --json
python python/manual_tests/narration_example_first_5s_smoke.py --narrate   # 需 API
```

若仍 **skipped**：请确认 `gateway.default_provider`（或 `GATEWAY_DEFAULT_PROVIDER`）对应的 key/base URL 已配置，且 `model_defaults.narration` 指向可用模型。

```bash
RUN_NARRATION_API_TEST=1 PYTHONPATH=python/movieteller_config/src:python/narration/src \\
  python -m pytest python/narration/tests/test_example_mp4_local.py -v -m integration
```
