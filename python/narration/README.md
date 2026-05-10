# Narration（视频片段旁白）

独立 Python 包：对本地视频按 **时间区间** 用 ffmpeg 抽帧（`-ss` / `-t`），再通过 **OpenAI 兼容** 的多模态 Chat API（`openai` Python 包）生成旁白。具体调用哪家由 **`narration_provider`**（slug）决定，密钥与 Base URL 与 MovieTeller 其它模块一样来自 **`movieteller_config`**（``api_keys`` / ``api_base_urls`` / ``narration_provider_models`` / ``narration_provider_model_catalog``）。

## 安装

在仓库根目录执行（需先装配置包）：

```bash
source .venv/bin/activate
python -m pip install -e ./python/movieteller_config
python -m pip install -e "./python/narration[dev]"
```

依赖：`openai`、已安装的 `movieteller-config`。系统需可用 **ffmpeg**（及同目录下的 **ffprobe**，或由 `ffmpeg` 路径推导）。

## 环境变量

与 MovieTeller 共用约定，见仓库根目录 [.env.example](../../.env.example)。常用项：

- **`NARRATION_PROVIDER`**：旁白使用的 **provider slug**（如 `openai`、`modelscope`），须与 ``API_KEYS_JSON`` / ``*_API_KEY`` 中的 slug 一致。
- `API_KEYS_JSON`、`API_BASE_URLS_JSON`
- `NARRATION_PROVIDER_MODELS_JSON`、`NARRATION_PROVIDER_MODEL_CATALOG_JSON`（旁白专用模型池）
- **`NARRATION_MODEL`** / **`NARRATION_MODEL_INDEX`**：覆盖当前 `narration_provider` 使用的模型（见 movieteller_config；也可用 ``narrate_segment(..., image_model=...)``）
- `NARRATION_IMAGE_MODEL` / `IMAGE_MODEL`（未命中 narration 专用模型池时的回退）
- `OPENAI_API_KEY` / `OPENAI_BASE_URL`（仅当 ``narration_provider`` 为 **openai** 时常用；仍写入 ``api_keys.openai``）
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
python -m narration ... --provider modelscope   # 单次覆盖 narration_provider
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

若仍 **skipped**：请确认 ``NARRATION_PROVIDER`` 与 ``API_KEYS_JSON``（或 ``MODELSCOPE_API_KEY_FREE`` 等）里的 **slug 一致**，且 ``API_BASE_URLS_JSON`` / ``*_BASE_URL`` 已为该 slug 配置网关。

```bash
RUN_NARRATION_API_TEST=1 PYTHONPATH=python/movieteller_config/src:python/narration/src \\
  python -m pytest python/narration/tests/test_example_mp4_local.py -v -m integration
```
