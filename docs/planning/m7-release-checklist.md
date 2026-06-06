# M7 发布清单（PR 拆分 + 上线注意）

## 上线前必做

1. 配置 `DATABASE_URL`（api / worker 模式必需）。
2. 确认 `ffprobe` 可用（与 `ffmpeg` 同目录或 PATH 中）。
3. 执行迁移：`cd server && npm run db:migrate`（应用 001→006）。
4. 跑回归：
   - `cd server && npm test`
   - `cd server && DATABASE_URL=... npm run test:db`
   - `cd client && npm run build`

## 迁移验证（三种库态）

自动化（共享开发库，`test/m7.db.test.js`）覆盖：

- `runMigrations` 可重复执行（幂等）。
- `schema_migrations` 含 001–006。
- `jobs` 含 M7 列（含 `reserved_usage_date`）。
- `006` 的 `ALTER ... IF NOT EXISTS` 可重复执行。

**建议在 staging 各做一次手工验证：**

| 库态 | 操作 | 期望 |
|------|------|------|
| 空库 | 仅配置 `DATABASE_URL`，`npm run db:migrate` | 001→006 全部应用，无报错 |
| 仅有 001 | 从 Phase2 快照恢复后 migrate | 002→006 成功，`users` backfill 自 `jobs` |
| 旧版 002（无 `reserved_usage_date`） | 只跑 migrate | 006 补列成功，已有 jobs 行保留 |

## 运行时合同

- **DB 不可用**：`POST /api/jobs`、`GET /api/usage` 等返回 **503**（fail fast）。
- **创建 Job**：ffprobe → 预占 → 写 DB → 写盘；盘失败则 `releaseQuota` + 删 job 行。
- **终态**：`finalizeBilling` 幂等（`billing_finalized_at`）；失败/取消释放预占，成功扣费。
- **Retention**：先删磁盘，再删 `jobs`；`usage_ledger` 独立按 `created_at` 删除。

## 上线后观察

- `jobs.reserved_minutes` 是否长期非零（预占泄漏）。
- `jobs.billing_finalized_at` 终态是否均非空。
- `usage_ledger` 与 Dashboard / Usage 页是否一致。
- 学习卡：盘删后 inline 是否仍 200（DB 优先）。

---

## PR 拆分建议

> 若代码已一次性落地，可按文件清单 cherry-pick / 分分支；或合并为 1–2 个大 PR 并在描述中标注逻辑块。

### PR-1：Retention + 迁移 002/006 + 迁移锁

- `server/db/migrations/002_*.sql`、`006_*.sql`
- `server/src/db/ensure.js`（advisory lock）
- `purgeOldJobsFromDb`、`purgeOrphanJobDirectories`、`purgeOldUsageLedger`
- `retentionPolicy.js`、`retentionScheduler.js`
- `jobsRepository` retention helpers
- `test/retention.scan.test.js`、`phase2-lite` retention 用例

**PR 描述要点：** 先删盘再删 DB；`usage_ledger` 独立 retention；006 为旧 002 补 `reserved_usage_date`。

### PR-2：用户 / 套餐 / 余额

- `003_billing_plans.sql`
- `plansRepository`、`usersRepository`、`balancesRepository`、`dailyUsageRepository`
- `ensureActiveBillingPeriod`、`upsertUserOnLogin`

### PR-3：创建时 ffprobe + 预占 + 补偿

- `probeDuration.js`、`resolveProcessingRange.js`、`reserveQuota.js`、`releaseQuota.js`
- `createJob.js` 重构
- `billing/errors.js`、`test/billing.reservation.test.js`

### PR-4：Python 裁剪

- `quota_clip.py`、`core.py`、`request_io.py`、`types.py`
- `tests/test_quota_clip.py`

### PR-5：终态结算 + usage API

- `004_usage_ledger.sql`
- `finalizeBilling.js`、`getUsageSummary.js`、`usageLedgerRepository.js`
- `routes/usage.js`、`dbJobSync.js`、queueWorker / jobQueue / forcedCancel 挂接
- `test/m7.db.test.js`（cancel finalize 用例）

### PR-6：前端

- `UsageHistoryPage.tsx`、`Dashboard.tsx`
- `client/src/types/job.ts`、`usage.ts`

### PR-7：学习卡 DB 优先

- `005_job_study_cards.sql`
- `studyCardsRepository.js`、`resolveStudyCardsArtifact.js`
- `artifactManifest.js`、`jobAvailability.js`、routes inline
- `test/m7.db.test.js`（DB-only study cards 用例）

### PR-8：文档

- `docs/reference/billing-and-usage.md`
- `job-lifecycle.md`、`phase2-lite.md`、`multi-user-data-model.md`
- 本文档 `m7-release-checklist.md`

---

## 合并 PR 时的 Test plan 模板

```markdown
## Test plan
- [ ] 空库 `npm run db:migrate`
- [ ] `npm test` / `DATABASE_URL=... npm run test:db`
- [ ] 创建短视频 Job，确认 `source_duration_sec` / 预占
- [ ] 超额上传确认裁剪（`quota_clip_applied`）
- [ ] 取消 queued Job，确认预占释放
- [ ] 成功 Job 后 `GET /api/usage` 有流水
- [ ] 学习卡 inline（可选：删盘后仍可读）
- [ ] `cd client && npm run build`
```
