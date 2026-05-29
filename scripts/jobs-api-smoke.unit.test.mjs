import assert from "node:assert/strict";
import { describe, it } from "node:test";

import {
  TERMINAL,
  formatJobError,
  jobDtoFromPollBody,
  parseArgs,
  summarizeTerminalJob,
  validateOpts,
} from "./jobs-api-smoke-lib.mjs";

describe("parseArgs / validateOpts", () => {
  it("defaults to api mode and localhost", () => {
    const opts = parseArgs([], {});
    assert.equal(opts.mode, "api");
    assert.equal(opts.baseUrl, "http://localhost:3001");
    assert.equal(opts.apiPreflight, true);
    assert.equal(validateOpts(opts).ok, true);
  });

  it("reads env overrides", () => {
    const opts = parseArgs([], {
      MOVIE_TELLER_BASE_URL: "http://example.test/",
      MOVIE_TELLER_SMOKE_MODE: "workflow",
      MOVIE_TELLER_SMOKE_TIMEOUT_SEC: "120",
    });
    assert.equal(opts.baseUrl, "http://example.test");
    assert.equal(opts.mode, "workflow");
    assert.equal(opts.timeoutSec, 120);
  });

  it("rejects unknown mode and short timeout", () => {
    assert.equal(validateOpts(parseArgs(["--mode=bogus"])).ok, false);
    assert.equal(validateOpts(parseArgs(["--timeout-sec=5"])).ok, false);
  });

  it("accepts cancel mode and no-api-preflight", () => {
    const opts = parseArgs(["--mode=cancel", "--no-api-preflight"]);
    assert.equal(opts.mode, "cancel");
    assert.equal(opts.apiPreflight, false);
    assert.equal(validateOpts(opts).ok, true);
  });
});

describe("TERMINAL and job helpers", () => {
  it("TERMINAL includes product statuses", () => {
    assert.equal(TERMINAL.has("succeeded"), true);
    assert.equal(TERMINAL.has("failed"), true);
    assert.equal(TERMINAL.has("canceled"), true);
    assert.equal(TERMINAL.has("running"), false);
  });

  it("jobDtoFromPollBody prefers nested job", () => {
    assert.equal(jobDtoFromPollBody({ job: { status: "running" } }).status, "running");
    assert.equal(jobDtoFromPollBody({ status: "queued" }).status, "queued");
  });

  it("formatJobError handles object and string", () => {
    assert.match(
      formatJobError({ error: { error_code: "runner_exited", message: "exit 1" } }),
      /runner_exited/
    );
    assert.equal(formatJobError({ error: "plain" }), "plain");
  });

  it("summarizeTerminalJob includes stage and error", () => {
    const text = summarizeTerminalJob(
      {
        jobId: "j1",
        currentStage: "workflow",
        error: { error_code: "provider_timeout", message: "timed out" },
      },
      "failed"
    );
    assert.match(text, /j1/);
    assert.match(text, /provider_timeout/);
  });
});
