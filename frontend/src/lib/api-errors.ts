export function formatApiError(status: number, body: string) {
  let detail = body.trim();

  try {
    const parsed = JSON.parse(body) as { detail?: unknown };
    if (typeof parsed.detail === "string") {
      detail = parsed.detail;
    }
  } catch {
    // Non-JSON error bodies are still useful as plain text.
  }

  if (status === 401 && detail === "Missing API key") {
    return "Operator API key required";
  }
  if (status === 401 && detail === "Invalid API key") {
    return "Invalid operator API key";
  }
  if (!detail) {
    return `${status}`;
  }
  return `${status} ${detail.slice(0, 160)}`;
}
