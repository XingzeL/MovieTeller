# MovieTeller 文档

文档分为两组：**说明性**（描述当前系统，须与实现一致）与 **过程性**（计划、落地记录、设计稿，允许滞后于代码）。

| 目录 | 类型 | 用途 |
|------|------|------|
| **[reference/](reference/)** | 说明性 | 合同、API、本地运行、可观测性、运维行为 |
| **[planning/](planning/)** | 过程性 | 路线图、设计-only、变更记录、归档计划 |

## 从哪里读

| 你想… | 打开 |
|--------|------|
| 本地跑通 Job 主链路 | [reference/local-development.md](reference/local-development.md) |
| Phase 2 Lite 生产拓扑与验收 | [reference/phase2-lite.md](reference/phase2-lite.md) |
| HTTP API 与状态机 | [reference/jobs-api.md](reference/jobs-api.md) + [reference/job-lifecycle.md](reference/job-lifecycle.md) |
| Smoke 测试 | [reference/jobs-api-smoke.md](reference/jobs-api-smoke.md) |
| 产品化阶段规划（非现状） | [planning/productization-roadmap.md](planning/productization-roadmap.md) |
| Full Phase 2 分布式设计（未实施） | [planning/phase2-queue-design.md](planning/phase2-queue-design.md) |

仓库根 [README.md](../README.md) 的快速开始指向 **reference** 下的说明性文档。
