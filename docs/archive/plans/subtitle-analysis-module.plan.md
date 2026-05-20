---
name: Subtitle analysis 字幕分析模块
overview: 消费 subtitle extraction 输出的结构化字幕 cues，分析字幕覆盖区间与无字幕空白区间（gaps），为后续旁白补充、片段规划或节奏控制提供输入。该模块不负责视频读取、不负责调用 CLI、不直接解析 SRT 文件。
todos:
  - id: analysis-cue-contract
    content: 固化 SubtitleCue / GapInterval / SubtitleGapAnalysis 数据结构
  - id: analysis-normalize-cues
    content: 实现 cues 排序、过滤非法区间、可选合并重叠或相邻区间
  - id: analysis-gap-detection
    content: 实现 gapsFromCues，基于时间轴识别无字幕区间
  - id: analysis-summary
    content: 实现 analyzeGapsFromCues，输出 gaps、总空白时长、cue 数量等摘要
  - id: analysis-tests
    content: 为连续字幕、重叠字幕、空输入、短 gap 阈值过滤、尾部 gap 等场景编写测试
isProject: false
---

# Subtitle analysis 模块

## 目标

基于 subtitle extraction 产生的 `cues[]`，找出字幕未覆盖的时间区间，为后续「在哪些片段插入补充旁白」提供结构化依据。

## 输入边界

本模块**不直接处理视频文件**、**不直接调用** `videocaptioner`、**不解析** `.srt` 文件。

本模块输入是结构化字幕 cues：

```ts
type SubtitleCue = {
  startSec: number
  endSec: number
  text: string
}
```

## 输出边界

建议输出：

```ts
type GapInterval = {
  startSec: number
  endSec: number
  durationSec: number
}

type SubtitleGapAnalysis = {
  gaps: GapInterval[]
  totalCueCount: number
  totalGapDurationSec: number
}
```

如已知视频总时长，可将其作为参数用于识别尾部 gap。

## 建议实现位置

优先建议放在 Python，与 extraction 邻接：

- `python/subtitle_extraction/...`  
  或  
- 单独 `python/subtitle_analysis/...`

若 Node 需要消费其结果，由 server 做桥接即可。

## 主要函数建议

**normalizeCues(cues)**

- 按开始时间排序
- 去掉非法区间（如 `endSec <= startSec`）
- 可选过滤空文本 cue

**mergeCueIntervals(cues, mergeThresholdSec=0.0)**

- 合并重叠或近邻区间
- 用于降低碎片化字幕对 gap 分析的影响

**gapsFromCues(cues, mediaDurationSec=None, minGapSec=0.0)**

- 计算 cue 之间的无字幕区间
- 若提供媒体总时长，则计算尾部 gap

**analyzeGapsFromCues(...)**

- 返回结构化分析摘要

## 分析规则建议

### 最小版本

- 使用排序后的 cues
- 基于前一个 cue 的 `endSec` 与下一个 cue 的 `startSec` 计算 gap
- 当 gap 的 `durationSec > minGapSec` 时保留

### 可选增强

- 将相邻且非常接近的 cues 视为连续覆盖
- 支持忽略纯标点或极短文本 cue

第一版不建议加入这些增强，除非样本已证明必要。

## 与 extraction 模块的依赖关系

**extraction 模块负责：**

- `videocaptioner transcribe`
- `.srt` 生成
- `.srt` → `cues[]`

**analysis 模块负责：**

- `cues[]` → gaps / summary

该边界应保持清晰，避免重复解析字幕文件或重复处理 CLI 错误。

## 测试

- 空 cues
- 单条 cue
- 多条连续 cue
- cue 间存在 gap
- cue 重叠
- cue 无序输入
- 非法 cue（`endSec <= startSec`）
- 指定 `mediaDurationSec` 时的尾部 gap
- `minGapSec` 过滤

## 第一阶段里程碑

第一阶段只完成纯函数分析能力：

1. 固化 `SubtitleCue` 和 `GapInterval`
2. 实现 `normalizeCues`
3. 实现 `mergeCueIntervals`
4. 实现 `gapsFromCues`
5. 覆盖主要测试场景

暂不接入前端和 HTTP 返回结构。

## 整体链路小结

- **Extraction**：先解决本地临时文件 → Python 调 CLI → SRT 解析成 `cues[]`
- **Analysis**：纯消费 `cues[]`，输出 gaps / summary；不碰上传、不碰视频、不碰 CLI

完成后更新仓库根 `README.md` 索引表状态。
