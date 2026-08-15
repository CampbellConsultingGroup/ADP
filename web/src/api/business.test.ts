// ADP-am7-follow-up: unit test for web/src/api/business.ts's
// useAssignCapabilityDomain, mirroring web/src/api/strategy.test.ts's
// fetch-mocking convention (no business.ts test file existed before this --
// confirmed absent when strategy.test.ts's own header comment was written).
//
// Regression coverage for a bug report (2026-08-15, "Assigning a L1
// capability to a Domain is not working"): the PATCH always succeeded
// server-side, but onSuccess invalidated the wrong query key for the
// capabilities list ("capabilities" instead of the real
// "business-capabilities") and never invalidated the domain *detail* query
// (["domain", id], the one DomainDetail.tsx actually reads via useDomain) at
// all -- only the ["domains"] list. Both together meant a currently-open
// Domain screen never refreshed after Assign/Remove, reading as "nothing
// happened."

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useAssignCapabilityDomain } from "./business";

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn());
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useAssignCapabilityDomain", () => {
  it("PATCHes domain_id to the capability's domain endpoint", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      jsonResponse({ id: "cap-1", name: "Diag Capability", level: 1, domain_id: "dom-1" }),
    );
    const qc = new QueryClient();
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children);
    const { result } = renderHook(() => useAssignCapabilityDomain("cap-1"), { wrapper });

    result.current.mutate("dom-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const call = fetchMock.mock.calls[0];
    expect(call[0]).toBe("/api/v1/business/capabilities/cap-1/domain");
    expect((call[1] as RequestInit).method).toBe("PATCH");
    expect(JSON.parse((call[1] as RequestInit).body as string)).toEqual({ domain_id: "dom-1" });
  });

  it("invalidates business-capabilities, domains, and every cached domain detail query on success", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      jsonResponse({ id: "cap-1", name: "Diag Capability", level: 1, domain_id: "dom-1" }),
    );
    const qc = new QueryClient();
    // Seed the cache as if both lists and a specific domain's detail view
    // were already fetched (the real scenario: DomainDetail.tsx open on
    // "dom-1" via useDomain, with useCapabilities()/useDomains() also
    // cached from the tab bar) -- invalidateQueries only has an effect on
    // queries that already exist in the cache.
    qc.setQueryData(["business-capabilities"], { items: [], total: 0 });
    qc.setQueryData(["domains"], { items: [], total: 0 });
    qc.setQueryData(["domain", "dom-1"], { id: "dom-1", name: "Human Resources", capabilities: [] });
    const wrapper = ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children);
    const { result } = renderHook(() => useAssignCapabilityDomain("cap-1"), { wrapper });

    result.current.mutate("dom-1");

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(qc.getQueryState(["business-capabilities"])?.isInvalidated).toBe(true);
    expect(qc.getQueryState(["domains"])?.isInvalidated).toBe(true);
    expect(qc.getQueryState(["domain", "dom-1"])?.isInvalidated).toBe(true);
  });
});
