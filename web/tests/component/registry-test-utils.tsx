/** Shared utilities for business/application registry component tests.
 *
 * Components call the API through global fetch with relative paths
 * (src/api/client.ts), so tests stub fetch with a route table keyed by
 * "METHOD /path" and record calls for interaction assertions.
 */

import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import { vi } from "vitest";

export interface FetchCall {
  method: string;
  url: string;
  body?: unknown;
}

/** Stub global fetch. Routes map "METHOD /url" to a JSON body (or a
 * [status, body] tuple). Unmatched requests 404 so tests fail loudly. */
export function mockFetch(routes: Record<string, unknown>): FetchCall[] {
  const calls: FetchCall[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({
        method,
        url,
        body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      const spec = routes[`${method} ${url}`];
      if (spec === undefined) {
        return new Response(JSON.stringify({ detail: "not mocked" }), { status: 404 });
      }
      const [status, body] = Array.isArray(spec) && typeof spec[0] === "number"
        ? (spec as [number, unknown])
        : [200, spec];
      if (status === 204) return new Response(null, { status: 204 });
      return new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json" },
      });
    }),
  );
  return calls;
}

export function renderWithQuery(ui: React.ReactElement): RenderResult {
  const qc = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

/** Wait until a fetch call matching method+url prefix was made. */
export function lastCall(calls: FetchCall[], method: string): FetchCall | undefined {
  return [...calls].reverse().find((c) => c.method === method);
}
