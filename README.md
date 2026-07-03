# MovieTeller

基于大模型的长视频旁白、TTS 与成片生成工具（LLM-based movie / video narration pipeline）。

当前仓库处于 **本地单机可用的产品化 Alpha**：Web 上传 → **Job API** → Python 全链路处理 → 进度/日志/产物下载。  
**主链路不是**早期的 Mock `POST /api/generate`。

## 系统架构

```text
浏览器 (React + Vite)
  │  /api → 开发时 Vite 代理；生产时 Nginx 反代
  ▼
Express API (Node.js)
  │  POST /api/jobs → 写磁盘 + Postgres 队列表
  │  Worker claim 后 spawn: python -m movie_pipeline.job_runner
  ▼
Python full_workflow
  │  字幕 ASR → 帧池 → 旁白 LLM → 润色 → TTS → 混流 → 学习卡片
  ▼
artifacts/jobs/{jobId}/
  workflow.json · logs/workflow.jsonl · artifacts/manifest.json
  render/narrated.mp4 · study_cards/
```

生产推荐拓扑：**Postgres + API 进程 + Worker 进程 + 本地磁盘**（Phase 2 Lite）。详见 [docs/reference/phase2-lite.md](docs/reference/phase2-lite.md)。

---

## 环境要求

### 运行时

| 组件 | 版本 / 要求 | 用途 |
|------|-------------|------|
| **Node.js** | 18+（建议 LTS） | Express API、Worker、前端构建 |
| **Python** | **3.12**（推荐） | Job runner、字幕/旁白/TTS 管线 |
| **PostgreSQL** | 16+ | Job 控制面、用户配额、计费（生产 / Phase 2 Lite **必需**） |
| **Docker** | 可选 | 本地启动 Postgres（`docker compose`） |

### 系统工具（须在 PATH 或 `.env` 中配置路径）

| 工具 | 必需 | 说明 |
|------|------|------|
| **ffmpeg** | 是 | 混流、抽帧、quota 裁剪；`GET /api/healthz/deep` 会检查 |
| **ffprobe** | 是（有 DB 时） | 创建 Job 时探测视频时长（计费 / 裁剪） |
| **VideoCaptioner CLI** | 是 | 字幕 ASR（`videocaptioner` 在 PATH，或配置 `VIDEOCAPTIONER_BIN`） |
| **yt-dlp** | URL 导入时需要 | 本地上传可跳过；B 站 / YouTube 等需 cookies，见 [secrets/README.md](secrets/README.md) |

### 外部服务

| 服务 | 必需 | 说明 |
|------|------|------|
| **LLM / TTS API** | 是（跑完整 workflow） | 旁白、润色、TTS 等；见下方「配置」 |
| **Clerk** | 生产推荐 | 真实用户登录；本地 dev 可跳过 |
| **Nginx** | 生产部署推荐 | 静态前端 + 反代 API；示例见 [deploy/nginx/movieteller.conf](deploy/nginx/movieteller.conf) |

### 硬件与磁盘

- 单 Worker 默认 **并发 1**（`MAX_RUNNING_JOBS=1`），长任务占 CPU / 内存 / 磁盘 I/O
- Job 数据默认在 **`artifacts/jobs/`**（`JOBS_ROOT`），含上传视频、中间产物、成片；需预留足够磁盘空间
- 成片代理下载上限约 **200MB**（见 phase2-lite 设计）

---

## 依赖清单

### Node.js（`server/` + `client/`）

```bash
cd server && npm install    # express, pg, @clerk/backend, multer, …
cd client && npm install      # react 19, vite 8, @clerk/clerk-react, tailwindcss 4, …
```

### Python 可编辑包（仓库根 `.venv`）

在仓库根目录创建虚拟环境后，**按顺序**安装全部 Python 包：

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -U pip

# 外部 CLI / 工具（非 pip 包）
python -m pip install videocaptioner pytest yt-dlp

# 仓库内 editable 包
for pkg in movieteller_config movieteller_logging pipeline_types media_utils model_gateway \
  pipeline_transcript rerank subtitle_extraction subtitle_analysis frame_source \
  video_frame_pool subtitle_context narration narration_polish narration_speech \
  narration_video movie_pipeline video_ingest; do
  python -m pip install -e "./python/${pkg}"
done
```

Node 启动 Job 时优先使用 **`.venv/bin/python3`**（可用 `MOVIE_TELLER_PYTHON` 覆盖）。

### Python 包与职责（摘要）

| 包 | 职责 |
|----|------|
| `movieteller_config` | 环境变量 + YAML 配置合并 |
| `model_gateway` | LLM / TTS / Embedding 统一网关 |
| `subtitle_extraction` | VideoCaptioner ASR 字幕 |
| `narration` / `narration_polish` / `narration_speech` / `narration_video` | 旁白生成、润色、TTS、混流 |
| `movie_pipeline` | 编排入口（含 `job_runner`） |
| `video_ingest` | 视频 URL 解析与下载（yt-dlp） |

各包细节见 `python/*/README.md`。

---

## 配置

配置优先级：**环境变量 > `config/local.yaml` > 打包默认值**。

### 1. 复制模板

```bash
cp .env.example .env
cp config/local.yaml.example config/local.yaml
```

- `.env`：API Key、端口、`DATABASE_URL`、Clerk、yt-dlp cookies 等
- `config/local.yaml`：provider、模型目录、TTS 默认值、超时/重试（**勿提交密钥**）

说明见 [config/README.md](config/README.md) 与 [python/movieteller_config/README.md](python/movieteller_config/README.md)。

### 2. 最小可跑配置示例

在 `.env` 中至少配置模型密钥（按你实际 provider 调整）：

```bash
# 示例：OpenAI 兼容网关
NEW_API_KEY_NARRATION_FREE=sk-...
TTS_API_KEY=sk-...

PORT=3001
FFMPEG_PATH=ffmpeg
```

在 `config/local.yaml` 中指向 provider 与模型（模板已含示例结构）。

### 3. Phase 2 Lite / 生产

```bash
DATABASE_URL=postgresql://movieteller:movieteller@localhost:5432/movieteller
```

### 4. Clerk 登录（可选，生产推荐）

```bash
# 仓库根 .env
CLERK_SECRET_KEY=sk_test_...

# client/.env.local（需自行创建）
VITE_CLERK_PUBLISHABLE_KEY=pk_test_...
```

未配置 Clerk 时，**非 production** 环境可用 demo 会话：`POST /api/dev/session`，body `{"userId":"user-a"}`。

### 5. 视频 URL 导入（可选）

B 站 / YouTube 需 cookies 文件，见 [secrets/README.md](secrets/README.md)：

```bash
YT_DLP_PATH=/path/to/MovieTeller/.venv/bin/yt-dlp
YT_DLP_COOKIES=secrets/yt-dlp-cookies.txt
YT_DLP_IMPERSONATE=chrome
```

---

## 本地运行

完整排障与取消语义见 **[docs/reference/local-development.md](docs/reference/local-development.md)**。

### 方式 A：Combined 快速调试（无 Postgres）

适合改代码、快速验证 API；**无 `DATABASE_URL`** 时使用内存队列，API 重启会将遗留 `queued`/`running` 标为 `failed`。

```bash
# 1) Python 环境（见上文「依赖清单」）
source .venv/bin/activate

# 2) 后端
cd server && npm install && npm run dev    # http://localhost:3001

# 3) 前端（新终端）
cd client && npm install && npm run dev    # http://localhost:5173
```

浏览器打开前端 → 上传 MP4 → 创建 Job → 查看进度并下载 **旁白成片** 与 **学习卡片**。

### 方式 B：Phase 2 Lite（推荐，接近生产）

需要 Docker 与 `DATABASE_URL`。

```bash
# 1) 启动 Postgres
docker compose up -d postgres

# 2) 迁移
cd server && npm install && npm run db:migrate

# 3) 终端 A — API（不 spawn Python）
npm run dev:api

# 4) 终端 B — Worker（从 DB claim Job）
npm run dev:worker

# 5) 终端 C — 前端
cd ../client && npm install && npm run dev
```

| 变量 | 说明 |
|------|------|
| `MOVIE_TELLER_RUN_MODE` | `combined`（默认）\| `api` \| `worker` |
| `JOBS_ROOT` | 默认 `<repo>/artifacts/jobs` |
| `MAX_RUNNING_JOBS` | Worker 并发，默认 `1` |
| `STALE_HEARTBEAT_SEC` | heartbeat 超时，默认 `90` |

健康检查：

- 浅检查：`GET http://localhost:3001/health`
- 深度检查：`GET http://localhost:3001/api/healthz/deep`（ffmpeg、jobs 目录、job_runner）

---

## 生产部署

当前**未内置** Express 托管前端静态资源；推荐 **Nginx + 分离进程**。

### 部署拓扑

```text
                    ┌─────────────┐
  用户浏览器 ────────►│   Nginx     │
                    │  :443/8443  │
                    └──────┬──────┘
           ┌───────────────┼───────────────┐
           │               │               │
           ▼               ▼               ▼
    client/dist/     /api/* 反代      /health
    静态 SPA         Express API
                     :3001
                           │
                           ▼
                    PostgreSQL :5432
                           ▲
                           │
                    Express Worker
                    (MOVIE_TELLER_RUN_MODE=worker)
                           │
                           ▼
                    python job_runner
                    artifacts/jobs/
```

### 步骤 1：准备服务器环境

与「环境要求」一致：Node 18+、Python 3.12、ffmpeg/ffprobe、VideoCaptioner、Postgres、（可选）yt-dlp。

### 步骤 2：拉代码并安装依赖

```bash
git clone <repo-url> MovieTeller && cd MovieTeller

# Python
python3.12 -m venv .venv && source .venv/bin/activate
# … 按上文「依赖清单」安装 pip 包

# Node
cd server && npm install && npm ci --omit=dev   # 生产可按需省略 devDependencies
cd ../client && npm install && npm run build    # 输出 client/dist
```

### 步骤 3：配置环境变量

在仓库根创建 `.env` 与 `config/local.yaml`（**勿提交**）：

```bash
PORT=3001
DATABASE_URL=postgresql://user:pass@localhost:5432/movieteller
MOVIE_TELLER_RUN_MODE=api          # API 进程
# Worker 进程单独设 MOVIE_TELLER_RUN_MODE=worker

CLERK_SECRET_KEY=sk_live_...
JOBS_ROOT=/var/lib/movieteller/jobs
MAX_RUNNING_JOBS=1
```

前端构建时写入 Clerk（`client/.env.production` 或构建前 export）：

```bash
VITE_CLERK_PUBLISHABLE_KEY=pk_live_...
```

### 步骤 4：数据库迁移

```bash
cd server
npm run db:migrate
```

上线前检查清单见 [docs/planning/m7-release-checklist.md](docs/planning/m7-release-checklist.md)（迁移幂等、计费、retention）。

### 步骤 5：启动 API 与 Worker

使用进程管理器（systemd、supervisor、pm2 等）分别守护：

```bash
# API
cd server
MOVIE_TELLER_RUN_MODE=api npm run start:api

# Worker（另进程 / 另机器，需共享 JOBS_ROOT 与 DATABASE_URL）
cd server
MOVIE_TELLER_RUN_MODE=worker npm run start:worker
```

**注意**：`combined` 模式仅适合本地调试；生产应使用 **api + worker** 分离。

### 步骤 6：Nginx 反向代理

1. 构建前端：`cd client && npm run build`
2. 参考 [deploy/nginx/movieteller.conf](deploy/nginx/movieteller.conf)：
   - `root` 指向 `client/dist`
   - `/api/` → `http://127.0.0.1:3001`
   - `client_max_body_size` 建议 ≥ 500m（大视频上传）
   - 生产 HTTPS 证书替换示例中的 mkcert 路径
3. 重载 Nginx 后访问站点

本地 HTTPS 示例（macOS Homebrew Nginx）：

```bash
brew install mkcert nss
mkcert -install
mkdir -p /opt/homebrew/etc/nginx/certs
mkcert -cert-file /opt/homebrew/etc/nginx/certs/movieteller-local.pem \
       -key-file /opt/homebrew/etc/nginx/certs/movieteller-local-key.pem \
       localhost 127.0.0.1 ::1
# 复制 deploy/nginx/movieteller.conf 并修改 root / 证书路径
```

### 步骤 7：部署后验证

```bash
curl -s http://localhost:3001/health
curl -s http://localhost:3001/api/healthz/deep | jq .

cd server
npm run smoke              # 需 API 已启动
npm run smoke:create       # 创建测试 Job
```

有 Postgres 时：

```bash
DATABASE_URL=... npm run test:db
```

---

## 主链路 API（摘要）

| 端点 | 说明 |
|------|------|
| `POST /api/jobs` | 上传 MP4 或 JSON `sourceUrl` 创建 Job |
| `GET /api/jobs` | 任务列表 |
| `GET /api/jobs/:id` | 详情 |
| `GET /api/jobs/:id/progress` | 进度 |
| `GET /api/jobs/:id/logs` | 结构化日志 |
| `GET /api/jobs/:id/artifacts/*` | 下载成片 / 学习卡片 |
| `POST /api/jobs/:id/cancel` | 取消 |
| `POST /api/jobs/:id/retry` | 手动重试 |

Job 目录：`artifacts/jobs/{jobId}/`（`JOBS_ROOT`）。  
完整契约：[docs/reference/jobs-api.md](docs/reference/jobs-api.md)。

---

## 自检（Smoke）

需先启动 API（Phase 2 Lite 还需 Worker）：

```bash
cd server
npm run smoke              # 健康、列表、上传校验
npm run smoke:create       # 创建 Job（无 --video 时用 ffmpeg 生成 1s 测试片）
npm run smoke:cancel       # 创建 → 取消
npm run smoke:workflow     # 轮询至终态（耗时长，需完整 Python/API）
```

详见 [docs/reference/jobs-api-smoke.md](docs/reference/jobs-api-smoke.md)。

---

## 文档索引

说明性文档（当前系统）与过程性文档（计划/归档）分目录存放，见 **[docs/README.md](docs/README.md)**。

| 文档 | 内容 |
|------|------|
| **[docs/reference/local-development.md](docs/reference/local-development.md)** | 本地运行主文档：架构、Job 目录、取消、排障 |
| [docs/reference/phase2-lite.md](docs/reference/phase2-lite.md) | Postgres + api/worker 生产拓扑与验收 |
| [docs/reference/jobs-api.md](docs/reference/jobs-api.md) | Job HTTP API、状态机、产物 manifest |
| [docs/reference/billing-and-usage.md](docs/reference/billing-and-usage.md) | 配额、预占、计费（M7） |
| [docs/planning/productization-roadmap.md](docs/planning/productization-roadmap.md) | 产品化路线图（过程性） |
| [python/movie_pipeline/README.md](python/movie_pipeline/README.md) | Python 编排与 CLI |

---

## 遗留 / 非主链路

| 入口 | 说明 |
|------|------|
| `POST /api/generate` | **Mock demo**（假旁白），已脱离主产品流程 |
| `POST /api/extract/subtitles` | 独立字幕提取 API |
| `python -m movie_pipeline …` | 开发者 CLI（SRT + 视频），不经过 Job 布局 |

---

## 常见问题

| 现象 | 处理 |
|------|------|
| 前端 Network error | 确认 server 在 3001；Vite 代理见 [client/vite.config.ts](client/vite.config.ts) |
| Job 一直 queued | 检查 Worker 是否运行、`MAX_RUNNING_JOBS`、Postgres 连接 |
| Job failed，无 API key | 配置 `.env` / `local.yaml` 中的 provider 与密钥 |
| B 站 412 / YouTube bot | 更新 [secrets/yt-dlp-cookies.txt](secrets/README.md) 或改本地上传 |
| DB 相关 API 503 | 检查 `DATABASE_URL` 与 Postgres；api/worker 模式 **必须** 有 DB |
| 取消后仍在跑 | 协作式取消 + 长调用空窗；见 local-development §10 |

更多见 [docs/reference/local-development.md#12-常见问题](docs/reference/local-development.md#12-常见问题)。
