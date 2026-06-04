---
name: Subtitle extraction 字幕提取模块
overview: 通过 Python 媒体处理层以子进程方式调用 VideoCaptioner CLI（videocaptioner transcribe），输入本地视频路径，输出字幕文件（默认 SRT）并解析为结构化 cues；Node 仅负责上传编排、临时文件和结果回传。该子进程边界是工程隔离策略，不构成 GPL-3.0 合规结论，仍需法务确认。
todos:
  - id: upload-temp-file
    content: 在 server 侧建立上传文件落地到本地临时路径的流程，替代仅内存态上传
  - id: extraction-python-wrapper
    content: 在 Python 侧封装 spawn(videocaptioner transcribe …)，支持 videocaptioner_bin / PATH、超时与 stderr 摘要
  - id: extraction-parse-srt
    content: 实现 parseSrt -> cues[]，供字幕分析模块使用
  - id: extraction-config
    content: 在 Python/Node 共用配置中补充可选项 videocaptioner_asr、videocaptioner_language、videocaptioner_transcribe_timeout_ms，并更新 local.yaml.example / .env.example / config/README.md
  - id: extraction-node-bridge
    content: 在 server 侧增加调用 Python 字幕提取流程的 orchestration 层，并处理临时文件清理
isProject: false
---

# Subtitle extraction 模块：VideoCaptioner 子进程方案

## 目标

为 MovieTeller 提供「本地视频 → 字幕文件 → 结构化字幕 cues」的能力，作为后续字幕分析与旁白补充的上游输入。

## 当前项目约束

- 当前 Web 后端仍以 Express mock API 为主，尚未接入真实媒体处理主流程。
- 当前上传路由使用内存存储，不直接提供本地文件路径。
- 当前 Python narration 模块已经具备真实媒体处理、子进程调用和本地集成测试模式，适合作为字幕提取能力的落点。

## 集成方式（已修订）

- **不在 MovieTeller 进程内** `import videocaptioner`，仅通过子进程调用其 CLI。
- **Python 负责实际字幕提取与 SRT 解析**。
- **Node 负责上传编排、临时文件管理、调用 Python、返回结果**。
- 输入契约为：**本地视频或音轨文件路径**。
- 输出契约为：
  - 原始字幕文件路径（默认 `.srt`）
  - 结构化字幕 `cues[]`

## 分层职责

### Node / server

建议位置：

- `server/src/routes/...`
- `server/src/services/extraction/`

职责：

- 接收上传文件或本地资源请求
- 将上传内容落地到临时目录
- 调用 Python 字幕提取入口
- 将结果转换为 HTTP 响应
- 在成功/失败后清理临时文件

### Python

建议位置：

- `python/subtitle_extraction/` 新包  
  或  
- `python/narration` 邻近新增模块（若希望继续复用现有媒体处理结构）

职责：

- 解析配置
- 调用 `videocaptioner transcribe`
- 控制超时
- 收集 stderr / exit code
- 校验输出字幕文件是否生成
- 解析 `.srt` 为 `cues[]`

## 数据流

```mermaid
flowchart LR
  upload[Uploaded video]
  temp[Temporary local file]
  py[Python extraction wrapper]
  vc[videocaptioner transcribe]
  srt[Subtitle .srt]
  cues[Parsed cues]

  upload --> temp
  temp --> py
  py --> vc
  vc --> srt
  srt --> cues
```

## 结构化输出建议

```ts
type SubtitleCue = {
  startSec: number
  endSec: number
  text: string
}
```

最小返回结果建议：

```ts
{
  subtitlePath: string
  cues: SubtitleCue[]
}
```

若后续不希望向前端暴露物理路径，可在 HTTP 层裁剪掉 `subtitlePath`。

## 配置

### 已有配置

- `videocaptioner_bin`

### 待新增配置

- `videocaptioner_asr`
- `videocaptioner_language`
- `videocaptioner_transcribe_timeout_ms`

这些配置需要在以下位置保持一致：

- `server/src/config/schema.js`
- `python/movieteller_config/src/movieteller_config/schema.py`
- `config/local.yaml.example`
- `.env.example`
- `config/README.md`

## 第一阶段里程碑

第一阶段只覆盖本地处理闭环，不包含前端接入：

1. 给定本地视频路径
2. Python 成功调用 `videocaptioner transcribe`
3. 生成 `.srt`
4. 解析为 `cues[]`
5. 提供最小 CLI / smoke test / unit tests

## 测试

### Python 单元测试

- CLI 参数构造
- timeout / 非零退出码 / stderr 映射
- parseSrt fixture 测试

### Python 可选集成测试

- 本机已安装 `videocaptioner`
- 使用短视频样本验证 `.srt` 产出

### Node 测试

- 上传内容成功落地为临时文件
- 成功调用 Python 提取入口
- 成功 / 失败路径都能清理临时文件

## 风险与边界

- 当前 Web 上传链路还没有本地临时文件生命周期，这属于前置改造项。
- `videocaptioner` 是否稳定生成预期格式的 `.srt` 需要通过样本验证。
- 子进程边界是工程隔离策略，不等于许可证风险已经消除；最终分发与合规仍需法务确认。

## 完成后文档更新

实现后更新：

- 仓库根 `README.md`
- `config/README.md`
- 相关 Python 模块 README / manual test 说明
