# 过程性文档（Planning）

记录 **计划、设计、落地过程与历史决策**。允许与当前代码不一致；以 [../reference/](../reference/) 说明性文档为准描述「现在怎么用」。

| 文档 | 内容 |
|------|------|
| [productization-roadmap.md](productization-roadmap.md) | 产品化阶段一～十路线图 |
| [phase2-queue-design.md](phase2-queue-design.md) | Full Phase 2 分布式队列（design-only） |
| [auth-plan.md](auth-plan.md) | Clerk / 多用户认证实施计划 |
| [multi-user-readiness-work-items.md](multi-user-readiness-work-items.md) | 多用户就绪工作项 |
| [database-persistence-plan.md](database-persistence-plan.md) | M7 用户、套餐、额度、使用记录与学习卡入库规划 |
| [observability-95-landing.md](observability-95-landing.md) | 可观测性 B1–B4 落地记录 |
| [stage-observability-design.md](stage-observability-design.md) | Stage 可观测性设计（含落地状态） |
| [pipeline-parallelization-plan.md](pipeline-parallelization-plan.md) | Pipeline 并行化方案 |
| [tts-centric-resume.md](tts-centric-resume.md) | TTS resume 范围与实现对照 |
| [runner-exit-cancel-fix.md](runner-exit-cancel-fix.md) | 取消终态 `runner_exited` 问题记录 |
| [gateway-retryable-retry.md](gateway-retryable-retry.md) | Gateway 可重试错误 |
| [capability-timeout-retries.md](capability-timeout-retries.md) | capability 超时/重试 |
| [cancel-signal-gateway-check.md](cancel-signal-gateway-check.md) | cancel.flag 与 gateway 检查点 |
| [url-video-download-ytdlp.md](url-video-download-ytdlp.md) | URL 视频下载 Lite 版（**分支已实现，待验收**；含已知问题与路线图） |
| [free-video-downloader-analysis.md](free-video-downloader-analysis.md) | free-video-downloader 下载实现调研 |
| [video-ingest-port-plan.md](video-ingest-port-plan.md) | 移植 video_ingest（Phase A/B/C：元数据优先 → Python 引擎 → downloading Job） |
| [archive/](archive/) | 历史计划、checklist、模块设计归档 |

当前生产合同见 [../reference/phase2-lite.md](../reference/phase2-lite.md)。
