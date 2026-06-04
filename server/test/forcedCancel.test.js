import assert from "node:assert/strict";
import test from "node:test";

import { isForcedCancelKillOutcomeAcceptable } from "../src/services/jobs/forcedCancel.js";

test("isForcedCancelKillOutcomeAcceptable allows killed, already_exited, no_pid", () => {
  assert.equal(isForcedCancelKillOutcomeAcceptable("killed"), true);
  assert.equal(isForcedCancelKillOutcomeAcceptable("already_exited"), true);
  assert.equal(isForcedCancelKillOutcomeAcceptable("no_pid"), true);
  assert.equal(isForcedCancelKillOutcomeAcceptable("failed"), false);
  assert.equal(isForcedCancelKillOutcomeAcceptable("skipped_windows"), false);
});
