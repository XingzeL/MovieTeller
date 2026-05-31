import assert from "node:assert/strict";
import test from "node:test";

import { createApp } from "../src/app.js";
import { startTestServer } from "./testServer.js";

/**
 * @param {string} baseUrl
 * @param {string} path
 * @param {RequestInit} [init]
 */
async function apiFetch(baseUrl, path, init = {}) {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return fetch(`${baseUrl}${path}`, { ...init, headers });
}

test("dev session sets cookie and whoami returns user", async (t) => {
  const app = createApp({ includeDevRoutes: true });
  const { baseUrl, close } = await startTestServer(app);
  t.after(() => close());

  const bad = await apiFetch(baseUrl, "/api/dev/session", {
    method: "POST",
    body: JSON.stringify({ userId: "bad id!" }),
  });
  assert.equal(bad.status, 400);

  const session = await apiFetch(baseUrl, "/api/dev/session", {
    method: "POST",
    body: JSON.stringify({ userId: "user-a" }),
  });
  assert.equal(session.status, 200);
  const setCookie = session.headers.get("set-cookie") || "";
  assert.match(setCookie, /mt_uid=user-a/);

  const whoami = await apiFetch(baseUrl, "/api/dev/whoami", {
    headers: { Cookie: "mt_uid=user-a" },
  });
  assert.equal(whoami.status, 200);
  const body = await whoami.json();
  assert.equal(body.userId, "user-a");
});

test("production createApp omits dev routes", async () => {
  const prev = process.env.NODE_ENV;
  process.env.NODE_ENV = "production";
  try {
    const app = createApp({ includeDevRoutes: false });
    const { baseUrl, close } = await startTestServer(app);
    const res = await fetch(`${baseUrl}/api/dev/whoami`);
    await close();
    assert.equal(res.status, 404);
  } finally {
    process.env.NODE_ENV = prev;
  }
});
