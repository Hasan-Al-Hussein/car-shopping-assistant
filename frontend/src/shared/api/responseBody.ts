import { abortable } from "./abort";
import { ClientFailure } from "./ClientFailure";

// Client safety bounds, not promises about server admission or valid inventory size.
export const RESPONSE_BYTES_MAX = 4 * 1024 * 1024;
export const RESPONSE_DEPTH_MAX = 48;

function withinDepth(value: unknown, depth = 0): boolean {
  if (depth > RESPONSE_DEPTH_MAX) return false;
  if (Array.isArray(value))
    return value.every((item) => withinDepth(item, depth + 1));
  if (value !== null && typeof value === "object") {
    return Object.values(value).every((item) => withinDepth(item, depth + 1));
  }
  return true;
}

export async function readJson(
  response: Response,
  signal: AbortSignal,
): Promise<unknown> {
  const invalid = () => new ClientFailure("invalid-response", "read");
  if (
    !/^application\/json(?:\s*;|$)/i.test(
      response.headers.get("Content-Type") ?? "",
    )
  )
    throw invalid();
  const declaredBytes = Number(response.headers.get("Content-Length"));
  if (Number.isFinite(declaredBytes) && declaredBytes > RESPONSE_BYTES_MAX)
    throw invalid();
  if (!response.body) throw invalid();
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let bytes = 0;
  let text = "";
  try {
    while (true) {
      const part = await abortable(reader.read(), signal);
      if (part.done) break;
      bytes += part.value.byteLength;
      if (bytes > RESPONSE_BYTES_MAX) throw invalid();
      text += decoder.decode(part.value, { stream: true });
    }
    text += decoder.decode();
    const value: unknown = JSON.parse(text);
    if (!withinDepth(value)) throw invalid();
    return value;
  } catch (error) {
    void reader.cancel().catch(() => undefined);
    if (error instanceof ClientFailure) throw error;
    if (signal.aborted) throw signal.reason;
    throw invalid();
  } finally {
    reader.releaseLock();
  }
}
