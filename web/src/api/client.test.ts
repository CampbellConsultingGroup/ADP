import { afterEach, describe, expect, it, vi } from "vitest";
import { ApiError, apiGet, apiMutation, apiRequest, describeErrorBody, errorDetail, hasStatus } from "./client";

function respond(status: number, body?: unknown) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockResolvedValue(
      new Response(body === undefined ? null : JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      }),
    ),
  );
}

afterEach(() => vi.unstubAllGlobals());

describe("api client errors (ADP-blp.33)", () => {
  it("uses the server's reason as the error message", async () => {
    respond(409, { detail: "An application capability named 'Payments' already exists here" });
    const err = (await apiMutation("POST", "/api/v1/x", {}).catch((e: ApiError) => e)) as ApiError;
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(409);
    expect(err.message).toBe("An application capability named 'Payments' already exists here");
    expect(hasStatus(err, 409)).toBe(true);
    expect(hasStatus(err, 403)).toBe(false);
  });

  it("summarises field validation errors", async () => {
    respond(422, {
      detail: [
        { loc: ["body", "name"], msg: "Field required" },
        { loc: ["body", "owner", "email"], msg: "value is not a valid email address" },
      ],
    });
    const err = (await apiRequest("/api/v1/x", { method: "POST" }).catch((e: ApiError) => e)) as ApiError;
    expect(err.message).toBe("name: Field required; owner.email: value is not a valid email address");
  });

  it("reads a message nested in a structured detail", () => {
    expect(describeErrorBody({ detail: { message: "promotion blocked", issues: [] } })).toBe("promotion blocked");
    expect(describeErrorBody({ detail: {} })).toBeNull();
    expect(describeErrorBody("nope")).toBeNull();
  });

  it("falls back to method, path and status when the body has no reason", async () => {
    respond(500);
    const err = (await apiGet("/api/v1/applications").catch((e: ApiError) => e)) as ApiError;
    expect(err.message).toBe("GET /api/v1/applications failed: 500");
    expect(err.status).toBe(500);
    expect(errorDetail(err)).toBe("GET /api/v1/applications failed: 500");
  });

  it("returns undefined for 204 and the parsed body otherwise", async () => {
    respond(204);
    expect(await apiMutation("DELETE", "/api/v1/x")).toBeUndefined();
    respond(200, { id: "a" });
    expect(await apiGet("/api/v1/x")).toEqual({ id: "a" });
  });

  it("hasStatus understands hand-built errors too", () => {
    expect(hasStatus(Object.assign(new Error("boom"), { status: 409 }), 409)).toBe(true);
    expect(hasStatus(new Error("403 Forbidden"), 403)).toBe(true);
    expect(hasStatus(new Error("boom"), 403)).toBe(false);
    expect(hasStatus(null, 403)).toBe(false);
  });
});
