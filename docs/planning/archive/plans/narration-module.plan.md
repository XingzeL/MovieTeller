---
name: Narration 视频旁白模块
overview: 独立 Python 包：按时间区间解码抽帧 + OpenAI 多模态生成旁白文本；依赖配置模块 movieteller_config 提供 API Key 与模型；与总计划 §14 对齐（区间解码优先）。
todos:
  - id: narr-deps-config
    content: 依赖 python/movieteller_config（见 config-module.plan.md）；story.py 仅通过 load_settings 取密钥与模型
    status: pending
  - id: narr-scaffold
    content: 新建 python/narration/ 目录树、pyproject.toml/requirements.txt、.env.example（业务默认值可由 movieteller_config 提供）
    status: pending
  - id: narr-core
    content: 实现区间抽帧（ffmpeg image2pipe 优先）+ 帧序列→旁白文案（prompts/story，片段时长）
    status: pending
  - id: narr-cli
    content: 实现 python -m narration.cli（--video --start --end --json）
    status: pending
  - id: narr-tests
    content: pytest：prompt 拼装、抽帧 mock；可选集成测（跳过需 OPENAI_API_KEY）
    status: pending
isProject: false
---

# Narration 模块子计划（视频理解 / 旁白生成）

## 1. 范围与边界

- **做什么**：输入**本地视频路径** + **可选 `start_sec` / `end_sec`**（与上游字幕分析输出的时间段一致），输出**该区间画面内容的旁白字符串**（英文为主，可配置）。
- **不做什么**：TTS、成片合成、ElevenLabs、Gradio（常见旁白流水线里的这些步骤**不**在本模块实现）。
- **上游**：字幕分析模块给出的 `tStartMs`/`tEndMs`（本模块只消费时间段，不依赖字幕文件）。
- **实现要点**：抽帧后经多模态 LLM 生成旁白（`prompts.py` 负责风格/字数，`story.py` 负责调用）；抽帧策略按总计划 **区间解码优先**（ffmpeg `-ss` / `-t`，不切分 mp4）。
- **配置**：OpenAI **API Key**、**模型 id**、**MAX_FRAMES**、**FFMPEG_PATH** 等一律通过 **[配置模块](config-module.plan.md)**（`movieteller_config`）读取；`story.py` **禁止**直接 `os.getenv("OPENAI_API_KEY")`（测试 mock 除外）。

## 2. 代码目录（本仓库内新建）

仓库根下新建（与 `python/movieteller_config/` 并列，后者见配置子计划）：

```text
python/narration/
├── pyproject.toml              # 依赖声明含 movieteller_config（本地 path 或 workspace）
├── README.md                   # 安装、与配置模块的衔接说明
├── .env.example                # 可选提示：实际键以 movieteller_config 为准
├── src/
│   └── narration/              # 包名 narration（注意 PYTHONPATH 或 editable install）
│       ├── __init__.py
│       ├── __main__.py         # python -m narration
│       ├── cli.py              # argparse：CLI 参数可覆盖配置中的 model/style
│       ├── frames.py           # 区间解码抽帧 → base64；ffmpeg 路径来自配置
│       ├── prompts.py          # 构建 system/user 文本（prompt_style / documentary 等）
│       ├── story.py            # OpenAI client 使用配置中的 api_key、base_url、model
│       └── narrate.py          # 对外 API：narrate_segment(..., settings 可选注入)
└── tests/
    ├── conftest.py             # fixtures：短视频路径可选跳过
    ├── test_prompts.py
    ├── test_frames_mock.py     # mock subprocess/ffmpeg 或纯函数
    └── test_story_mock.py      # mock openai client
```

说明：**实现阶段**再创建上述文件；本文件为子计划与契约。

## 3. 配置约定（委托配置模块）

具体键名、合并优先级、Python/Node 双实现见 **[config-module.plan.md](config-module.plan.md)**。Narration 仅依赖解析后的 **Settings** 对象（如 `settings.default_provider()`、`settings.default_model_for_capability("narration")`、`settings.max_frames_per_segment`）。

## 4. 对外 API（Python）

```python
def narrate_segment(
    video_path: str,
    start_sec: float | None = None,
    end_sec: float | None = None,
    *,
    prompt_style: str = "documentary",
    custom_prompt: str = "",
    image_model: str | None = None,
) -> str: ...
```

- 若 `start_sec`/`end_sec` 均为 `None`：视为 `video_path` 已是短片段，时长由 `moviepy`/`ffprobe` 获取。
- **片段时长**用于 `prompts` 中字数估算，**不得**使用整片时长。

## 5. CLI 契约

```bash
python -m narration --video /path/to.mp4 --start 12.5 --end 45 --json
```

stdout 输出 JSON：`{ "text": "...", "duration_sec": 32.5 }`（字段可实现期微调）。

## 6. 测试策略

- **单元测试**：`prompts.py` 拼接与字数逻辑；`frames.py` 在 mock subprocess 下返回固定 base64。
- **可选集成测试**：设置 `OPENAI_API_KEY` 时跑真实 API（pytest marker `integration`）；CI 默认跳过。

## 7. 与 Node / 总计划衔接

- Node `NarrationProvider` 后续可通过 **子进程调用 CLI** 或 **HTTP 包装**（本计划不包含 HTTP，可在 Phase 2 追加）；Node 侧使用 **`server/src/config`**（见 [config-module.plan.md](config-module.plan.md) §5）读取同类键，避免与 Python 行为不一致。
- **总计划**：与 Cursor「三模块需求与开发计划」§14（Python 视频理解）、§14.3（区间解码）保持一致；必要时在本仓库新增 `docs/planning/archive/plans/pipeline-overview.plan.md` 做入库快照。

## 8. 实现顺序（本子计划内）

1. **接入 `movieteller_config`**（或与配置子计划并行完成最小 `load_settings`）。
2. 脚手架 + `.env.example`（指向配置模块文档）。
3. `frames.py` 区间解码 + 单元测试（使用配置中的 ffmpeg 路径、max_frames）。
4. `story.py` + `prompts.py` + mock 测试（注入 fake Settings）。
5. `narrate.py` 组装 + `cli.py`。
6. README 与可选 integration marker。
