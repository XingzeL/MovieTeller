import fs from "node:fs";

import { readJobRecord } from "./readJob.js";
import { resolveArtifactDownload } from "./artifactManifest.js";

/**
 * 尝试清理某个 Job 的视频文件（仅当 video_downloaded_at 已标记时）
 * 这个函数设计为可被安全多次调用（幂等）
 * @param {string} jobId
 */
export function purgeVideoForJob(jobId) {
  try {
    const { record, paths } = readJobRecord(jobId);

    // 安全检查：必须先被标记为已下载
    if (!record.video_downloaded_at) {
      console.log(`[Storage Purge] Skipped purge for job ${jobId} — video not yet marked as downloaded.`);
      return;
    }

    // 已经清理过就直接返回
    if (record.video_purged_at) {
      return;
    }

    let videoFilePath = null;
    try {
      const resolved = resolveArtifactDownload(jobId, "renderedVideo");
      videoFilePath = resolved.filePath;
    } catch (e) {
      videoFilePath = null;
    }

    if (videoFilePath && fs.existsSync(videoFilePath)) {
      fs.unlinkSync(videoFilePath);
      record.video_purged_at = new Date().toISOString();

      fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");

      console.log(`[Storage Purge] Video file deleted for job ${jobId}`);
    } else {
      // 文件已经不存在，也标记为已清理，避免重复尝试
      record.video_purged_at = new Date().toISOString();
      fs.writeFileSync(paths.workflowJsonPath, `${JSON.stringify(record, null, 2)}\n`, "utf8");
      console.log(`[Storage Purge] Video already gone for job ${jobId}, marked as purged.`);
    }
  } catch (err) {
    console.error(`[Storage Purge] Failed to purge video for job ${jobId}`, err);
  }
}
