/**
 * @param {unknown} err
 */
export function isDatabaseUnavailableError(err) {
  if (!err || typeof err !== "object") return false;
  const code = "code" in err ? String(err.code) : "";
  return (
    code === "ECONNREFUSED" ||
    code === "ENOTFOUND" ||
    code === "57P01" ||
    code === "57P03" ||
    code === "ETIMEDOUT"
  );
}

/**
 * @param {import('express').Response} res
 * @param {unknown} err
 */
export function respondDatabaseError(res, err) {
  if (isDatabaseUnavailableError(err)) {
    return res.status(503).json({ error: "database unavailable" });
  }
  console.error(err);
  return res.status(500).json({ error: String(err?.message || err) });
}
