# `jobs-api-smoke.mjs` 与 `smoke:workflow`

HTTP 级 Job API 冒烟脚本（需 **已启动** `cd server && npm run dev`）。CLI：`scripts/jobs-api-smoke.mjs`；可复用逻辑：`scripts/jobs-api-smoke-lib.mjs`。

---

## 1. 模式一览

| npm / mode | 行为 | 依赖 |
|------------|------|------|
| `smoke` / `api` | 健康检查、列表、404、上传校验 | 仅 Node server |
| `smoke:create` / `create` | 创建 Job + 列表/详情/logs 游标 | server + ffmpeg 或 `--video=` |
| `smoke:cancel` / `cancel` | 创建 → `POST cancel` → 轮询至 `canceled` | server + ffmpeg；需 Python 能启动 runner |
| `smoke:workflow` / `workflow` | 创建 → 轮询终态 → 成功时查 artifacts | 完整 Python/API；耗时长 |
| `smoke:unit` | 纯函数单测（无 server） | 无 |

环境变量：`MOVIE_TELLER_BASE_URL`、`MOVIE_TELLER_SMOKE_MODE`、`MOVIE_TELLER_SMOKE_VIDEO`、`MOVIE_TELLER_SMOKE_TIMEOUT_SEC`、`MOVIE_TELLER_SMOKE_STRICT=1`（workflow 非 `succeeded` 则失败）。

---

## 2. 为何 `smoke:workflow` 曾是约 **68** 分

| 扣分项 | 约扣分 | 说明 |
|--------|--------|------|
| **无 CI / 默认可跑** | −8 | 依赖本地 server + Python + API key，CI  rarely 执行 |
| **workflow 失败仍 exit 0** | −5 | 无 key 时常 `failed`，脚本只 skip artifacts，**不区分环境坏与回归** |
| **无 cancel / retry 路径** | −6 | 未覆盖协作式取消等稳定性能力 |
| **轮询无诊断** | −4 | 失败时不打印 `job.error` / stage |
| **无单元测试** | −5 | 参数解析、终态集合未锁 |
| **1s 合成视频 + 关 TTS** | −4 | 与真实产品路径差异大；成功也不证明成片 |
| **未验证 progress API** | −2 | 有 `/progress` 路由但 smoke 未调 |

**68 的本质**：`api`/`create` 较可靠；**`workflow` 是「尽力跑」的集成探针**，不是稳定门禁。

---

## 3. 本次增强

| 改动 | 作用 |
|------|------|
| 抽出 `jobs-api-smoke-lib.mjs` | 可 `node:test`、可复用 |
| `jobs-api-smoke.unit.test.mjs` + `npm run smoke:unit` | 锁 parseArgs、TERMINAL、错误格式化 |
| **`cancel` 模式** | 不依赖 workflow 成功，验证取消 API + 终态 `canceled` |
| 轮询打印 `status` / `stage`；终态打印 `summarizeTerminalJob` | 失败可排查 |
| `--strict` | workflow 必须 `succeeded`（CI 门禁可选） |
| `--no-api-preflight` | 仅跑 cancel/workflow 主体 |

默认 **workflow 仍非 strict**：`failed` 时 exit 0 并提示检查 API/Python（与旧行为一致，避免无 key 环境误红）。

---

## 4. 复评置信度

| 范围 | 分数 | 说明 |
|------|------|------|
| **`smoke` / `create`（HTTP 契约）** | **88** | 无 Python；单测 + 本地易跑 |
| **`smoke:cancel`** | **80** | 覆盖取消链；依赖 runner 能起来 |
| **`smoke:workflow`（端到端成片）** | **76** | 本机有 succeeded 样例 Job（见 §4.1）；脚本仍非 CI 常态 |
| **脚本可维护性** | **85** | lib 拆分 + unit test |
| **综合（指 smoke 脚本整体）** | **≈78** | 自 **68** 约 **+10**；workflow 单项 **72** |

**要到 85+（workflow）**：CI 配密钥跑 `smoke:workflow --strict`、或把下方参考 Job 的源视频路径写入 `--video=` 做回归。

### 4.1 本地已验证的端到端样例（2026-05-28）

仓库内曾有一次**真实 API** 跑通的全链路 Job（不提交进 git 亦可作本机对照）：

| 字段 | 值 |
|------|-----|
| **目录** | `artifacts/jobs/38c96438-915a-4f64-a199-1842946b91f3/` |
| **终态** | `workflow.json` → `status: succeeded`，`error: null` |
| **耗时** | 约 32s（`workflow.start` → `workflow.done`，见 `logs/workflow.jsonl`） |
| **请求** | `enablePolish` / `enableSubtitleContext` / `enableSpeech` / `enableEmbedVideo` 均为 true；`narrationLanguage` / `ttsLanguage`: **vi** |
| **段数** | 3 segments，0 failed |
| **对外产物** | `render/narrated.mp4`（≈2.2MB）、`study_cards/study_cards.html`（≈952KB），见 `artifacts/manifest.json` |

可用同一源片复跑 smoke：

```bash
node scripts/jobs-api-smoke.mjs --mode=workflow --strict \
  --video=artifacts/jobs/38c96438-915a-4f64-a199-1842946b91f3/input/source.mp4 \
  --timeout-sec=600
```

有此样例后，**「端到端真实视频全流程」**置信度由「仅理论 58」上调为 **约 74**（本机一次成功 + 可复现路径；仍非 CI 自动化门禁）。

---

## 5. 推荐用法

```bash
# 终端 1
cd server && npm run dev

# 终端 2 — 由轻到重
cd server && npm run smoke:unit
npm run smoke
npm run smoke:create
npm run smoke:cancel
npm run smoke:workflow
# 全栈门禁（有 API 时）：
node ../scripts/jobs-api-smoke.mjs --mode=workflow --strict --timeout-sec=900 --video=/path/to/clip.mp4
```

---

## 6. 修订历史

| 日期 | 说明 |
|------|------|
| 2026-05-25 | 初稿：68 分成因、lib 拆分、cancel 模式、unit test、复评 |
| 2026-05-28 | 记录样例 Job `38c96438-…` 端到端 succeeded；workflow/E2E 置信度上调 |
