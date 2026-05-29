import { requeueExistingJob } from "./jobQueue.js";

/**
 * @param {string} jobId
 */
export function retryJob(jobId) {
  return requeueExistingJob(jobId);
}
