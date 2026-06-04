# MovieTeller Minimum Production Launch Checklist

## Scope

这份清单只覆盖“最小可上线版本”。

目标不是一步到位做成大规模平台，而是让当前 MovieTeller 从本地原型升级为：

- 可部署到公网
- 视频在服务器侧处理
- 用户可以提交任务并异步拿结果
- 系统具备基本稳定性、安全性和成本控制

---

## Launch Definition

满足以下条件即可认为达到“最小可上线版本”：

1. 用户可以上传视频并创建任务
2. 后台 Worker 可以完成：
   - 字幕提取
   - 字幕分析
   - 无字幕片段旁白生成
3. 前端可以查询任务状态和最终结果
4. 原始视频、SRT、结果 JSON 不依赖本机临时目录持久化
5. API 与 Worker 解耦，不同步阻塞 HTTP 请求
6. 有最基本的鉴权、限流、日志和失败处理

---

## Phase 0: Freeze Output Contract

### Must Have

- 确认最终结果 JSON schema
- 确认任务状态枚举
- 确认前端只依赖哪些字段

### Deliverables

- `result schema` 文档
- `job status` 文档
- 前后端统一字段命名表

### Exit Criteria

- `subtitleSpans`
- `rawGaps`
- `narrationCandidates`
- `narratedSegments`

这 4 组字段的结构固定，后续实现都按此 schema 输出。

---

## Phase 1: Async Job Skeleton

### Must Have

- 新增异步任务 API
- 引入队列
- 引入数据库任务表
- API 不再同步执行长任务

### Implementation Checklist

- [ ] 新增 `POST /api/jobs`
- [ ] 新增 `POST /api/jobs/:id/submit`
- [ ] 新增 `GET /api/jobs/:id`
- [ ] 新增 `GET /api/jobs/:id/result`
- [ ] 设计 `video_jobs` 表
- [ ] API 创建任务记录
- [ ] API 入队
- [ ] Worker 能消费队列里的任务

### Exit Criteria

- 能从 API 创建任务
- Worker 能拉到任务并写回状态
- 前端可以轮询状态变化

---

## Phase 2: Object Storage Integration

### Must Have

- 上传文件不再走 API 服务器中转
- 处理结果持久化到对象存储

### Implementation Checklist

- [ ] 集成对象存储 SDK
- [ ] `POST /api/jobs` 返回预签名上传 URL
- [ ] 前端直传视频到对象存储
- [ ] `submit` 时校验对象存在
- [ ] Worker 从对象存储下载视频
- [ ] Worker 上传 `.srt`
- [ ] Worker 上传最终结果 JSON

### Exit Criteria

- 原始视频能从对象存储读取
- 结果能从对象存储回放
- 重启 API/Worker 不丢失结果

---

## Phase 3: Python Pipeline Runtime

### Must Have

- Worker 内部能稳定调用 Python pipeline
- 生产环境不依赖仓库本地 `.venv`

### Implementation Checklist

- [ ] 编写 Worker Dockerfile
- [ ] 镜像内安装 Python 3.12
- [ ] 镜像内安装 ffmpeg / ffprobe
- [ ] 镜像内安装 `videocaptioner`
- [ ] 镜像内安装：
  - `movieteller_config`
  - `subtitle_extraction`
  - `subtitle_analysis`
  - `narration`
- [ ] 固定 Python 入口命令
- [ ] 固定临时工作目录

### Exit Criteria

- Worker 在干净容器中能独立完成一条视频处理任务

---

## Phase 4: End-to-End Processing

### Must Have

- Worker 能跑通完整链路

### Required Pipeline

- [ ] 下载视频
- [ ] 提取字幕
- [ ] 分析无字幕区间
- [ ] 生成旁白脚本
- [ ] 上传结果
- [ ] 更新数据库状态

### Exit Criteria

- 对一条测试视频，能产出：
  - `.srt`
  - `subtitleSpans`
  - `rawGaps`
  - `narrationCandidates`
  - `narratedSegments`

---

## Phase 5: Basic Frontend Integration

### Must Have

- 前端能创建任务
- 前端能展示进度
- 前端能展示最终 JSON 结果

### Implementation Checklist

- [ ] 增加“上传并创建任务”流程
- [ ] 增加任务轮询
- [ ] 增加处理中 UI
- [ ] 增加失败状态 UI
- [ ] 增加结果页面：
  - 旁白时间轴
  - 旁白文本
  - 对应无字幕片段

### Exit Criteria

- 用户从前端可以完整完成一次上传到结果查看

---

## Phase 6: Security Baseline

### Must Have

- 鉴权
- 上传限制
- 结果访问控制

### Implementation Checklist

- [ ] 用户登录态校验
- [ ] 任务归属校验
- [ ] 上传 MIME type 校验
- [ ] 文件大小限制
- [ ] 结果下载鉴权
- [ ] API Key 用 Secret Manager 或部署环境注入

### Exit Criteria

- 未登录用户不能创建任务
- 用户不能读取别人的任务结果

---

## Phase 7: Cost Control Baseline

### Must Have

- 避免无限制消耗 ASR 和模型额度

### Implementation Checklist

- [ ] 单视频时长上限
- [ ] 单视频体积上限
- [ ] `maxCandidates` 上限
- [ ] 每用户每日任务数限制
- [ ] 每用户每日总视频时长限制
- [ ] Worker 任务超时

### Suggested Defaults

- 单视频大小：`<= 500 MB`
- 单视频时长：`<= 10 min`
- `maxCandidates`: `<= 5`
- 单任务总执行超时：`<= 15 min`

### Exit Criteria

- 恶意或异常输入不会无限制拉高成本

---

## Phase 8: Failure Handling Baseline

### Must Have

- 失败时能定位
- 可重试错误能自动重试

### Implementation Checklist

- [ ] 任务失败原因落库
- [ ] Worker 输出阶段日志
- [ ] 网络类错误自动重试 2 到 3 次
- [ ] 非法视频直接失败
- [ ] 部分成功时保留中间结果

### Exit Criteria

- 失败任务可以从数据库和日志中定位问题

---

## Phase 9: Observability Baseline

### Must Have

- 日志
- 指标
- 基本告警

### Implementation Checklist

- [ ] 每个任务打印 `job_id`
- [ ] 打印阶段耗时
- [ ] 打印字幕条数、候选片段数、生成段数
- [ ] 统计成功率
- [ ] 统计平均处理时长
- [ ] 对 Worker 崩溃或队列堆积设置告警

### Exit Criteria

- 能回答：
  - 最近 24 小时成功率是多少
  - 哪个阶段最慢
  - 哪类失败最多

---

## Recommended Minimum Stack

最小可上线版本推荐：

- API: Node.js + Express
- Queue: Redis + BullMQ
- Worker: Python pipeline in Docker
- DB: PostgreSQL
- Storage: S3 / OSS / COS
- Deploy:
  - API 容器
  - Worker 容器
  - Redis
  - PostgreSQL

---

## Go-Live Checklist

上线前最终检查：

- [ ] API 异步化完成
- [ ] Worker 容器可重复部署
- [ ] 对象存储打通
- [ ] 数据库迁移完成
- [ ] 至少 3 个真实视频样本跑通
- [ ] 前端任务状态与结果页可用
- [ ] 鉴权和权限校验可用
- [ ] 限流和配额可用
- [ ] 日志和告警可用
- [ ] 模型和 ASR 密钥不在仓库明文中

---

## Not In Scope For Minimum Launch

以下能力可以放到第二阶段：

- WebSocket 实时流式更新
- 分布式多机弹性调度
- 视频内容审核体系
- 用户自定义旁白风格模板库
- 自动合成最终配音视频
- 多租户计费系统

---

## Final Recommendation

对当前项目来说，最小可上线版本不应该追求“大而全”，而应该优先完成：

1. 异步任务化
2. 对象存储化
3. Worker 容器化
4. 基本安全与成本控制

做到这四点，就已经可以从本地原型进入公网受控上线阶段。
