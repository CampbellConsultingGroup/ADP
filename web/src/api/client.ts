// ADP-SPEC-026: Bearer token injected from Keycloak when VITE_AUTH_ENABLED=true.

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

const AUTH_ENABLED = import.meta.env.VITE_AUTH_ENABLED !== "false";

async function getAuthHeader(): Promise<Record<string, string>> {
  if (!AUTH_ENABLED) return {};
  try {
    const { getValidToken } = await import("../auth/keycloak");
    const token = await getValidToken(30);
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
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
    throw new ApiError(res.status, `${method} ${path} failed: ${res.status}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}
