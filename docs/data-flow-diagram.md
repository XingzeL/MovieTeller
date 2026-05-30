# MovieTeller 当前数据流图（2026-05-30 更新版）

本图聚焦于 **Job 生命周期**、**视频/学习卡存储策略**（下载一次即删除视频）、以及 `original_source` + `video_downloaded_at` 字段的流转。

---

## 1. 整体架构泳道图（推荐阅读）

```mermaid
flowchart TB
    subgraph Client["Client (React / Browser)"]
        direction TB
        Start[StartPage]
        Dash[Dashboard]
        Upload[UploadPage]
        Panel[JobPanel + WorkflowProgressBar]
        History[历史卡片列表]
    end

    subgraph Node["Node.js Server (Express)"]
        direction TB
        Routes[routes/jobs.js]
        Create[createJob.js]
        Read[readJob.js + artifactManifest.js]
        Progress[Progress Polling]
        Download[Artifacts Download 接口]
    end

    subgraph Python["Python Pipeline"]
        direction TB
        Full[full_workflow.py]
        Export[workflow_exports.py]
        Study[study_cards_html.py]
        Pipeline[pipeline.py]
    end

    subgraph FS["File System (artifacts/jobs/{jobId}/)"]
        direction TB
        WF[workflow.json]
        Manifest[artifacts/manifest.json]
        StudyCard[study_cards/study_cards.html]
        Video[render/narrated.mp4]
    end

    %% 数据流向
    Start -- "Get Started" --> Dash
    Dash -- "Create a Video" --> Upload
    Upload -- "POST /api/jobs\n(文件 + 参数)" --> Routes
    Routes --> Create
    Create -- "写入 workflow.json\n(带 original_source)" --> WF
    Create -- "触发 Python" --> Python

    Python -- "生成产物\n写入 manifest.json" --> Manifest
    Python -- "更新 workflow.json 状态" --> WF

    Panel -- "轮询 /api/jobs/:id" --> Routes
    Panel -- "轮询 /api/jobs/:id/progress" --> Progress
    Progress -- "读取 workflow.json" --> WF

    History -- "展示 original_source\n+ video_downloaded_at" --> Dash

    Download -- "GET /artifacts/renderedVideo" --> Download
    Download -- "标记 video_downloaded_at" --> WF
    Download -- "（未来）触发删除视频" --> Video

    Download -- "GET /artifacts/studyCardsHtml" --> Download
```

---

## 2. 关键流程详细时序图

### 2.1 Job 创建流程（含 original_source 写入）

```mermaid
sequenceDiagram
    participant C as Client (UploadPage)
    participant N as Node Server
    participant F as File System
    participant P as Python Pipeline

    C->>N: POST /api/jobs<br/>(multipart: file + enableSpeech + cefrLevel + ...)
    N->>N: createJob.js<br/>生成 jobId、保存原始文件
    N->>N: buildOriginalSourceFromRequest()
    N->>F: 写入 workflow.json<br/>(original_source + video_downloaded_at: null)
    N->>P: 触发 Python 工作流<br/>(spawnPreparedJob)
    P->>P: full_workflow.py 执行
    P->>F: 生成 study_cards.html + narrated.mp4<br/>更新 manifest.json
    P->>F: 更新 workflow.json 状态为 succeeded
```

### 2.2 视频下载 + 标记删除流程（核心存储策略）

```mermaid
sequenceDiagram
    participant C as Client (Dashboard)
    participant N as Node Server
    participant F as File System

    C->>N: GET /api/jobs/{jobId}/artifacts/renderedVideo
    N->>F: resolveArtifactDownload()
    N->>C: 返回视频文件流（res.download）
    Note over N,C: 文件开始传输
    N->>F: 读取 workflow.json
    N->>N: 如果 video_downloaded_at 为空<br/>则写入当前时间
    N->>F: 写回 workflow.json
    Note over N: （可选异步）触发视频文件删除<br/>video_purged_at = now
```

**关键点**：
- 只有 `kind === "renderedVideo"` **且不是 `?inline=true` 预览** 时才会标记。
- 标记后即可认为用户已拿到视频，文件可以被安全删除。

### 2.3 Dashboard 历史卡片数据获取流程

```mermaid
sequenceDiagram
    participant C as Client (Dashboard)
    participant N as Node Server
    participant F as File System

    C->>N: GET /api/jobs（或单个 Job 详情）
    N->>F: readJobRecord()
    N->>N: jobRecordToDto()（包含 original_source + video_downloaded_at）
    N->>N: listJobArtifacts()（判断当前可下载的产物）
    N->>C: 返回 Job DTO + artifacts 列表
    C->>C: 根据 video_downloaded_at 决定按钮文案
```

---

## 3. 字段流转总结表

| 字段                    | 写入时机                     | 写入位置               | 读取位置                  | 作用 |
|-------------------------|------------------------------|------------------------|---------------------------|------|
| `original_source`       | Job 创建时                   | `createJob.js`         | Dashboard、重新生成逻辑   | 记录原始素材来源，支持一键重新生成 |
| `video_downloaded_at`   | 用户第一次成功下载视频后     | `routes/jobs.js` 下载接口 | Dashboard 卡片状态判断    | 触发“视频已删除”状态 + 后续清理 |
| `video_purged_at`       | 视频文件被真正删除后（可选） | 清理任务               | 审计/日志                 | 记录清理时间 |
| `artifacts`             | Python 生成产物后            | Python `workflow_exports.py` | `artifactManifest.js`     | 记录当前可下载的产物列表 |

---

## 4. 当前（2026-05-30）存储策略总结

- **视频文件**（`narrated.mp4`）：**下载一次即标记删除**（不长期保存）
- **学习卡**（`study_cards.html`）：目前倾向长期保留（用户核心价值）
- **原始来源**（`original_source`）：永久保留（支持重新生成）
- **workflow.json**：永久保留（元数据核心）

---

如果你需要我把这张图进一步拆成：
- 更简化的高层图
- 仅包含“重新生成”流程的图
- 加入未来“自动清理任务”的图

随时告诉我，我可以继续补充或生成单独的 Mermaid 图。