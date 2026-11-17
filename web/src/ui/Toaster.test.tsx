import { afterEach, describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import { apiGet, apiMutation } from "../api/client";
import { Toaster } from "./Toaster";

function respond(status = 200, body: unknown = {}) {
  vi.stubGlobal(
    "fetch",
    vi.fn().mockImplementation(() =>
      Promise.resolve(new Response(status === 204 ? null : JSON.stringify(body), { status })),
    ),
  );
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("save confirmation (ADP-blp.48)", () => {
  it("says Saved after a write and Removed after a delete, then clears", async () => {
    vi.useFakeTimers();
    respond();
    render(<Toaster />);
    expect(screen.getByRole("status").textContent).toBe("");

    await act(async () => {
      await apiMutation("PATCH", "/api/v1/business/capabilities/c1", { maturity_level: 3 });
    });
    expect(screen.getByRole("status").textContent).toContain("Saved");

    respond(204);
    await act(async () => {
      await apiMutation("DELETE", "/api/v1/business/capabilities/c1");
    });
    expect(screen.getByRole("status").textContent).toContain("Removed");

    act(() => {
      vi.advanceTimersByTime(3000);
    });
    expect(screen.getByRole("status").textContent).toBe("");
  });

  it("stays quiet for reads, failures and requests that only start work", async () => {
    render(<Toaster />);
    respond();
    await act(async () => {
      await apiGet("/api/v1/applications");
      await apiMutation("POST", "/api/v1/designs/DSN-1/recommend", {});
      await apiMutation("POST", "/api/v1/chat/conversations", {});
      await apiMutation("POST", "/api/v1/patterns/validate", {});
    });
    respond(422, { detail: "nope" });
    await act(async () => {
      await apiMutation("POST", "/api/v1/applications", {}).catch(() => undefined);
    });
    expect(screen.getByRole("status").textContent).toBe("");
  });
});
