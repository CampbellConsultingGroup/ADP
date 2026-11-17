// ADP-SPEC-026: Bearer token injected from Keycloak when VITE_AUTH_ENABLED=true.

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    // Parsed JSON response body, when the error response had one -- ADP-SPEC-042
    // needs this to surface a 409 conflict's current_active_text/current_version
    // (FastAPI nests structured detail under `.detail`) without a bespoke fetch
    // call per endpoint. Optional and additive: every existing ApiError call
    // site ignores it.
    public readonly body?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED !== "false";

export async function getAuthHeader(): Promise<Record<string, string>> {
  if (!AUTH_ENABLED) return {};
  try {
    const { getValidToken } = await import("../auth/keycloak");
    const token = await getValidToken(30);
    // Don't fail silently: a missing token here is why authed API calls 401
    // and the app shows an error instead of data (ADP-cm9). Surface it.
    if (!token) console.error("getAuthHeader: no Keycloak token available; request will be unauthenticated");
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch (err) {
    console.error("getAuthHeader: failed to obtain Keycloak token", err);
    return {};
  }
}

/**
 * The human-readable reason in an error response body, if it has one (ADP-blp.33).
 *
 * FastAPI puts it in `detail`: a string for a refused request (the rule-named 409/422 messages),
 * a list of field errors for a body that failed validation, or an object with a `message`.
 */
export function describeErrorBody(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string" && detail.trim()) return detail;
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const { loc, msg } = item as { loc?: unknown; msg?: unknown };
        if (typeof msg !== "string") return null;
        const field = Array.isArray(loc) ? loc.filter((p) => p !== "body").join(".") : "";
        return field ? `${field}: ${msg}` : msg;
      })
      .filter((part): part is string => part !== null);
    return parts.length > 0 ? parts.join("; ") : null;
  }
  if (detail && typeof detail === "object") {
    const message = (detail as { message?: unknown }).message;
    if (typeof message === "string" && message.trim()) return message;
  }
  return null;
}

/**
 * Build the ApiError for a failed response. Its message is the server's own reason when the
 * body carries one, so a component that shows `error.message` tells the user what was refused;
 * otherwise it is the generic "<METHOD> <path> failed: <status>". The status and parsed body are
 * always on the error -- use hasStatus() rather than searching the message for a number.
 */
export async function toApiError(method: string, path: string, res: Response): Promise<ApiError> {
  let body: unknown;
  try {
    body = await res.json();
  } catch {
    // Non-JSON error body -- leave it undefined.
  }
  const message = describeErrorBody(body) ?? `${method} ${path} failed: ${res.status}`;
  return new ApiError(res.status, message, body);
}

/** The message to show for a failed request: the server's reason, else the error's own text. */
export function errorDetail(err: unknown): string {
  if (err instanceof ApiError) return describeErrorBody(err.body) ?? err.message;
  return err instanceof Error ? err.message : String(err);
}

/** True when the error is a response with this HTTP status. */
export function hasStatus(err: unknown, status: number): boolean {
  if (err instanceof ApiError) return err.status === status;
  // Errors built by hand (older tests) carry the status as a property or only in the text.
  const own = (err as { status?: unknown } | null)?.status;
  if (typeof own === "number") return own === status;
  return err instanceof Error && err.message.includes(String(status));
}

/** One request helper for every endpoint: auth header, JSON body, ApiError on failure. */
export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const authHeader = await getAuthHeader();
  const res = await fetch(path, {
    ...init,
    headers: { "Content-Type": "application/json", ...authHeader, ...init?.headers },
  });
  if (!res.ok) throw await toApiError(init?.method ?? "GET", path, res);
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function apiGet<T>(path: string): Promise<T> {
  return apiRequest<T>(path);
}

export async function apiMutation<T, B = unknown>(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: B,
): Promise<T> {
  return apiRequest<T>(path, {
    method,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
}
