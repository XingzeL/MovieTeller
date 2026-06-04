import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import test from "node:test";

import {
  isProcessAlive,
  killProcessGroup,
} from "../src/services/jobs/runnerControl.js";

test("killProcessGroup sends SIGTERM then SIGKILL to negative pid on POSIX", async (t) => {
  if (process.platform === "win32") {
    t.skip("POSIX only");
    return;
  }

  const calls = [];
  const killFn = (pid, signal) => {
    calls.push({ pid, signal });
  };

  let alive = true;
  const result = await killProcessGroup(4242, {
    killFn,
    isAliveFn: () => alive,
    graceMs: 80,
    sleepFn: async () => {
      if (calls.length === 1 && calls[0].signal === "SIGTERM") {
        alive = false;
      }
    },
  });

  assert.equal(calls[0]?.pid, -4242);
  assert.equal(calls[0]?.signal, "SIGTERM");
  assert.ok(
    result.outcome === "killed" || result.outcome === "already_exited"
  );
  assert.ok(calls.length >= 1);
});

test("killProcessGroup uses SIGKILL after grace when process stays alive", async (t) => {
  if (process.platform === "win32") {
    t.skip("POSIX only");
    return;
  }

  const calls = [];
  await killProcessGroup(5150, {
    killFn: (pid, signal) => calls.push({ pid, signal }),
    isAliveFn: () => true,
    graceMs: 30,
    sleepFn: async () => {},
  });

  assert.deepEqual(
    calls.map((c) => c.signal),
    ["SIGTERM", "SIGKILL"]
  );
  assert.equal(calls[1]?.pid, -5150);
});

test("POSIX child ignoring SIGTERM is killed by SIGKILL", async (t) => {
  if (process.platform === "win32") {
    t.skip("POSIX only");
    return;
  }

  const child = spawn(
    process.execPath,
    [
      "-e",
      `process.on('SIGTERM',()=>{}); setInterval(()=>{}, 1000);`,
    ],
    { detached: true, stdio: "ignore" }
  );
  child.unref();
  const pid = child.pid;
  assert.ok(pid);

  t.after(() => {
    try {
      if (pid && isProcessAlive(pid)) process.kill(-pid, "SIGKILL");
    } catch {
      /* ignore */
    }
  });

  const result = await killProcessGroup(pid, { graceMs: 200 });
  assert.equal(result.outcome, "killed");
  assert.equal(isProcessAlive(pid), false);
});
