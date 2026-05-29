# Gateway `execute_with_retry` 与 retryable 过滤

本文说明 **model_gateway** 中 `execute_with_retry` + `is_retryable_exception` 的设计、为何曾评估为约 **75** 置信度、调研中发现的问题，以及修复与测试后的提升。

日常配置见 [local-development.md §11](./local-development.md#11-稳定性超时--重试--重跑) 与 `config/local.yaml.example` 中的 `capability_retries`。

---

## 1. 能力范围

| 组件 | 路径 | 职责 |
|------|------|------|
| `execute_with_retry` | `python/model_gateway/src/model_gateway/policies.py` | 对 `fn()` 最多调用 `max_attempts` 次；非 retryable 立即抛出 |
| `is_retryable_exception` | 同上 | 决定是否值得再试 |
| `classify_error` | `python/movieteller_logging/src/movieteller_logging/errors.py` | 从异常**类型 + 消息字符串**推导 `error_code` / `retryable` |
| Facade | `python/model_gateway/src/model_gateway/facade.py` | chat / embedding / TTS 在 adapter 外包一层 `execute_with_retry`，`max_attempts` 来自 `capability_retries` |

**不在此范围**：Job 级 `POST /retry`、pipeline stage 的 `stage_executor.retryable`、workflow artifact resume。

---

## 2. 为何曾是约 75 分（低置信）

### 2.1 设计表面合理

```text
capability_retries.tts: 2  → 最多 2 次调用
adapter 抛错 → classify_error → retryable?
  是 → 再试
  否 → 立即失败（如 401）
```

文档与配置齐全，且已有 2 条 `test_policies.py` 用例（401 ValueError 不重试、Timeout 重试）。

### 2.2 扣分原因（约 75 的构成）

| 扣分项 | 约扣分 | 说明 |
|--------|--------|------|
| **Gateway 类型异常未单独处理** | **−8** | `GatewayConfigError` 等经 `classify_error` 常落入 `internal_error` → **被误标为可重试** |
| **分类完全依赖字符串** | **−5** | SDK 异常类型多样；`ValueError` 一律 `invalid_request`，与消息里的 `401` 无关 |
| **Facade 无重试用例** | **−4** | 单测只覆盖 policies 层，未验证 `_generate_chat` 等是否真会二次调用 adapter |
| **`classify_error` 矩阵单薄** | **−3** | movieteller_logging 仅 2 条（500、401），429/timeout/404 未锁 |
| **无生产/SDK E2E** | **−5** | 真实 OpenAI/DashScope 限流、断连未观测 |

**75 分的本质**：重试**框架**存在且有两条 happy path 单测，但 **Gateway 一等公民异常与 Facade 集成未验证**，且存在「配置错误仍重试」的**反例**。

### 2.2 修复前的危险路径（示例）

```python
# adapter 内
raise GatewayConfigError("speech output_path is required")

# classify_error → error_type GatewayConfigError → code internal_error → retryable True
# execute_with_retry → 再试 2～3 次，浪费且日志误导
```

---

## 3. 修复后方案（当前约 **87** 分，2026-05-25 复评）

### 3.1 `is_retryable_exception` 分层

```text
1. GatewayConfigError / GatewayUnsupportedCapabilityError / GatewayAuthError → 永不重试
2. GatewayTimeoutError / GatewayRateLimitError / GatewayTransientError → 始终重试
3. 其它 GatewayError（含 GatewayProviderError）→ classify_error(消息)
4. 其它异常 → classify_error
```

这样 **类型明确的配置/能力错误** 不再依赖脆弱字符串。

### 3.2 `classify_error` 仍负责

- 裸 `RuntimeError` / `TimeoutError`（adapter 包装前）
- `GatewayProviderError("HTTP 500 ...")` 等带 provider 文案的错

可重试 `error_code` 集合（`movieteller_logging.errors._is_retryable`）：

- `provider_500`
- `provider_timeout`
- `provider_rate_limited`
- `internal_error`（**仅**对非 Gateway 配置类；Gateway 配置类已由上层拦截）

### 3.3 测试覆盖（修复后）

| 套件 | 内容 |
|------|------|
| `model_gateway/tests/test_policies.py` | 矩阵 11 类异常；耗尽次数；`max_attempts=1`；`GatewayConfigError` 不重试；Provider 500 重试 |
| `model_gateway/tests/test_facade.py` | chat / **TTS（volcengine）** 500 重试 1 次且 `meta.retry_count==1`；401 只调 1 次 |
| `movieteller_logging/tests/test_errors.py` | 429、timeout、ValueError→invalid_request |

运行（仓库根、完整 `PYTHONPATH` 或已 editable 安装各包）：

```bash
cd /path/to/MovieTeller
export PYTHONPATH="python/movieteller_config/src:python/movieteller_logging/src:python/pipeline_types/src:python/media_utils/src:python/model_gateway/src"
.venv/bin/python -m pytest \
  python/model_gateway/tests/test_policies.py \
  python/model_gateway/tests/test_facade.py \
  python/movieteller_logging/tests/test_errors.py -q
```

### 3.4 置信度评分（当前 **87 / 100**）

| 维度 | 分数 | 说明 |
|------|------|------|
| **逻辑正确性**（policies + 类型过滤） | **92** | `is_retryable_exception` 分层；Config/Auth 不重试；11 类矩阵 + 耗尽/`max_attempts=1` |
| **Facade 贯通**（`capability_retries` → 真实二次调用） | **88** | chat + TTS（volcengine）各 2 条（500 重试 / 401 不重试）；embedding / edge / dashscope 未测重试 |
| **分类器**（`classify_error`） | **85** | 5 条单测（500/401/429/timeout/ValueError）；仍靠字符串；`invalid_model_response` 等未锁 |
| **生产可观测**（真实 API、退避、CI 全绿） | **78** | 无 integration E2E；立即重试无退避；CI 未必常跑全量 pytest |
| **综合（加权）** | **≈87** | 以「Job 中 gateway 自动重试是否符合预期」为主场景 |

**相对 75 → 87 的 +12 来源（近似）**：

| 变化 | 约 +分 |
|------|--------|
| 修复 GatewayConfig 误重试 | +4 |
| policies 从 2 条扩到 18 条（含 11 类 parametrize） | +3 |
| Facade：chat 重试用例 | +2 |
| Facade：TTS 对称用例 | +2 |
| `classify_error` 扩测 | +1 |
| 仍缺项（E2E、退避、embedding Facade） | −（封顶不到 90） |

### 3.5 与上一档（82～85）的差异

增补 **TTS Facade 对称用例** 后，**Facade 贯通**子分从约 84 提到 **88**，综合由 **82～85** 上调至 **87**。未达 90 的主因未变：无真实 provider、无指数退避、embedding 重试路径未在 Facade 层单测。

**未到 90+ 的剩余缺口**：

| 缺口 | 约影响 |
|------|--------|
| 无真实 OpenAI/DashScope/Volc 取消与 429 手测 | −3～5 |
| 无指数退避 | −2 |
| `_embed_texts` 无 Facade 重试用例 | −1～2 |
| TTS 仅 volcengine 路径；edge/dashscope 重试未测 | −1 |
| 未知文案 `GatewayProviderError` → 可能 `internal_error` 重试 | −1 |

---

## 4. 修复前后对照

| 维度 | 修复前（~75） | 当前（~87） |
|------|----------------|-------------|
| GatewayConfigError | 可能当 `internal_error` **重试** | **永不重试** |
| GatewayTimeoutError 等 | 依赖消息里是否含 timeout | **类型即重试** |
| Facade 行为 | 未测 | chat + TTS 各 500/401 用例 |
| 单测数量 | policies 2 条 | policies **18**（含矩阵）+ facade **4** + errors **5** |
| 监控字段 | `retry_count` 在成功路径写入 meta | 同上，chat/TTS 有 `retry_count` 断言 |
| **综合置信度** | **75** | **87** |

---

## 5. `execute_with_retry` 行为摘要

```python
for attempt in 1..max_attempts:
    try:
        return fn(), attempt - 1   # 第二项为 retry_count（成功前的重试次数）
    except Exception as exc:
        if attempt >= max_attempts: raise
        if not is_retryable(exc): raise
```

- `max_attempts` 来自 `settings.capability_max_attempts(capability)`，默认 **2**（即最多 2 次调用，1 次重试）。
- `is_retryable=None` 时会重试所有异常（当前 Facade **未**使用此模式）。

---

## 6. 仍不足以达到 95+ 的缺口

| 缺口 | 建议 |
|------|------|
| 无指数退避 / jitter | 429 连打可能加剧限流 |
| `GatewayProviderError` 空消息 → `internal_error` 可重试 | adapter 应尽量带 HTTP 码或改用 typed 子类 |
| embedding Facade 重试未单独测 | 可为 `_embed_texts` 加与 chat 对称用例 |
| 真实 API 集成测试 | marker `integration`，CI 默认跳过 |

---

## 7. 修订历史

| 日期 | 说明 |
|------|------|
| 2026-05-25 | 初稿：75 分成因、Gateway 类型过滤修复、扩展单测 |
| 2026-05-25 | 增补 TTS Facade 对称用例（volcengine 500 重试 / 401 不重试） |
| 2026-05-25 | 复评综合置信度：**87**（子维度表 + 75→87 归因） |
