import { spawn } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

import { getRepoRoot } from "../../config/index.js";

function resolvePythonBin(repoRoot) {
  const venv = path.join(repoRoot, ".venv", "bin", "python3");
  if (fs.existsSync(venv)) return venv;
  return "python3";
}

/**
 * @param {string} logPath
 * @returns {Promise<Record<string, unknown>>}
 */
export function readWorkflowProgressFromLog(logPath) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(logPath)) {
      resolve({
        status: "unknown",
        percent: 0,
        label: "等待开始",
        currentStage: null,
      });
      return;
    }

    const repoRoot = getRepoRoot();
    const python = resolvePythonBin(repoRoot);
    const env = {
      ...process.env,
      PYTHONPATH: [
        path.join(repoRoot, "python", "movieteller_logging", "src"),
        process.env.PYTHONPATH,
      ]
        .filter(Boolean)
        .join(path.delimiter),
    };

    const child = spawn(python, ["-m", "movieteller_logging", logPath], {
      cwd: repoRoot,
      env,
      stdio: ["ignore", "pipe", "pipe"],
    });

    let stdout = "";
    let stderr = "";
    child.stdout.on("data", (chunk) => {
      stdout += chunk.toString();
    });
    child.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    child.on("error", reject);
    child.on("close", (code) => {
      if (code !== 0) {
        reject(new Error(stderr.trim() || `progress helper exited ${code}`));
        return;
      }
      try {
        resolve(JSON.parse(stdout.trim()));
      } catch (err) {
        reject(err);
      }
    });
  });
}
