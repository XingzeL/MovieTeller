---
name: Configuration 配置模块
overview: 集中管理 API Key、模型名、ffmpeg 路径与运行时参数；Python 视频理解与 Node 编排均通过本模块读取配置（环境变量优先，可选 YAML 覆盖）。
todos:
  - id: cfg-python-pkg
    content: 新建 python/movieteller_config/（或 mt_config）：load_settings()、default.yaml、与 .env 合并优先级
    status: pending
  - id: cfg-node
    content: 新建 server/src/config/index.js：dotenv + 校验 OPENAI_*、IMAGE_MODEL；供 pipeline/narrationProvider 引用
    status: pending
  - id: cfg-docs
    content: 根目录 .env.example 或分模块 .env.example；README 说明优先级与勿提交密钥
    status: pending
isProject: false
---

# Configuration 模块子计划（跨语言配置）

## 1. 目标

- **单一入口**：业务代码（**视频理解 / Narration**、后续字幕流水线、Node API）**不**散落读取 `os.environ["OPENAI_API_KEY"]`，统一通过**配置模块**获取已解析、带默认值与校验的配置对象。
- **可注入**：测试与环境可通过传入 dict / mock 覆盖，便于单元测试。
- **敏感信息**：API Key、密钥类 **仅**来自环境变量或本地忽略文件（如 `.env`、`config/local.yaml`），**禁止**提交仓库。

## 2. 配置项清单（首期）

| 键 | 用途 | 典型来源 |
|----|------|----------|
| `OPENAI_API_KEY` | OpenAI 多模态 / Chat | 环境变量 |
| `OPENAI_BASE_URL` | 可选，兼容代理或 Azure 风格端点 | 环境变量 |
| `NARRATION_IMAGE_MODEL` / `IMAGE_MODEL` | 视频理解所用模型 id（如 `gpt-4o-mini`） | env 或 yaml 默认 |
| `MAX_FRAMES_PER_SEGMENT` | 单段最多截图张数 | yaml + env 覆盖 |
| `FFMPEG_PATH` | ffmpeg 可执行文件路径 | env，默认 `ffmpeg` |
| `DEFAULT_PROMPT_STYLE` | documentary / how-to / … | yaml |
| （预留）`VIDEOCAPTIONER_BIN`、`NARRATION_API_URL` | 其它适配器 | env |

命名可在实现期统一前缀（如 `MT_*`），但须在 README 中列表说明。

## 3. 优先级（合并规则）

统一约定（Python 与 Node 行为一致）：

1. **环境变量**（最高）
2. **`config/local.yaml`**（或 `MOVIE_TELLER_CONFIG` 指向的文件路径，gitignore）
3. **`config/default.yaml`** 包内默认

布尔与数字需做类型解析；缺失必填项时 **启动即报错**（fail-fast），避免运行到一半才 401。

## 4. Python 侧布局（供 Narration 使用）

与 [narration-module.plan.md](narration-module.plan.md) 并列，建议独立包名避免与标准库冲突：

```text
python/movieteller_config/
├── pyproject.toml          # 可被 narration 列为依赖
├── README.md
├── src/
│   └── movieteller_config/
│       ├── __init__.py     # export load_settings, Settings
│       ├── schema.py       # 数据结构（dataclass 或 TypedDict）
│       └── loader.py       # 读 env + yaml + 合并
├── config/
│   └── default.yaml
└── tests/
    └── test_loader.py
```

**Narration 模块用法**：`story.py`、`cli.py` 在发起请求前调用 `from movieteller_config import load_settings`，使用 `settings.default_provider()`、`settings.default_model_for_capability("narration")`；**禁止**在业务文件顶层直接 `os.getenv(...)` 读取模型网关配置（测试除外）。

## 5. Node 侧布局（供编排与 Provider 使用）

```text
server/src/config/
├── index.js          # loadConfig(): { openaiApiKey, imageModel, ... }
└── schema.js         # 可选：默认值与校验
```

- 使用 `dotenv` 可选加载项目根 `.env`。
- `createHttpNarrationProvider`、`pipeline/narrateVideo.js` **引用** `config`，不写死模型名。

## 6. 与 Narration 子计划的顺序依赖

- **配置模块应先于或并行于 Narration 核心**：`narrate_segment` / `frames` / `story` 开发时即接入 `load_settings`。
- 更新 [narration-module.plan.md](narration-module.plan.md) 中「配置约定」：**详见本子计划**，避免重复维护两份键名。

## 7. 测试

- Python：`test_loader.py` 覆盖合并优先级、缺失必填报错。
- Node：可选轻量测试 mock `process.env`。

## 8. 实现顺序（本子计划内）

1. 约定键名与 `default.yaml` 模板 + `.gitignore` 规则（`local.yaml`、`.env`）。
2. 实现 `movieteller_config.loader` + 测试。
3. 实现 `server/src/config` + 在现有 mock 路由中试读（可不改变行为）。
4. Narration 子计划中的 `story.py` 改为消费配置模块。
