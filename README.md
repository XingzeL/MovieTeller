# MovieTeller
基于大模型的自动生成AI电影旁白和剧本的工具；The LLM base Movie/video Script, narration generator

## MVP：本地运行（AI English Scene Narrator · mock）

前置条件：**Node.js 18+**（建议使用当前 LTS）。

本仓库为前后端分离的两套工程，开发时需要**同时**启动后端与前端。

### 1. 后端（Express）

```bash
cd server
npm install
npm run dev
```

默认监听 **http://localhost:3001**。健康检查：`GET http://localhost:3001/health`。

Mock 生成接口：`POST http://localhost:3001/api/generate`（JSON 传 URL；`multipart/form-data` 传本地 MP4）。

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

后端启动时会加载 `.env` 并缓存配置（见 `server/src/index.js` 中对 `loadConfig()` 的调用）。
