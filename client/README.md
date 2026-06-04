# MovieTeller 前端

Vite + React + TypeScript。本地开发时通过代理访问后端 Job API。

## 运行

```bash
npm install
npm run dev
```

默认 **http://localhost:5173**；`/api` 代理到 `http://localhost:3001`（见 [vite.config.ts](./vite.config.ts)）。

需先在仓库根目录按 [docs/reference/local-development.md](../docs/reference/local-development.md) 启动 `server`。

## 主界面

- **上传页**（`UploadPage`）：`POST /api/jobs`，支持 `?jobId=` 打开已有任务
- **任务面板**（`JobPanel`）：状态、进度、增量日志、取消、产物下载

主链路说明与排障见仓库根 [README.md](../README.md) 与 [docs/reference/local-development.md](../docs/reference/local-development.md)。

## 构建

```bash
npm run build
```

产物在 `dist/`。
