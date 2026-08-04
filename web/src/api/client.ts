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

export async function apiGet<T>(path: string): Promise<T> {
  const authHeader = await getAuthHeader();
  const res = await fetch(path, {
    headers: { ...authHeader, "Content-Type": "application/json" },
  });
  if (!res.ok) {
    throw new ApiError(res.status, `GET ${path} failed: ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export async function apiMutation<T, B = unknown>(
  method: "POST" | "PUT" | "PATCH" | "DELETE",
  path: string,
  body?: B,
): Promise<T> {
  const authHeader = await getAuthHeader();
  const res = await fetch(path, {
    method,
    headers: { ...authHeader, "Content-Type": "application/json" },
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    let parsedBody: unknown;
    try {
      parsedBody = await res.json();
    } catch {
      // Non-JSON error body — leave parsedBody undefined.
    }
    throw new ApiError(res.status, `${method} ${path} failed: ${res.status}`, parsedBody);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
