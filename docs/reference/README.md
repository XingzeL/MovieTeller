# 说明性文档（Reference）

描述 **当前实现** 的行为与用法。若与代码不一致，应改文档或改代码。

| 文档 | 内容 |
|------|------|
| [local-development.md](local-development.md) | 本地环境、前后端启动、Job 目录、排障 |
| [phase2-lite.md](phase2-lite.md) | Postgres 控制面 + api/worker 实施合同与验收 |
| [job-lifecycle.md](job-lifecycle.md) | Job 状态机、ACL、取消、Phase 2 Lite 附录 |
| [jobs-api.md](jobs-api.md) | Job HTTP API、manifest、smoke 入口 |
| [jobs-api-smoke.md](jobs-api-smoke.md) | `jobs-api-smoke.mjs` 模式与 `--strict` |
| [observability.md](observability.md) | JSONL 事件、`workflow.stage.*` 字段约定 |
| [worker-runtime.md](worker-runtime.md) | `MOVIE_TELLER_RUN_MODE`、recovery 矩阵 |
| [job-queue-limitations.md](job-queue-limitations.md) | 单进程队列与多实例限制 |
| [multi-user-storage-and-transport.md](multi-user-storage-and-transport.md) | 用户隔离与下载传输 |
| [multi-user-data-model.md](multi-user-data-model.md) | 逻辑数据模型（控制面 + 文件产物） |
| [clerk-signup-troubleshooting.md](clerk-signup-troubleshooting.md) | Clerk 注册/登录排障 |
| [data-flow-diagram.md](data-flow-diagram.md) | 数据流示意 |

过程性文档（路线图、设计稿、落地记录）见 [../planning/](../planning/)。
