# Authentication Plan（真实登录，不引数据库）

本文档是 **PR-F 的执行合同**：用真实、后端可验证的身份替换 demo Cookie，**不改变** Job 文件存储、`jobAccess` ACL、manifest、下载一次策略或队列/runtime 形态。

与 [job-lifecycle.md](./job-lifecycle.md)、[multi-user-storage-and-transport.md](./multi-user-storage-and-transport.md) 配套阅读。

Clerk 本地注册/登录排障记录见 [clerk-signup-troubleshooting.md](./clerk-signup-troubleshooting.md)。

---

## 已锁定决策（PR-F v1）

以下在实施前已确定，**不再**在 PR-F 中摇摆。

| # | 决策 | 说明 |
|---|------|------|
| 1 | **Bearer token** 为第一版传递方式 | 前端从 Clerk 取 session token → `Authorization: Bearer <token>`；后端只验证 Bearer。Clerk **session cookie 同站传递**仅作未来备选（Vite :5173 + Express :3001 易踩 CORS/SameSite）。 |
| 2 | **`resolveUserId` 可返回 `null`** | 生产禁止「永远有 user」的 `demo-user` fallback。未登录 = `null` → `requireCurrentUser` 返回 **401**。 |
| 3 | **中间件拆分** | `resolveUserId` / `currentUserOptional` / `requireCurrentUser`；`/api/jobs`、`/api/generate`、`/api/extract` 使用 `requireCurrentUser`。 |
| 4 | **路由分层** | public → dev（非 prod）→ protected；避免 `/api/healthz` 被误保护。 |
| 5 | **两套 ID 规范化** | dev cookie/header 继续 `normalizeUserId`；Clerk 已验证 ID 用 `normalizeAuthUserId`（长度 + 危险字符，不套 dev 正则）。 |
| 6 | **`generate` / `extract` 一并要求登录** | 与 `/api/jobs` 相同 protected 策略。 |
| 7 | **生产 CORS** | 允许 `Authorization`；**不**允许 `X-MovieTeller-User-Id`。 |

---

## 目标与非目标

### 两条轨道（必须拆开）

| 轨道 | 目标 | 本计划 |
|------|------|--------|
| **A. 真实登录** | 注册/登录；`req.user.id` 来自已验证 Bearer | **PR-F** |
| **B. 用户持久化** | 用户资料、套餐、额度 | **不做**；见 [阶段 2/3](#阶段-3数据库化后置) |

### 本阶段目标

- Clerk 登录；Job 的 `workflow.json.user_id` = Clerk `userId`（稳定 sub）。
- 现有 `*ForUser` ACL 不变。
- 未登录访问 protected API → **401**。
- 跨用户 → **404**。

### 本阶段非目标

- Postgres、`users` 表、Job 目录迁移、Plan/Credits、自动合并 demo 历史 Job。

---

## 当前基线（Phase 1）

| 能力 | 实现 |
|------|------|
| Job owner | `workflow.json.user_id` |
| ACL | `jobAccess.*ForUser` |
| 创建 Job | 仅 `req.user.id`；body `userId` 已忽略 |
| 身份（临时） | `mt_uid` →（非 prod）header → **`demo-user`（PR-F 生产废除）** |
| Dev | `/api/dev/session`、`ensureDevSession`、`?asUser=` |

**原则**：只改身份解析与路由鉴权层，**不绕过** `jobAccess`。

---

## 认证传递：Bearer（v1）

```text
Browser (ClerkProvider, signed in)
  │  getToken() → session JWT
  │  apiFetch: Authorization: Bearer <token>
  ▼
Express
  │  clerkMiddleware / verify Bearer（仅 protected 路由）
  │  normalizeAuthUserId(auth.userId) → req.user.id
  ▼
jobAccess.*ForUser(req.user.id, ...)
```

**为何不用 Cookie session（v1）**

- 前端 Vite `localhost:5173`、API `localhost:3001` 分端口；Clerk session cookie + `credentials: 'include'` + SameSite 组合易出问题。
- Bearer 显式、易在测试里 mock、与生产行为一致。

**本地 dev（未配置 Clerk 时）**

- 仍可用 `mt_uid` / `POST /api/dev/session` / `X-MovieTeller-User-Id`（仅 non-production）。
- `apiFetch` 无 token 时不发 `Authorization`；`ensureDevSession` 见下文。

---

## 身份策略（生产 / 非生产）

### Production

| 来源 | 允许 |
|------|------|
| `Authorization: Bearer` + Clerk 验证 | **唯一** |
| Cookie `mt_uid` | **禁止** |
| `X-MovieTeller-User-Id` | **禁止**（CORS 也不暴露该 header） |
| body `userId` | **禁止** |
| `/api/dev/*` | **不注册** |
| `demo-user` 默认 | **禁止**；`resolveUserId` → `null` |

### Non-production

| 优先级 | 来源 |
|--------|------|
| 1 | Bearer + Clerk（若已配置） |
| 2 | Cookie `mt_uid` |
| 3 | `X-MovieTeller-User-Id` |
| 4 | `CLERK_BYPASS_USER_ID` |
| — | `POST /api/dev/session` |

ACL 测试继续用 Cookie；新增 mock Bearer / Clerk `req.auth` 测试。

---

## 中间件设计（替换「永远有 user」）

当前 [`currentUser.js`](../server/src/middleware/currentUser.js) 在链末返回 `demo-user`，**PR-F 后生产不得如此**。

### 建议 API

```text
resolveUserId(req): string | null
  production: 仅 Clerk Bearer 验证成功 → id；否则 null
  non-production: Clerk → cookie → header → bypass → null（不再默认 demo-user）

currentUserOptional(req, res, next)
  req.user = resolveUserId(req) ? { id } : null
  始终 next()（不 401）

requireCurrentUser(req, res, next)
  const id = resolveUserId(req)
  if (!id) return res.status(401).json({ error: "unauthorized" })
  req.user = { id }
  next()
```

### 用户 ID 规范化（两套）

| 函数 | 用于 | 规则 |
|------|------|------|
| `normalizeUserId` | dev cookie、`?asUser=`、测试 header | 现有 [`USER_ID_PATTERN`](../server/src/middleware/userId.js) |
| `normalizeAuthUserId` | Clerk 验证后的 `userId` | 非空字符串、长度上限（如 128）、禁止 `/` `\`、控制字符；**不**强行套用 dev 的 64 字符字母数字规则 |

`workflow.json.user_id` 存 **normalizeAuthUserId** 后的 Clerk id。

---

## 路由挂载（`app.js`）

**历史问题**：`/api` 全局挂用户中间件后再挂 `healthRouter`，若改成全局 require auth 会误伤 `/api/healthz`。

**PR-F 目标结构**：

```text
/health                          → public（无 auth）

/api/dev/*                       → non-production only；dev session / whoami
                                   （dev 路由内自行 currentUserOptional 或不需要）

/api/healthz/*                   → public（在 protected 之前注册）

/api/jobs、/api/generate、/api/extract
                                 → clerkMiddleware（若需要）+ requireCurrentUser + 业务路由
```

实现要点：

- **不要**在整条 `/api` 上挂 `requireCurrentUser`。
- protected 子路由分别挂载，或单独 `protectedApiRouter`。
- CORS：
  - **production**：`allowedHeaders: ["Content-Type", "Authorization"]`
  - **non-production**：可额外允许 `X-MovieTeller-User-Id`

---

## 前端

### `apiFetch`（[`apiClient.ts`](../client/src/api/apiClient.ts)）

```text
若有 Clerk session token → Authorization: Bearer <token>
否则（仅 dev）→ 依赖 mt_uid cookie（ensureDevSession 写入）
credentials: 'include' 可保留（dev cookie 路径）
```

### `ensureDevSession` — **仅 dev**

```text
import.meta.env.PROD → no-op（禁止 POST /api/dev/session）
dev 且无 Clerk token → 现有 ?asUser= / localStorage 逻辑
dev 且已登录 Clerk → no-op
```

调用方：Dashboard、Workspace、UploadPage、StudyCardPage、JobPanel — 生产路径不得触发 dev session。

### 其它

- `ClerkProvider` 包裹 App；保护 `/dashboard`、`/create`、`/jobs/*`、`/study-cards/*`。
- 公开路由：`/sign-in`（`SignIn`）、`/sign-up`（`SignUp`）；`SignIn` 的 `signUpUrl` 指向 `/sign-up`。
- Dashboard 显示 `useUser()`，非 “User Demo”。
- 受保护 Job 资源（缩略图、学习卡下载/内联预览）须 `apiFetch` + Blob/`srcDoc`；生产禁止裸 `<img src="/api/jobs/...">` 或 `<a href="/api/jobs/...">`（浏览器不会带 Bearer）。

---

## 推荐实施顺序（PR-F）

1. **本文档** — Bearer + nullable user 已锁定（本节）。
2. **后端身份中间件重构** — `resolveUserId` → `null`；`currentUserOptional` / `requireCurrentUser`；production 禁用 cookie/header/demo。
3. **Clerk server** — 验证 Bearer；`normalizeAuthUserId`。
4. **`app.js` 路由分层** — public / dev / protected；生产 CORS。
5. **前端** — `ClerkProvider`、路由保护、`apiFetch` Bearer、`ensureDevSession` dev-only。
6. **测试** — 见下表。
7. **文档同步** — `local-development.md`、`multi-user-storage-and-transport.md`（传输改为 Bearer）。

---

## 测试计划

| 场景 | 期望 |
|------|------|
| 未登录 `GET /api/jobs` | **401** |
| mock Clerk Bearer / `req.auth` 用户 A 创建 Job | `workflow.user_id` = A |
| 用户 B 访问 A 的 jobId | **404** |
| `NODE_ENV=production` + `X-MovieTeller-User-Id` | 不生效 / **401** |
| non-prod + `mt_uid` cookie | 现有 `jobs.acl.test.js` 仍绿 |
| production | `/api/dev/session` 未注册 |
| `GET /api/healthz`（或 deep） | 无需 Bearer 仍 **200** |

建议：`server/test/auth.clerk.test.js` + 保留 `auth.session.test.js`。

---

## 验收标准（PR-F Done）

- [x] Bearer 为唯一生产认证方式（文档与实现一致；已实现 `clerkBearer.js` + `apiFetch`）。
- [x] A/B 登录后 Job 互不可见；`user_id` 为 Clerk id（真实 Clerk 双账号手测通过）。
- [x] 未登录 protected API → **401**；跨用户 → **404**（自动测试 + 直接访问他人 Job 手测通过）。
- [x] 生产无法伪造身份；无 `/api/dev/session`。
- [x] `ensureDevSession` 在 production build 为 no-op。
- [x] public health 路由无需登录。
- [x] combined `npm run dev` 行为不变（临时端口 smoke：combined server、Vite、protected API 直链 401 均通过）。
- [x] non-prod cookie ACL 测试仍绿。

---

## 历史 Job 与迁移

| 类型 | PR-F 默认 |
|------|-----------|
| 无 `user_id` | 不迁移 |
| demo / 旧 `mt_uid` Job | **不自动**合并到 Clerk 账户 |

---

## 阶段 2：用户资料（后置）

最小：仅 Clerk `useUser()`。本地 `profile.json` 或 Postgres `users` 表 — **另 PR**。

---

## 阶段 3：数据库化（后置）

`users`、`jobs`、audit、credits — 见 [phase2-queue-design.md](./phase2-queue-design.md)、[multi-user-data-model.md](./multi-user-data-model.md)。

---

## 与 PR 批次关系

| 批次 | 说明 |
|------|------|
| A–C、D、D2 | 先合；与 auth 无关 |
| **F** | 本合同：Clerk + Bearer + 中间件/路由；不动 Job 存储 |

---

## 参考

- [Clerk Express](https://clerk.com/docs/quickstarts/express)
- [Clerk React](https://clerk.com/docs/quickstarts/react)
- [@clerk/backend authenticateRequest](https://clerk.com/docs/references/backend/authenticate-request)（Bearer 验证）
