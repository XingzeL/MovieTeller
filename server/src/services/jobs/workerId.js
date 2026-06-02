import os from "node:os";

export function getWorkerId() {
  const pod = process.env.POD_NAME?.trim();
  if (pod) return `${pod}:${process.pid}`;
  return `${os.hostname()}:${process.pid}`;
}
