// ADP-d8u.1: unit tests for web/src/api/strategy.ts's hooks. Mocks
// global.fetch, mirroring web/src/api/chat.test.ts's fetch-mocking
// convention (no business.ts test file exists yet to mirror instead --
// confirmed absent during Setup, T013).

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import {
  useCreateObjective,
  useCreateTheme,
  useLinkObjectiveCapability,
  useThemes,
} from "./strategy";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient();
  return React.createElement(QueryClientProvider, { client: qc }, children);
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useThemes", () => {
  it("GETs /api/v1/strategy/themes", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      jsonResponse({ items: [{ id: "t1", name: "Growth", created_at: "2026-01-01T00:00:00Z" }], total: 1 }),
    );
    const { result } = renderHook(() => useThemes(), { wrapper });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/strategy/themes");
    expect(result.current.data?.items[0].name).toBe("Growth");
  });
});

describe("useCreateTheme", () => {
  it("POSTs the name to /api/v1/strategy/themes", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      jsonResponse({ id: "t1", name: "Usage-based pricing", created_at: "2026-01-01T00:00:00Z" }, 201),
    );
    const { result } = renderHook(() => useCreateTheme(), { wrapper });

    result.current.mutate({ name: "Usage-based pricing" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/api/v1/strategy/themes");
    expect((call[1] as RequestInit).method).toBe("POST");
    expect(JSON.parse((call[1] as RequestInit).body as string)).toEqual({
      name: "Usage-based pricing",
    });
  });
});

describe("useCreateObjective", () => {
  it("POSTs the full create body to /api/v1/strategy/objectives", async () => {
    const fetchMock = vi.mocked(fetch);
    const created = {
      id: "obj-1",
      theme_id: "t1",
      owner: "Claims Platform Team",
      statement: "Reduce claims cycle time",
      metric_name: null,
      target_value: null,
      target_unit: null,
      direction: null,
      fiscal_year: 2026,
      period: "Q3",
      capability_ids: [],
      value_stream_ids: [],
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    fetchMock.mockResolvedValue(jsonResponse(created, 201));
    const { result } = renderHook(() => useCreateObjective(), { wrapper });

    result.current.mutate({
      theme_id: "t1",
      owner: "Claims Platform Team",
      statement: "Reduce claims cycle time",
      fiscal_year: 2026,
      period: "Q3",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/api/v1/strategy/objectives");
    expect(JSON.parse((call[1] as RequestInit).body as string)).toEqual({
      theme_id: "t1",
      owner: "Claims Platform Team",
      statement: "Reduce claims cycle time",
      fiscal_year: 2026,
      period: "Q3",
    });
  });
});

describe("useLinkObjectiveCapability", () => {
  it("POSTs capability_id to the objective's capabilities endpoint", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(jsonResponse(["cap-1"], 201));
    const { result } = renderHook(() => useLinkObjectiveCapability("obj-1"), { wrapper });

    result.current.mutate("cap-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/api/v1/strategy/objectives/obj-1/capabilities");
    expect(JSON.parse((call[1] as RequestInit).body as string)).toEqual({
      capability_id: "cap-1",
    });
  });
});
