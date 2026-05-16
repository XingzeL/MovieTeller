# Unified Gateway Config Refactor Plan

## Purpose

这份文档把“统一走 `newapi`，功能模块不再感知 provider/model”的改造目标拆成可执行实施计划。

目标：

- 功能模块不再感知 `provider`
- 功能模块不再感知 `model`
- `model_gateway` 成为唯一模型路由入口
- 配置从“按模块维护 provider/model/index/catalog”收敛为“统一连接信息 + capability 默认模型”
- 保持分阶段兼容，避免一次性重写所有模块

---

## Target Architecture

### Layering

```text
business modules
  narration
  narration_polish
  narration_speech
  subtitle_context
  movie_pipeline
        |
        v
model_gateway capability facade
        |
        +--> capability router
        +--> model resolver
        +--> endpoint resolver
        +--> provider adapter
```

### Ownership

功能模块负责：

- 组织业务输入
- 构造 prompt / multimodal payload / speech payload
- 消费 gateway 返回结果

`model_gateway` 负责：

- capability -> default model
- model -> provider endpoint
- provider endpoint -> request adapter
- 执行请求、重试、限流、遥测

`movieteller_config` 负责：

- 基础连接配置
- capability 默认模型
- 业务默认参数

---

## Target Config Schema

目标形态建议如下：

```yaml
default_prompt_style: movie_commentary

narration_polish_enabled: true
narration_tts_enabled: true

narration_polish_target_wpm: 250
narration_polish_cefr_level: B1
narration_polish_strength: medium
narration_polish_safety_margin_sec: 0.2

gateway:
  default_provider: newapi

api_providers:
  newapi: "http://127.0.0.1:3000/v1"

api_keys:
  newapi: "$NEW_API_KEY_NARRATION_FREE"

model_catalog:
  Qwen/Qwen3-VL-30B-A3B-Instruct: {}
  qwen2.5-7b-instruct: {}
  deepseek-v4-flash: {}
  qwen3-14b: {}
  qwen3-tts-flash: {}
  text-embedding-v4: {}

model_defaults:
  narration: "Qwen/Qwen3-VL-30B-A3B-Instruct"
  polish: "qwen2.5-7b-instruct"
  tts: "qwen3-tts-flash"
  embedding: "text-embedding-v4"

tts_defaults:
  voice: "Cherry"
  rate: "+0%"
  volume: "+0%"
  pitch: "+0Hz"
  boundary: "SentenceBoundary"

video_defaults:
  background_audio_volume: 0.35
  speech_audio_volume: 1.0
```

当前阶段默认所有模型经由 `newapi`，因此 `model_catalog` 可以先仅维护模型字符串白名单。

如果未来一个 model 可能映射到不同 provider，再扩展为：

```yaml
model_catalog:
  qwen3-tts-flash:
    provider: newapi
    capability: tts
```

---

## Old Config To Deprecate

以下旧字段应逐步淘汰：

- `narration_provider`
- `narration_polish_provider`
- `subtitle_context_embedding_provider`
- `narration_tts_provider`
- `narration_speech_provider`
- `narration_model`
- `narration_model_index`
- `narration_polish_model`
- `narration_polish_model_index`
- `narration_tts_model`
- `narration_tts_model_index`
- `narration_provider_models`
- `narration_provider_model_catalog`
- `narration_polish_provider_models`
- `narration_polish_provider_model_catalog`
- `tts_provider_model_catalog`
- `subtitle_context_embedding_model`
- `narration_speech_voice`
- `narration_speech_rate`
- `narration_speech_volume`
- `narration_speech_pitch`
- `narration_speech_boundary`

注意：

- 不要第一阶段就删除这些字段
- 先新增新 schema，再迁移调用，再清理旧字段

---

## New Public Runtime Contracts

### Business Modules Should Depend On Capabilities

业务模块只依赖 capability 级接口：

- `generate_narration(...)`
- `polish_text(...)`
- `synthesize_speech(...)`
- `embed_texts(...)`

业务模块不再直接构造：

- `ChatRequest(provider=..., model=...)`
- `EmbeddingRequest(provider=..., model=...)`
- `SpeechRequest(provider=..., model=...)`

低层 DTO 可以保留，但应逐步收缩到 gateway 内部使用。

### Business Modules Should Only Pass Business Params

`narration` 只传：

- prompt style
- custom prompt
- segment timing
- frames / context

`polish` 只传：

- text
- target_wpm
- cefr_level
- strength
- safety_margin_sec

`tts` 只传：

- text
- duration / target duration
- voice / rate / volume / pitch / boundary

`embedding` 只传：

- texts

---

## Refactor Strategy

采用三阶段迁移。

### Phase 1

新增新 schema 和 gateway 路由能力，不移除旧实现。

### Phase 2

逐个业务模块迁移到 capability-first gateway。

### Phase 3

删除旧 provider/model/index/catalog 逻辑。

---

## Phase 1: Add New Config Schema

### Goal

让 `movieteller_config` 能解析新配置结构，但保持旧字段兼容。

### Files

- `config/local.yaml.example`
- `python/movieteller_config/src/movieteller_config/schema.py`
- `python/movieteller_config/src/movieteller_config/loader.py`
- `python/movieteller_config/src/movieteller_config/config/default.yaml`
- `python/movieteller_config/tests/test_loader.py`

### Tasks

1. 在 `config/local.yaml.example` 中整理出新 schema 示例
2. 在 `Settings` 中新增新字段
3. 在 `settings_from_dict(...)` 中解析新字段
4. 在 env loader 中为新字段增加读取逻辑
5. 新增测试覆盖新字段解析

### New Settings Fields

建议新增：

- `gateway_default_provider: str`
- `api_providers: Mapping[str, str]`
- `model_catalog: Mapping[str, Mapping[str, Any]] | Mapping[str, Any]`
- `model_defaults: Mapping[str, str]`
- `tts_default_voice: str`
- `tts_default_rate: str`
- `tts_default_volume: str`
- `tts_default_pitch: str`
- `tts_default_boundary: str`

如果想先保持实现简单，也可以先 flatten 为：

- `narration_model_default`
- `polish_model_default`
- `tts_model_default`
- `embedding_model_default`

但长期更推荐 `model_defaults` map。

### New Methods

在 `Settings` 中新增：

- `default_provider() -> str`
- `default_model_for_capability(capability: str) -> str`
- `default_tts_voice() -> str`
- `default_tts_rate() -> str`
- `default_tts_volume() -> str`
- `default_tts_pitch() -> str`
- `default_tts_boundary() -> str`

### Compatibility Rules

在过渡期：

- 若新字段存在，优先使用新字段
- 若新字段缺失，回退旧字段

例如：

- `default_model_for_capability("narration")`
  - 优先 `model_defaults.narration`
  - 回退旧 `narration_provider` + `narration_model*` 体系

### Acceptance

- 新 schema 可被 `load_settings()` 正确读取
- 旧 schema 仍能运行
- 测试中能覆盖“新优先、旧回退”

---

## Phase 2: Add Capability-First Gateway API

### Goal

让 `model_gateway` 不再要求业务模块先传 `provider` 和 `model`。

### Files

- `python/model_gateway/src/model_gateway/router.py`
- `python/model_gateway/src/model_gateway/facade.py`
- `python/model_gateway/src/model_gateway/types.py`
- `python/model_gateway/tests/test_router.py`
- `python/model_gateway/tests/test_facade.py`

### Current Problem

当前 router 入口是：

- `resolve_chat_endpoint(request, settings)`
- `resolve_embedding_endpoint(request, settings)`
- `resolve_speech_endpoint(request, settings)`

这些接口假设：

- `request.provider` 已经由业务模块决定
- `request.model` 已经由业务模块决定

这与目标设计相反。

### New Router Responsibilities

新增两层解析：

1. capability -> default model
2. model -> provider/base_url/key/adapter

### New Router Functions

建议新增：

- `resolve_default_model(capability: str, settings) -> str`
- `resolve_model_provider(model: str, settings) -> str`
- `resolve_model_endpoint(model: str, capability: str, settings) -> ResolvedEndpoint`

当前阶段若全走 `newapi`，则：

- `resolve_model_provider(...)` 可直接返回 `settings.default_provider()`

### New Facade Functions

建议新增业务接口：

- `generate_narration(...)`
- `polish_text(...)`
- `synthesize_speech(...)`
- `embed_texts_for_capability(...)`

这些接口内部：

1. 读取 capability 默认模型
2. 解析 provider/base_url/key
3. 调具体 adapter

### DTO Strategy

保留底层 `ChatRequest` / `EmbeddingRequest` / `SpeechRequest`，但逐渐不让业务模块直接使用。

新增 capability-level DTO 或直接用 facade 参数。

### Speech Adapter Change

当前 speech adapter 在：

- `edge_tts`
- `volcengine_tts`

而未来你要统一走 `newapi`。

因此需要：

1. 把 `newapi` 作为支持的 speech provider
2. 或更进一步，取消 speech 的 provider 白名单，统一按默认 provider 走 OpenAI-compatible speech adapter

建议后者。

### Acceptance

- gateway 可在不显式传 provider/model 的情况下完成 4 类能力调用
- speech 支持 `newapi`
- 旧 facade 接口先保留兼容

---

## Phase 3: Migrate Narration Module

### Goal

`narration` 不再直接依赖 provider/model 配置。

### Files

- `python/narration/src/narration/story.py`
- `python/narration/src/narration/narrate.py`
- `python/narration/src/narration/cli.py`
- `python/narration/tests/test_narrate_mock.py`

### Current Problem

当前 narration 路径依赖：

- `settings.narration_provider`
- `settings.narration_options()`

### Target

`narration` 只负责：

- 帧采样
- prompt 组织
- 多模态消息构造

调用时直接使用：

- `gateway.generate_narration(...)`

### Tasks

1. 移除 `settings.narration_options()` 在业务层的主要责任
2. 将 `provider_slug` / `model` 从 narration 业务逻辑中抽走
3. 保留 prompt style / custom prompt 作为 narration 业务参数
4. 将 logging 中的 provider/model 来源改为 gateway 输出元信息

### Acceptance

- narration 在业务层不再读 `narration_provider`
- narration 测试仍通过

---

## Phase 4: Migrate Narration Polish Module

### Goal

`narration_polish` 只关心文本重写参数，不关心 provider/model。

### Files

- `python/narration_polish/src/narration_polish/polish.py`
- `python/narration_polish/src/narration_polish/cli.py`
- `python/narration_polish/tests/test_polish.py`

### Current Problem

当前 polish 路径依赖：

- `settings.narration_polish_options()`
- `narration_polish_provider`
- `narration_polish_model_index`

### Tasks

1. 让 `polish.py` 只接收文本和业务参数
2. 将模型选择迁移到 gateway
3. 保留 target_wpm / cefr / strength / safety_margin 的业务默认值逻辑
4. CLI 中的 model override 改成调试用途，而不是正常依赖

### Acceptance

- polish 模块业务代码不再读取 provider/model/index
- 可继续输出 `provider/model` 到结果 metadata，供调试追踪

---

## Phase 5: Migrate Subtitle Context Embedding

### Goal

embedding 调用不再从模块层读取 provider/model。

### Files

- `python/subtitle_context/src/subtitle_context/embedding.py`
- `python/subtitle_context/src/subtitle_context/index.py`
- `python/subtitle_context/tests/test_embedding.py`

### Current Problem

当前路径依赖：

- `subtitle_context_embedding_provider`
- `subtitle_context_embedding_model`

### Tasks

1. 把 `require_subtitle_context_embedding_model()` 的职责迁移到 gateway
2. `embedding.py` 改用 `gateway.embed_texts(...)`
3. `index.py` 中记录实际使用的 model 作为 metadata，而不是从 config 直接读

### Acceptance

- subtitle_context 业务层不再读 provider/model
- build metadata 仍能记录最终模型

---

## Phase 6: Migrate Narration Speech Module

### Goal

TTS 模块只关心文本和合成参数，不再自己解析 provider/model。

### Files

- `python/narration_speech/src/narration_speech/speech.py`
- `python/narration_speech/src/narration_speech/cli.py`
- `python/narration_speech/tests/test_speech.py`
- `python/model_gateway/src/model_gateway/adapters/edge_tts.py`
- `python/model_gateway/src/model_gateway/adapters/volcengine_tts.py`

### Current Problem

当前 TTS 设计存在两个问题：

1. `narration_speech_options()` 混合了解析 provider/model/voice
2. `tts_provider_model_catalog` 实际被当成 voice catalog

### Tasks

1. `speech.py` 只保留：
   - 文本
   - segment duration
   - target duration
   - voice/rate/volume/pitch/boundary
2. 默认 voice/rate/volume/pitch/boundary 从 `tts_defaults` 读取
3. model 由 gateway 通过 `model_defaults.tts` 决定
4. speech adapter 改成支持统一 `newapi`
5. 将 `edge_tts` 作为可选本地 adapter，而不是默认配置核心

### Acceptance

- `narration_speech` 业务层不再依赖 `narration_tts_provider`
- `newapi` TTS 可以走通
- `edge_tts` 仍可作为兼容或 fallback 路径

---

## Phase 7: Migrate Movie Pipeline

### Goal

`movie_pipeline` 只做流程编排，不再组装 provider/model-aware options。

### Files

- `python/movie_pipeline/src/movie_pipeline/pipeline.py`
- `python/movie_pipeline/src/movie_pipeline/full_workflow.py`
- `python/movie_pipeline/src/movie_pipeline/cli.py`
- `python/movie_pipeline/tests/test_pipeline_mock.py`

### Current Problem

pipeline 仍然从 `settings` 拉：

- `narration_options()`
- `narration_polish_options()`
- `narration_speech_options()`

### Tasks

1. 将 pipeline options 改造成业务参数容器
2. narration / polish / speech 的模型路由全部交给模块内部调用 gateway
3. `full_workflow.py` 不再显式组装 provider/model options
4. mock tests 改成 mock gateway capability 接口，而不是 mock provider-level request

### Acceptance

- pipeline 不再直接拿 provider/model
- full workflow 输出保持稳定

---

## Phase 8: Migrate Manual Tests And CLIs

### Goal

手动脚本和 CLI 只允许业务参数 override，模型 override 仅作调试用途。

### Files

- `python/manual_tests/*`
- `python/narration/src/narration/cli.py`
- `python/narration_polish/src/narration_polish/cli.py`
- `python/narration_speech/src/narration_speech/cli.py`
- `python/movie_pipeline/src/movie_pipeline/cli.py`

### Tasks

1. 清理脚本中对旧 provider/index 配置的依赖
2. 如需调试模型，统一使用显式 debug override 参数
3. 生产/常规路径默认只读 capability defaults

### Acceptance

- manual tests 默认路径不需要知道 provider/model/index
- CLI 仍保留调试入口

---

## Phase 9: Remove Legacy Schema

### Goal

删除旧字段与旧路由逻辑，完成收口。

### Files

- `python/movieteller_config/src/movieteller_config/schema.py`
- `python/movieteller_config/src/movieteller_config/loader.py`
- `python/movieteller_config/src/movieteller_config/config/default.yaml`
- `python/movieteller_config/tests/test_loader.py`
- `python/model_gateway/src/model_gateway/router.py`
- 受影响的 README / docs

### Tasks

1. 删除旧 Settings 字段
2. 删除旧 env 变量解析
3. 删除 `*_model_index` 测试
4. 删除 `*_provider_model_catalog` 测试
5. 删除旧 README 内容，更新到新 schema

### Acceptance

- 代码库不再依赖旧 provider/index/catalog 体系
- 文档只描述新 schema

---

## Detailed File-Level Checklist

### A. Config Layer

#### `config/local.yaml.example`

- 替换为新 schema 示例
- 增加 capability defaults
- 增加 `tts_defaults`
- 删除旧 provider/index/catalog 示例

#### `python/movieteller_config/src/movieteller_config/schema.py`

- 为 `Settings` 增加新字段
- 增加 capability default helpers
- 标记旧 helper 为 deprecated

#### `python/movieteller_config/src/movieteller_config/loader.py`

- 增加新配置读取逻辑
- 为 `model_defaults` 提供 env override 方案
- 保持旧字段兼容直到 Phase 9

#### `python/movieteller_config/tests/test_loader.py`

- 新增新 schema 解析测试
- 新增“新优先、旧回退”测试
- 保留旧测试直到删除旧 schema

### B. Gateway Layer

#### `python/model_gateway/src/model_gateway/router.py`

- 增加 capability router
- 增加 model resolver
- 把 `resolve_*_endpoint` 转成内部兼容层

#### `python/model_gateway/src/model_gateway/facade.py`

- 增加 capability-first facade
- 保留 raw facade 兼容

#### `python/model_gateway/src/model_gateway/types.py`

- 如有必要新增 capability request DTO
- 或在 facade 层直接以参数方式承载 capability 请求

#### `python/model_gateway/tests/test_router.py`

- 测试 capability -> model
- 测试 model -> endpoint
- 测试统一 `newapi` speech 路由

#### `python/model_gateway/tests/test_facade.py`

- 测试 capability-first facade 可工作
- 测试 narration/polish/tts/embedding 默认模型选择

### C. Business Modules

#### `python/narration/src/narration/story.py`

- 改为调用 capability-first narration gateway
- 删除 provider/model 决策逻辑

#### `python/narration_polish/src/narration_polish/polish.py`

- 改为调用 capability-first polish gateway
- 保留业务参数整形

#### `python/subtitle_context/src/subtitle_context/embedding.py`

- 改为调用 capability-first embedding gateway

#### `python/narration_speech/src/narration_speech/speech.py`

- 改为调用 capability-first speech gateway
- 默认 voice 走 `tts_defaults`

### D. Pipeline And Manual Tests

#### `python/movie_pipeline/src/movie_pipeline/full_workflow.py`

- 删除 provider/model-aware option 组装逻辑

#### `python/movie_pipeline/src/movie_pipeline/pipeline.py`

- 保留业务参数传递
- 将模型路由下沉

#### `python/manual_tests/full_video_workflow_harrypotter_long.py`

- 保持只关注文本产物与 speech/video 续跑逻辑
- 不再关心 provider/model

---

## Recommended Implementation Order

按这个顺序改风险最低：

1. `config/local.yaml.example`
2. `movieteller_config/schema.py`
3. `movieteller_config/loader.py`
4. `model_gateway/router.py`
5. `model_gateway/facade.py`
6. `subtitle_context/embedding.py`
7. `narration/story.py`
8. `narration_polish/polish.py`
9. `narration_speech/speech.py`
10. `movie_pipeline/full_workflow.py`
11. `movie_pipeline/pipeline.py`
12. manual tests / CLIs
13. 删除旧 schema

---

## Acceptance Checklist

最终验收应满足：

- 功能模块代码中不再读取 provider 字段
- 功能模块代码中不再读取 model/index/catalog 字段
- `gateway` 能根据 capability 自动选 default model
- 所有默认请求都统一走 `newapi`
- TTS 走统一 `newapi` 路由
- `edge_tts` 仅作为可选兼容路径
- `config/local.yaml.example` 只展示新 schema
- 旧 schema 清理完成后，README 与测试同步更新

---

## Notes

### About Provider

当前阶段“项目不用考虑 provider”的准确含义是：

- provider 不再暴露给功能模块和大多数配置项
- provider 退化为 gateway 内部实现细节
- 当前默认 provider 固定为 `newapi`

### About Model Override

建议保留调试用途的模型覆盖能力，但不作为业务模块默认依赖。

可允许：

- CLI `--model`
- manual test `MODEL_OVERRIDE`

但生产/常规代码路径不依赖这些 override。

