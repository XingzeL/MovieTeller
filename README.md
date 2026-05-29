# MovieTeller

基于大模型的长视频旁白、TTS 与成片生成工具（LLM-based movie / video narration pipeline）。

当前仓库处于 **本地单机可用的产品化 Alpha**：Web 上传 → **Job API** → Python 全链路处理 → 进度/日志/产物下载。  
**主链路不是**早期的 Mock `POST /api/generate`。

## 快速开始

前置：**Node.js 18+**、**Python 3.12**、**ffmpeg**、已配置的模型 API（见 `.env` / `config/local.yaml`）。

```bash
# 1) Python（仓库根，详见 docs/local-development.md）
python3.12 -m venv .venv && source .venv/bin/activate
# … pip install 各 python/* 包与 videocaptioner

# 2) 后端
cd server && npm install && npm run dev    # http://localhost:3001

# 3) 前端（新终端）
cd client && npm install && npm run dev    # http://localhost:5173
```

浏览器打开前端 → 上传 MP4 → 创建 Job → 在任务列表与详情中查看进度，成功后下载 **旁白成片** 与 **学习卡片**。

## 文档索引

| 文档 | 内容 |
|------|------|
| **[docs/local-development.md](docs/local-development.md)** | **本地运行主文档**：架构、环境、前后端、Job 目录、排障 |
| [docs/jobs-api.md](docs/jobs-api.md) | Job HTTP API、状态机、产物 manifest、smoke |
| [docs/productization-roadmap.md](docs/productization-roadmap.md) | 产品化阶段路线图 |
| [python/movieteller_config/README.md](python/movieteller_config/README.md) | 配置与 provider |

## 主链路（摘要）

```text
UploadPage → POST /api/jobs → server jobQueue → python -m movie_pipeline.job_runner
→ artifacts/jobs/{jobId}/workflow.json + logs/workflow.jsonl + artifacts/manifest.json
→ 前端轮询 GET /jobs/:id、/progress、/logs；GET /artifacts 下载
```

- Job 数据目录：默认 `artifacts/jobs/`（`JOBS_ROOT`）
- 任务列表：`GET /api/jobs`
- 深度健康检查：`GET /api/healthz/deep`
- 快速自检：`cd server && npm run smoke`

## 配置

- **优先级**：环境变量 > `config/local.yaml` > 默认
- 模板：[.env.example](.env.example)、[config/local.yaml.example](config/local.yaml.example)
- Node 与 Python 共用同一套配置约定（`movieteller_config` / `server/src/config`）

## 遗留 / 非主链路

| 入口 | 说明 |
|------|------|
| `POST /api/generate` | **Mock demo**（假旁白），已脱离主产品流程 |
| `POST /api/extract/subtitles` | 独立字幕提取 |
| `python -m movie_pipeline …` | 开发者 CLI（SRT + 视频），不经过 Job 布局 |

## 模块说明（Python）

编排入口：[python/movie_pipeline](python/movie_pipeline)（含 `job_runner`）。  
领域包：`narration`、`narration_polish`、`narration_speech`、`narration_video`、`subtitle_extraction` 等，见各目录 `README.md`。

## 生产构建（可选）

```bash
cd client && npm run build   # 输出 client/dist
```

当前未内置 Express 托管静态资源；部署时需自行反向代理或 `express.static`。
