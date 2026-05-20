---
name: Subtitle context 台词语义上下文模块
overview: 基于字幕文本构建“仅回看历史、不可剧透”的语义检索索引，为 narration 提供剧情背景补充。首版使用 embedding 模型 + 本地向量索引，不引入独立向量数据库服务。
isProject: false
---

# Subtitle context 模块

## 1. 目标

在现有链路中，`subtitle_analysis` 已经能够提供：

- 无台词时间窗
- `prev_subtitle_text`
- `next_subtitle_text`

但当前 narration 只真正利用了时间边界，没有利用台词文本语义。

本模块目标是：

1. 对字幕文本切片
2. 为切片生成 embedding
3. 构建本地检索索引
4. 在每个无台词段生成前，仅检索“当前时间点之前已经发生过的剧情片段”
5. 将其作为弱参考上下文提供给视觉 narration prompt

要求：

- 不剧透
- 不把未来剧情引入 prompt
- 不替代关键帧，只补充剧情理解

## 2. 模块边界

建议新建独立包：

- `python/subtitle_context/`

职责：

| 模块 | 职责 |
|------|------|
| `subtitle_extraction` | 提取 `.srt` / `cues` |
| `subtitle_analysis` | 找无台词时间窗、给出 `prev/next` |
| `subtitle_context` | 字幕切片、embedding、历史检索 |
| `video_frame_pool` | 关键帧 |
| `narration` | 组合 `prev/next/history/keyframes` 构造 prompt 并生成旁白 |

不建议把语义检索塞进：

- `subtitle_analysis`
- `narration`

因为它本身是独立的数据准备与检索层。

## 3. 是否需要向量数据库

首版不建议引入独立向量数据库服务。

### 3.1 首版需要的能力

- embedding 模型
- 本地向量索引
- 相似度检索
- 时间过滤

### 3.2 首版不需要的能力

- `qdrant`
- `milvus`
- `weaviate`
- `pgvector`

原因：

- 当前主要是单机开发
- 每个视频的字幕 chunk 数量有限
- 每视频本地索引即可满足需求

### 3.3 首版建议存储形式

每个视频一个目录，例如：

```text
harrypotter.subtitle_context/
  chunks.jsonl
  embeddings.npy
  build_config.json
```

因此，首版本质上是“本地向量检索模块”，不是“独立向量数据库系统”。

## 4. embedding 模型与依赖

## 4.1 一定需要

- embedding provider
- embedding model
- `numpy`
- 当前项目已有的 OpenAI-compatible client 能力

如果 embedding provider 也走 OpenAI-compatible 接口，则很可能可以直接复用现有 `openai` Python 包与 provider 配置机制。

## 4.2 首版依赖建议

最小依赖：

- `numpy`
- `openai`

可选增强：

- `faiss-cpu`

建议首版先不用 `faiss`，直接：

- `numpy` 向量矩阵
- cosine similarity

## 5. 配置方案

建议在 `movieteller_config` 中新增独立配置组。

### 5.1 模型配置

embedding 统一走网关 capability 路由：

| 配置项 | 说明 |
|------|------|
| `gateway.default_provider` | 默认 provider slug |
| `model_defaults.embedding` | embedding 默认模型 |

### 5.2 检索配置

建议新增：

| 配置项 | 默认值建议 | 说明 |
|------|------:|------|
| `subtitle_context_chunk_cue_count` | `5` | 每个 chunk 包含几句字幕 |
| `subtitle_context_chunk_stride` | `3` | chunk 滑动步长 |
| `subtitle_context_history_window_sec` | `600` | 仅检索当前片段开始前多久内的历史剧情 |
| `subtitle_context_top_k` | `6` | 语义检索 top-k |
| `subtitle_context_summary_enabled` | `false` | 首版可先关闭摘要压缩 |

## 6. 数据契约

### 6.1 chunk 结构

每条字幕语义 chunk 至少包含：

```json
{
  "chunkId": "000012",
  "startSec": 120.3,
  "endSec": 146.8,
  "text": "....",
  "cueCount": 5
}
```

### 6.2 检索结果结构

```json
{
  "queryText": "...",
  "segmentStartSec": 188.2,
  "historyWindowSec": 600,
  "chunks": [
    {
      "chunkId": "000012",
      "startSec": 120.3,
      "endSec": 146.8,
      "text": "...",
      "score": 0.82
    }
  ]
}
```

## 7. 不剧透约束

这是本模块最重要的规则，必须是硬约束。

假设当前无台词段是：

```text
segment = [T0, T1]
```

那么任何可被检索的字幕 chunk 必须满足：

```text
chunk.end_sec <= T0
```

并且：

```text
T0 - chunk.end_sec <= subtitle_context_history_window_sec
```

也就是说：

- 只能回看已经发生过的剧情
- 不能使用未来 chunk
- 不能因为 `next` 把未来剧情检索进来

## 8. 检索策略

### 8.1 首版建议

首版只用：

- `prev_subtitle_text`

作为主检索 query。

`next_subtitle_text` 可以保留在最终 prompt 里作为边界锚点，但不参与未来语义检索。

### 8.2 为什么不直接用 `next` 做检索

因为：

- `next` 代表当前无台词段之后马上出现的内容
- 它可以作为段落边界信息
- 但不能扩展成未来剧情召回，否则会剧透

## 9. Prompt 集成建议

最终 narration prompt 结构建议为：

```text
【剧情锚点（强约束）】
上一句台词：
{prev}

下一句台词：
{next}

【历史背景（弱参考，仅来自当前时间点之前）】
以下内容来自当前片段开始前已经发生过的剧情，仅用于帮助理解人物关系、情绪和事件背景：
{retrieved_history}

【画面信息（最高优先级）】
关键帧图像
```

必须写死的规则：

- 不要引入当前时间点之后才发生的信息
- 如果背景信息与画面冲突，以画面为准
- 不要把检索上下文直接复述成对白摘要

## 10. CLI 与 Python API

### 10.1 建索引 CLI

```bash
python -m subtitle_context \
  --srt harrypotter.extracted.srt \
  --output-dir harrypotter.subtitle_context \
  --json
```

### 10.2 Python API

```python
def build_subtitle_context_index(
    *,
    srt_path: str,
    output_dir: str,
    settings: Settings | None = None,
) -> SubtitleContextBuildResult:
    ...
```

```python
def retrieve_past_subtitle_context(
    *,
    index_dir: str,
    query_text: str,
    segment_start_sec: float,
    history_window_sec: float | None = None,
    top_k: int | None = None,
    settings: Settings | None = None,
) -> SubtitleContextRetrievalResult:
    ...
```

## 11. 实施阶段

### 第一阶段

- chunk 字幕
- 生成 embedding
- 写本地索引
- 支持历史检索
- 不做摘要压缩

### 第二阶段

- narration prompt 接入
- 将检索结果作为弱参考上下文

### 第三阶段

- 可选 summarize / rerank
- 可选 `faiss`
- 可选多视频索引

## 12. 测试建议

至少覆盖：

- chunk 切分正确
- embedding 数量与 chunk 数一致
- 过去时间过滤生效
- 未来 chunk 永远不会出现在结果中
- `top_k` 生效
- 空 query / 空索引 / 空字幕场景

## 13. 推荐结论

当前阶段建议：

1. 单独拆出 `subtitle_context` 模块
2. 增加独立 embedding 配置
3. 首版本地索引，不上独立向量数据库
4. 强制不剧透：只允许检索 `segment.start_sec` 之前的台词块

这样改造成本最低，也最贴合你当前的 Python 视频处理主线。
