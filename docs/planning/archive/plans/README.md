# MovieTeller 模块计划索引

总览与子模块关系说明：以 Cursor 中的「三模块需求与开发计划」为准（可与本目录计划并行维护）；若需入库总览可后续增加 `pipeline-overview.plan.md`。

各模块**单独计划文件**：

| 模块 | 计划文件 | 状态 |
|------|----------|------|
| **Configuration（配置，跨模块）** | [config-module.plan.md](config-module.plan.md) | 已建立 |
| Narration（视频理解 / 旁白文本） | [narration-module.plan.md](narration-module.plan.md) | 已建立 |
| Subtitle extraction（本地字幕提取） | [subtitle-extraction-module.plan.md](subtitle-extraction-module.plan.md) | 待补充 |
| Subtitle analysis（字幕间隙分析） | [subtitle-analysis-module.plan.md](subtitle-analysis-module.plan.md) | 待补充 |
| Subtitle context（台词语义上下文） | [subtitle-context-module.plan.md](subtitle-context-module.plan.md) | 已建立 |
| Frame pool（分镜检测与约束抽帧） | [分镜检测与约束抽帧_1a0e9bc7.plan.md](分镜检测与约束抽帧_1a0e9bc7.plan.md) | 原始方案 |
| Frame pool（分镜检测与约束抽帧实施版） | [分镜检测与约束抽帧-实施版.plan.md](分镜检测与约束抽帧-实施版.plan.md) | 已整理 |

**依赖顺序**：实现视频理解（Narration）前，宜先落地 **Configuration**（或由 Narration 第一期并行实现 `movieteller_config`，见 [config-module.plan.md](config-module.plan.md) §6）。

将上述「待补充」文件与总计划 §2 对应章节同步编写即可。
