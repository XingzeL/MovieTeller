# MovieTeller
基于大模型的自动生成AI电影旁白和剧本的工具；The LLM base Movie/video Script, narration generator

## MVP：本地运行（AI English Scene Narrator · mock）

前置条件：**Node.js 18+**（建议使用当前 LTS）和 **Python 3.12**。

本仓库为前后端分离的两套工程，开发时需要**同时**启动后端与前端。

### 0. Python 虚拟环境

建议所有 Python 相关能力都放在仓库根目录的 **`.venv`** 中运行：

```bash
cd /path/to/MovieTeller
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e ./python/movieteller_config -e ./python/narration -e ./python/subtitle_extraction
python -m pip install -e ./python/narration_polish -e ./python/subtitle_analysis
python -m pip install videocaptioner pytest
```

后端的字幕提取链路现在会**优先使用仓库根目录 `.venv/bin/python3`**；手动 smoke 也应先激活 `.venv`，再运行 `python` / `python3`。

### 1. 后端（Express）

```bash
cd server
npm install
npm run dev
```

默认监听 **http://localhost:3001**。健康检查：`GET http://localhost:3001/health`。

Mock 生成接口：`POST http://localhost:3001/api/generate`（JSON 传 URL；`multipart/form-data` 传本地 MP4）。

字幕提取（建议安装到项目 `.venv`：`python -m pip install videocaptioner`）：`POST http://localhost:3001/api/extract/subtitles`，`multipart/form-data` 字段 **`file`**。 Python 包见 [python/subtitle_extraction/README.md](python/subtitle_extraction/README.md)。

### 2. 前端（Vite + React）

新建终端：

```bash
cd client
npm install
npm run dev
```

浏览器打开终端里提示的地址（一般为 **http://localhost:5173**）。前端通过 Vite 代理把 `/api` 转发到 `localhost:3001`，请勿单独改端口除非同时改 [client/vite.config.ts](client/vite.config.ts) 与后端 `PORT`。

### 3. 生产构建（可选）

```bash
cd client && npm run build   # 静态文件在 client/dist
```

当前 MVP 不提供 Express 托管静态资源；若需一体化部署，可将 `client/dist` 交给任意静态服务器或由 Express `express.static` 提供。

## 配置模块（Configuration）

MovieTeller 使用统一的配置加载规则（Python **`movieteller_config`**、Node **`server/src/config`**）：

- **优先级**：环境变量 > 仓库根目录 `config/local.yaml`（gitignore）> `MOVIE_TELLER_CONFIG` 指向的 YAML > 默认值。
- **换供应商**：一般只需改 YAML / `API_KEYS_JSON` / `PREFIX_API_KEY` 与 `NARRATION_IMAGE_MODEL`，无需改 `movieteller_config` 或 `server/src/config` 代码（约定：`FOO_API_KEY`→`foo`，`API_KEYS_JSON` 覆盖单项 env）。
- **模板**：复制根目录 [.env.example](.env.example) 为 `.env`（`.env` 勿提交）。
- **详情**：见 [python/movieteller_config/README.md](python/movieteller_config/README.md) 与根目录 [.env.example](.env.example)。
- **Python 旁白生成（ffmpeg 区间抽帧 + OpenAI 兼容 API，slug 由 ``NARRATION_PROVIDER`` 指定）**：见 [python/narration/README.md](python/narration/README.md)。
- **Python 旁白润色（按 duration / 语速 / CEFR 级别改写，供后续 TTS 使用）**：见 [python/narration_polish/README.md](python/narration_polish/README.md)。

后端启动时会加载 `.env` 并缓存配置（见 `server/src/index.js` 中对 `loadConfig()` 的调用）。
