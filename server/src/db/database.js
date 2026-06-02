import { isApiRunMode, isWorkerRunMode } from "../runtime/runMode.js";

/**
 * @returns {string | null}
 */
export function getDatabaseUrl() {
  const url = process.env.DATABASE_URL?.trim();
  return url || null;
}

export function isDbEnabled() {
  return Boolean(getDatabaseUrl());
}

/** API / worker run modes require Postgres (Phase 2 Lite). */
export function requiresPhase2Database() {
  return isApiRunMode() || isWorkerRunMode();
}
