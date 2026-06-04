/**
 * Resolve cancel_deadline_at for markJobCanceling.
 * Tests may set CANCEL_DEADLINE_SECONDS; production uses CANCEL_DEADLINE_MINUTES.
 */
export function resolveCancelDeadlineAt(nowMs = Date.now()) {
  const secondsRaw = process.env.CANCEL_DEADLINE_SECONDS?.trim();
  if (secondsRaw !== undefined && secondsRaw !== "") {
    const seconds = Number(secondsRaw);
    if (Number.isFinite(seconds) && seconds > 0) {
      return new Date(nowMs + seconds * 1000);
    }
  }
  const minutes = Number(process.env.CANCEL_DEADLINE_MINUTES || 30);
  const safeMinutes = Number.isFinite(minutes) && minutes > 0 ? minutes : 30;
  return new Date(nowMs + safeMinutes * 60 * 1000);
}

/**
 * @param {string | Date | null | undefined} deadlineAt
 */
export function isCancelDeadlinePassed(deadlineAt, nowMs = Date.now()) {
  if (!deadlineAt) return false;
  const t = deadlineAt instanceof Date ? deadlineAt.getTime() : Date.parse(String(deadlineAt));
  if (!Number.isFinite(t)) return false;
  return t <= nowMs;
}
