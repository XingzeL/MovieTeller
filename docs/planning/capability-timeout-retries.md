# TTS / Embedding 的 `capability_timeouts` 与 `capability_retries`

本文说明配置如何进入 `model_gateway.facade`、各 adapter 是否真正执行超时/重试，以及置信度从约 **70** 提升的路径。

配置模板：`config/local.yaml.example`、`python/movieteller_config/src/movieteller_config/config/default.yaml`。

---

## 1. 配置 → 运行时

| YAML 键 | Settings API | Facade 使用 |
|---------|--------------|-------------|
| `capability_timeouts.tts` | `capability_timeout_sec("tts")` | `_synthesize_speech(..., capability="tts")` → `_with_capability_timeout` |
| `capability_timeouts.embedding` | `capability_timeout_sec("embedding")` | `_embed_texts(..., capability="embedding")` |
| `capability_retries.tts` | `capability_max_attempts("tts")` | `execute_with_retry(..., max_attempts=…)` |
| `capability_retries.embedding` | `capability_max_attempts("embedding")` | 同上 |

`_with_capability_timeout`：仅当 request 未设 `timeout_sec` 时，用 settings 中的 capability 值写入 request。

`embed_texts_for_capability` / `synthesize_speech_for_capability` 最终走 `_embed_texts` / `_synthesize_speech`，capability 默认为 **`embedding`** / **`tts`**，与 YAML 键名一致。

---

## 2. 为何曾是约 **70** 分

| 扣分项 | 约扣分 | 说明 |
|--------|--------|------|
| **embedding 未把 timeout 传给 SDK** | **−10** | `_with_capability_timeout` 写了 request，但 `openai_compatible.embed_texts` 忽略 `timeout_sec` |
| **edge / dashscope TTS 无超时** | **−6** | `capability_timeouts.tts` 对常用 adapter 无效 |
| **无 Facade 级 timeout/重试单测** | **−5** | 仅 chat 有部分 retry 测，未覆盖 tts/embedding |
| **无 schema 加载测** | **−3** | `capability_timeouts` 映射未单测 |
| **default.yaml 数值未验证** | **−2** | 180s/60s 是否合理无观测 |
| **无 E2E** | **−4** | 真实长 TTS 是否被切断未手测 |

**70 的本质**：配置与 facade **接线存在**，但 **embedding 超时是空操作**，TTS 超时 **因 adapter 而分裂**，测试未证明端到端生效。

---

## 3. 修复与现状（adapter 矩阵）

| Adapter | `capability_retries` | `capability_timeouts` |
|---------|----------------------|------------------------|
| **openai_compatible** chat | ✅ SDK `timeout` | ✅ |
| **openai_compatible** embedding | ✅ `execute_with_retry` | ✅ **已修**：`embeddings.create(timeout=…)` |
| **volcengine_tts** | ✅ | ✅ `kwargs["timeout"]` |
| **edge_tts** | ✅ | ✅ **已加**：`asyncio.wait_for` |
| **dashscope_tts** | ✅ | ❌ 仍未传超时（SDK 调用无 timeout 参数） |

重试过滤见 [gateway-retryable-retry.md](gateway-retryable-retry.md)（仅 `retryable` 错误）。

---

## 4. 测试（修复后）

| 文件 | 内容 |
|------|------|
| `movieteller_config/tests/test_capability_policy.py` | YAML → `capability_timeout_sec` / `capability_max_attempts` |
| `model_gateway/tests/test_facade_capability_timeouts.py` | `_with_capability_timeout`、embed timeout 传入 SDK、embed 500 重试、volcengine timeout、edge 超时失败 |

```bash
cd /path/to/MovieTeller
export PYTHONPATH="python/movieteller_config/src:python/movieteller_logging/src:python/model_gateway/src:..."
.venv/bin/python -m pytest \
  python/movieteller_config/tests/test_capability_policy.py \
  python/model_gateway/tests/test_facade_capability_timeouts.py -q
```

---

## 5. 复评置信度：**82 / 100**（2026-05-25）

| 维度 | 分数 | 说明 |
|------|------|------|
| **配置加载** | **92** | schema 单测 + default.yaml |
| **Facade 接线** | **90** | `_with_capability_timeout` / `max_attempts` 有单测 |
| **embedding 生效** | **88** | OpenAI SDK timeout + retry Facade 测 |
| **TTS 生效** | **80** | volcengine + edge 有测；dashscope 仍无超时 |
| **生产 E2E** | **72** | 无真实 180s TTS 手测 |
| **综合** | **≈82** | 自 **70** 约 **+12** |

**未到 90+**：dashscope 超时、TTS Facade 对称 retry（401/500）可再补；真实长音频与 subtitle_context 大批量 embedding 未 E2E。

---

## 6. 修订历史

| 日期 | 说明 |
|------|------|
| 2026-05-25 | 初稿：70 分成因、embedding timeout 修复、edge wait_for、单测与复评 82 |
