# 可观测性 95% 落地记录

按规划 **0 → B2.0 → B3 → B1 → B2.1–B2.3 → B4** 执行；**不保留**宏阶段 legacy 事件（`subtitle_extraction.start` 等）。

## 步骤对照

| 步骤 | 内容 | 状态 |
|------|------|------|
| **0** | 基线：`scripts/run-observability-tests.sh`；33 条 observability pytest | 已落地 |
| **B2.0** | `stage_registry`：`render`/`export` 宏 ID；`FIXED_STAGE_TO_MACRO`；去掉 `narration_pipeline` | 已落地 |
| **B3** | `.github/workflows/python-observability.yml` | 已落地 |
| **B1** | `workflow_stages` / `workflow_exports` 仅 `StageLogger` → `workflow.stage.*` | 已落地 |
| **B2.1** | `progress.py` 宏 `current_stage` 只读 `workflow.stage.*` | 已落地 |
| **B2.2** | 保留 `WORKFLOW_*`、`STAGE_GROUP_*`、`SEGMENT_*`、gateway、study_card warning | 已落地 |
| **B2.3** | `test_progress` / README / `docs/reference/observability.md` | 已落地 |
| **B4** | 扫尾：`legacy_stage` 字段移除；`run-observability-tests.sh` 禁止 src 内 legacy 字面量 | 已落地 |

## 本地验证（步骤 0）

```bash
chmod +x scripts/run-observability-tests.sh
./scripts/run-observability-tests.sh
```

可选：对 succeeded Job 看进度 CLI（需已有 `artifacts/jobs/<id>/logs/workflow.jsonl`）：

```bash
PYTHONPATH=... python -m movieteller_logging.cli progress artifacts/jobs/<jobId>/logs/workflow.jsonl
```

## 事件契约（当前）

- **宏阶段生命周期**：仅 `workflow.stage.start|done|skipped|failed`，`stage` 字段为 `FIXED_WORKFLOW_STAGES` 中的 id（如 `render`、`export`）。
- **进度聚合**：`progress_from_jsonl` / `overall_progress` 宏阶段位置与 artifact（`x_*`）只消费 `workflow.stage.*`。
- **细粒度**：`segment.*`、`stage.group.*`、`gateway.*` 仍用于 segment / 旁白组 / 模型调用定位。

## 破坏性说明

- 旧 JSONL 中的 `subtitle_extraction.done` 等**不再**驱动进度条宏阶段；仅新任务日志可正确还原 CLI/API 进度。
- `stage_registry` 宏 ID 由 `video_package` / `workflow_export` 改为 **`render` / `export`**（与 `events.FIXED_WORKFLOW_STAGES` 一致）。

## 置信度（主观）

| 项 | 约分 |
|----|------|
| 宏阶段单一事件源 + 合同测 | **92** |
| 进度只读 `workflow.stage.*` | **90** |
| CI observability workflow | **88** |
| 端到端 Job + 前端进度条（需再跑 strict smoke） | **78** |

未到 **96+** 的常见缺口：前端日志 UI 未按 `event` 过滤；runner/CLI 仍有面向用户的 `print`；段级事件与宏阶段合同分离（by design）。

## 相关文件

- `python/movie_pipeline/stage_observability.py`
- `python/movieteller_logging/progress.py`、`stage_registry.py`、`events.py`
- `python/movie_pipeline/tests/test_workflow_stage_observability_contract.py`
- `.github/workflows/python-observability.yml`
