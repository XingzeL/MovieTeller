# 数据库保存规划

本文记录 M7 阶段的数据库落地计划。它建立在当前 Phase 2 Lite 之上：`jobs` 已经作为 Job 控制面，产物仍保存在本地 `artifacts/jobs/{jobId}/`。

目标是继续把用户、套餐、额度、使用记录和学习卡 HTML 纳入 Postgres；源视频、成片、帧池、音频和中间文件仍然只放磁盘。

## 设计原则

| 原则 | 说明 |
|------|------|
| 控制面进 Postgres | 用户可见状态、权限、队列、额度、使用记录 |
| 大文件不进数据库 | 源视频、成片、帧池、音频和中间 JSON 仍放磁盘 |
| 学习卡 HTML 例外 | Python 仍写文件，Worker 终态后把 HTML 正文同步到 Postgres |
| Python 不直连数据库 | Python 仍只写 `workflow.json`、日志和产物文件 |
| 使用记录独立保存 | 使用记录按自己的时间删除，不跟随 `jobs` 自动删除 |
| 额度防止用超 | 创建 Job 时先预占额度，成功后转为实扣，失败或取消后释放 |
| 小并发优先稳定 | 不引入支付回调、多 Worker 扩展或对象存储 URL |

## 当前基线

当前 `jobs` 表已经承担以下职责：

- 队列和执行：`status`、`attempt_id`、`claimed_*`、`last_heartbeat_at`、取消相关字段。
- 用户展示：`original_source`、`current_stage`、`progress`、`error_*`、`retryable`。
- 视频下载一次：`video_downloaded_at`、`video_purged_at`、`video_state_version`。
- 本地路径指针：`output_root`、`input_video_path`。

当前本地磁盘仍保存：

- `request.json`
- `workflow.json`
- `logs/*.jsonl`
- 源视频、成片、音频、帧池、学习卡文件

## M7a：Retention 对齐

当前 retention 只删除磁盘目录，不删除 Postgres 中的 `jobs` 行。这会导致 Dashboard 看到已经没有文件的旧任务。

新增 `purgeOldJobsFromDb(maxAgeDays)`，与磁盘删除使用同一个时间窗口，默认 3 天。

删除顺序锁定为：

```text
1. 从 jobs 查询需要删除的终态 Job
2. 对每个 Job 先删除磁盘目录
3. 磁盘删除成功后，再删除 jobs 行
4. jobs 删除时自动删除 job_study_cards
5. usage_ledger 独立按 created_at 删除，不依赖 jobs 自动删除
6. 磁盘删除失败时保留 jobs 行，记录日志，下次继续重试
```

禁止两种做法：

- 先删数据库再删磁盘，但没有孤儿目录清理。
- 先删磁盘后数据库失败，却没有下次重试。

可选低频补偿：

```text
如果发现磁盘目录存在，但数据库已经没有对应 jobs 行，则删除该孤儿目录。
```

## M7a：jobs 新增字段

计划给 `jobs` 增加：

| 字段 | 说明 |
|------|------|
| `source_duration_sec` | 用户上传原视频时长 |
| `processed_duration_sec` | 创建时锁定的计划处理时长 |
| `quota_clip_applied` | 是否因为套餐限制发生裁剪 |
| `quota_policy` | 创建时的套餐和限制快照 |
| `reserved_minutes` | 当前 Job 预占的额度分钟数 |
| `billing_finalized_at` | 终态扣费或释放是否已经完成 |

`processed_duration_sec` 表示“计划处理时长”，不是裁剪输出文件的最终探测时长。后续如果需要精确对账，可以再增加实际输出时长字段。

## M7b：用户、套餐和余额表

新增表：

- `users`
- `plans`
- `user_subscriptions`
- `user_balances`
- `user_daily_usage`

`users.id` 使用 Clerk 用户 id，与当前 `jobs.user_id` 一致。

迁移策略：

```text
1. 创建 users 表
2. 从已有 jobs 中 SELECT DISTINCT user_id 回填 users
3. 新登录或首次创建 Job 时 upsert users
4. 第一阶段 jobs.user_id 保持 TEXT，不加数据库外键
5. 新表可以引用 users
```

这样可以避免已有 Job 数据导致迁移失败。

套餐种子数据：

| code | 名称 | 月费 | 月额度 | 单次上限 | 日上限 |
|------|------|------|--------|----------|--------|
| `free` | 免费 | ¥0 | 5 分钟 | 3 分钟 | 无独立日上限 |
| `lite` | Lite | ¥29 | 120 分钟 | 15 分钟 | 60 分钟 |
| `pro` | Pro | ¥59 | 300 分钟 | 30 分钟 | 120 分钟 |
| `max` | Max | ¥99 | 450 分钟 | 50 分钟 | 150 分钟 |

本期不接支付。价格字段只用于展示和后续扩展。

## M7b：创建 Job 前探测视频时长

创建 Job 时，Node 后端需要先拿到视频时长，再计算可处理范围。

计划：

```text
1. 上传文件先进入临时位置
2. 调用 ffprobe 获取视频时长
3. 探测失败时返回 video_probe_failed，不创建 Job
4. 探测超时时返回明确错误，不创建 Job
5. 无可靠时长时不得预占额度
```

实现上可以新增 `probeDurationSec`。它应有明确超时，例如 30 秒。错误码和返回状态需要写入 reference 文档。

## M7b：处理范围和裁剪

产品策略：

```text
超出套餐限制时，不拒绝整单，只处理额度内的前段视频。
```

分层：

| 层 | 职责 |
|----|------|
| Node API | 探测时长、读取套餐、计算 `startPoint` / `endPoint`、写入 `request.json` 和 `jobs` |
| Python job_runner | 在调用 `run_full_workflow` 前裁剪视频，并替换 `WorkflowRequest.video_path` |
| 下游流程 | 不知道裁剪这件事，只处理一个普通视频路径 |

`request.json` 新增字段：

| 字段 | 说明 |
|------|------|
| `startPoint` | 入点，本期默认 0 |
| `endPoint` | 绝对出点，单位秒 |

Python 只在 `job_runner/core.py` 前门使用这两个字段。进入 `run_full_workflow` 前应清空，避免下游阶段感知入出点。

无需裁剪时，继续使用 `input/source.mp4`。需要裁剪时，Python 写出 `input/processed.mp4`，下游只读该文件。

## M7b：额度预占

不能只在任务成功后扣额度。否则用户可以连续提交多个任务，让多个任务同时看到同一份余额。

锁定模型：

```text
创建 Job
  -> 懒刷新当前计费周期
  -> 锁住该用户的余额行和日用量行
  -> 计算 need = ceil(processed_duration_sec / 60)
  -> 检查 remaining_minutes - reserved_minutes 是否足够
  -> 如果有日上限，也检查日剩余额度是否足够
  -> 增加 user_balances.reserved_minutes
  -> 增加 user_daily_usage.reserved_minutes
  -> jobs.reserved_minutes = need
  -> 插入 queued Job

Job succeeded
  -> reserved 减少
  -> remaining_minutes 减少
  -> daily consumed 增加
  -> 写使用记录
  -> jobs.reserved_minutes = 0
  -> jobs.billing_finalized_at = now()

Job failed / canceled
  -> reserved 减少
  -> 写一条 0 扣费使用记录
  -> jobs.reserved_minutes = 0
  -> jobs.billing_finalized_at = now()
```

终态扣费或释放必须只能执行一次。

建议加 `jobs.billing_finalized_at`，并在扣费或释放时使用条件：

```text
WHERE job_id = ?
  AND billing_finalized_at IS NULL
```

使用记录也应加唯一约束，防止同一个 Job 写多条终态记录。

## M7b：创建失败补偿

数据库事务不能自动回滚磁盘文件，所以创建 Job 必须明确补偿步骤。

要求：

```text
额度预占失败
  -> 删除临时上传文件
  -> 不创建任务目录

文件写入失败
  -> 释放已预占额度
  -> 删除任务目录

插入 jobs 失败
  -> 释放已预占额度
  -> 删除任务目录

写 request/workflow 失败
  -> 释放已预占额度
  -> 删除任务目录
```

预占和插入 `jobs` 应放在同一个数据库事务里。磁盘失败时，通过显式 SQL 释放预占。

## M7b：计费周期刷新

不能只依赖定时任务刷新月度额度。上线前必须有懒刷新。

在这些入口调用 `ensureActiveBillingPeriod(userId)`：

- `POST /api/jobs`
- `GET /api/usage`
- 读取用户余额

遇到周期过期时：

```text
如果用户没有 queued/running/canceling Job：
  -> 重置 remaining_minutes = plan quota
  -> 清零 reserved_minutes
  -> 推进 period_start / period_end

如果用户还有未完成 Job：
  -> 暂不刷新周期
  -> 返回当前周期数据
  -> 等任务终态后下一次再刷新
```

这是上线前风险最小的策略。

## M7c：使用记录表

新增 `usage_ledger`，也就是使用记录表。

它记录用户每次任务对额度的影响：

- 哪个用户
- 哪个任务
- 哪个视频
- 原视频时长
- 计划处理时长
- 扣了多少分钟
- 扣完还剩多少
- 任务状态
- 记录时间

建议字段：

| 字段 | 说明 |
|------|------|
| `id` | 主键 |
| `user_id` | 用户 id |
| `job_id` | 可为空，引用 `jobs`，任务删除后设为空 |
| `job_id_snapshot` | 冗余保存任务 id 字符串 |
| `created_at` | 记录时间 |
| `video_name` | 视频名称 |
| `source_duration_seconds` | 原视频时长 |
| `processed_duration_seconds` | 计划处理时长 |
| `consumed_minutes` | 成功时扣费分钟；失败或取消为 0 |
| `remaining_after` | 扣费后的余额 |
| `status` | `succeeded` / `failed` / `canceled` |

`job_id` 使用：

```sql
ON DELETE SET NULL
```

不要使用跟随 `jobs` 自动删除的规则。使用记录按自己的 `created_at` 删除。

删除规则：

```text
DELETE FROM usage_ledger
WHERE created_at < cutoff
```

## M7d：使用记录 API 和前端

新增：

```text
GET /api/usage?limit=&offset=
```

返回：

```text
records: 最近 3 天使用记录
summary:
  remainingMinutes
  consumedInPeriod
  succeededCount
```

前端 `UsageHistoryPage` 替换当前 mock 数据。

注意文案：

- 列表是近 3 天。
- 余额和本周期消耗是当前计费周期。
- 不要把“近 3 天列表”误写成“完整本月流水”。

Job 卡片可以展示：

```text
原视频 N 分钟
按套餐处理前 M 分钟
```

## M7e：学习卡 HTML 入库

新增 `job_study_cards` 表：

| 字段 | 说明 |
|------|------|
| `job_id` | 主键，引用 `jobs`，任务删除时一起删除 |
| `html` | 完整 HTML 正文 |
| `byte_size` | HTML 字节数 |
| `stored_at` | 写入时间 |
| `source_path` | 原始磁盘路径，可选 |

写入方式：

```text
Python 成功导出学习卡文件
Worker 终态 reconcile 时读取学习卡 HTML
UPSERT 到 job_study_cards
读取失败时 Job 仍可 succeeded，但记录日志
```

读取方式需要新增统一模块，例如 `resolveStudyCardsArtifact`：

| 调用方 | 行为 |
|--------|------|
| `listJobArtifacts` | 数据库有 HTML 或磁盘文件存在时返回学习卡条目 |
| `jobAvailability.canOpenStudyCards` | 使用同一判断，不能只看磁盘 |
| `GET .../studyCardsHtml` | 优先读数据库，旧 Job 回退磁盘 |
| inline / download | 共用同一读取逻辑 |

测试要求：

- 数据库有 HTML，磁盘文件已删，仍可打开。
- 数据库没有 HTML，磁盘文件存在，旧 Job 仍可打开。
- 数据库和磁盘都有时，优先读数据库。

需要确认学习卡 HTML 是否完全自包含。如果 HTML 里引用 `frame_pool/` 图片，磁盘删除后数据库 HTML 可能缺图。本期可以先记录风险，但实现时应检查。

## 推荐迁移拆分

| 文件 | 内容 |
|------|------|
| `002_jobs_retention_and_duration.sql` | jobs 增加时长、裁剪、预占、扣费完成字段 |
| `003_billing_plans.sql` | users、plans、subscriptions、balances、daily usage 和种子数据 |
| `004_usage_ledger.sql` | 使用记录表 |
| `005_job_study_cards.sql` | 学习卡 HTML 表 |

## 推荐实现顺序

1. M7a：jobs 新字段 + DB retention。
2. M7b：用户、套餐、余额、周期懒刷新。
3. M7b：ffprobe 时长探测。
4. M7b：创建 Job 时额度预占。
5. M7b：Python 前门裁剪。
6. M7c：终态扣费/释放 + 使用记录表。
7. M7d：使用记录 API 和前端页面。
8. M7e：学习卡 HTML 入库和读取统一逻辑。

## 验收测试

必须覆盖：

- 已有 `jobs` 数据时，迁移可以执行。
- 同一用户并发创建多个 Job，额度不会用超。
- 预占后创建失败，额度会释放，任务目录会清理。
- 同一个 Job 终态处理跑两次，只扣一次或只释放一次。
- 任务失败或取消后，预占额度会释放。
- 周期过期但仍有未完成任务时，不会清零正在使用的预占额度。
- 磁盘删除失败时保留数据库行，下轮可以重试。
- 数据库删除失败时不会永久产生幽灵任务。
- 使用记录独立删除，不跟随 `jobs` 自动删除。
- 学习卡仅数据库、仅磁盘、数据库和磁盘都有三种路径都能工作。
- ffprobe 失败、超时、正常视频、超长视频都覆盖。

## 本期不做

- 支付回调。
- 多 Worker 扩展。
- 对象存储和外部下载 URL。
- 集中审计表。
- 成片、音频、帧池等大文件入库。
- 无数据库模式下的使用记录功能。

