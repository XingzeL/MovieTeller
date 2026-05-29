# TTS-centric Resume 与「先交付学习卡」

产品策略（阶段四收窄版）：

- **不做**全链路每 stage 的 checkpoint API（无 `POST /resume?from=…`）。
- **要做**同一 Job 目录重跑时 **按 segment 补 TTS**（`tts_segment_is_reusable`）。
- **TTS 失败时仍导出学习卡**：旁白/润色/词卡数据保留，跳过 render，Job 记为 `failed` 且 `retryable`，便于用户下载学习卡后点重试。

## 行为摘要

| 场景 | Job `status` | 学习卡 | 成片 |
|------|--------------|--------|------|
| 全部成功 | `succeeded` | 有 | 有（若开启） |
| 部分/全部 TTS 失败 | `failed`（`tts_partial_failure`） | **仍导出**（HTML 存在时） | 跳过（`render` → `incomplete_tts`） |
| 学习卡导出也失败 | `failed` | 无 | 无 |

## 实现要点

- `pipeline.run_candidate`：TTS 异常 → `segment.tts.failed`（`fatal=False`），segment 仍写入 payload（含 `studyCard`）。
- `stage_video_package`：`enable_embed_video` 且 speech 不完整 → `workflow.stage.skipped` / `incomplete_tts`。
- `full_workflow`：export 完成后若 `workflowTts.failed > 0`，写 `artifacts.ttsPartialFailure`，`workflow.json` 为 `failed` + `retryable`。
- **外层** subtitle/frame_pool 复用仍为重试加速，非产品必承诺项。

## 重试

`POST /api/jobs/:id/retry` 在同一 `artifacts/jobs/{id}` 上重跑；已成功 segment 的 mp3 通过 `tts_segment_is_reusable` 跳过。

## 测试

```bash
pytest python/movie_pipeline/tests/test_tts_resume.py \
       python/movie_pipeline/tests/test_tts_partial_study_cards.py -q
```
