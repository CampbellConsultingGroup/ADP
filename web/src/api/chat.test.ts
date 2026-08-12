// ADP-914.8: unit tests for useSendMessage's new diagramContext/onComplete
// parameters. Mocks global.fetch to return a minimal SSE-shaped stream --
// VITE_AUTH_ENABLED resolves to "false" in tests (confirmed directly), so
// getAuthHeader() short-circuits and no Keycloak mocking is needed.

import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { renderHook, act, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import React from "react";
import { useSendMessage } from "./chat";

function sseResponse(lines: string[]): Response {
  const body = lines.map((l) => `data: ${l}\n\n`).join("");
  const stream = new ReadableStream({
    start(controller) {
      controller.enqueue(new TextEncoder().encode(body));
      controller.close();
    },
  });
  return new Response(stream, { status: 200 });
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

describe("useSendMessage: diagramContext (ADP-914.8)", () => {
  it("includes diagram_context in the POST body when provided", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      sseResponse([JSON.stringify({ type: "text_delta", text: "hi" })]),
    );
    const { result } = renderHook(() => useSendMessage("/api/v1/chat"), { wrapper });

    await act(async () => {
      await result.current.sendMessage("conv-1", "hello", "Diagram title: X");
    });

    const call = fetchMock.mock.calls[0];
    const body = JSON.parse((call[1] as RequestInit).body as string);
    expect(body).toEqual({ content: "hello", diagram_context: "Diagram title: X" });
  });

  it("omits diagram_context entirely when not provided (regression guard)", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      sseResponse([JSON.stringify({ type: "text_delta", text: "hi" })]),
    );
    const { result } = renderHook(() => useSendMessage("/api/v1/chat"), { wrapper });

    await act(async () => {
      await result.current.sendMessage("conv-1", "hello");
    });

    const call = fetchMock.mock.calls[0];
    const body = JSON.parse((call[1] as RequestInit).body as string);
    expect(body).toEqual({ content: "hello" });
    expect(body).not.toHaveProperty("diagram_context");
  });
});

describe("useSendMessage: onComplete (ADP-914.8)", () => {
  it("invokes onComplete with the full accumulated text on a successful send", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      sseResponse([
        JSON.stringify({ type: "text_delta", text: "Hello, " }),
        JSON.stringify({ type: "text_delta", text: "world." }),
      ]),
    );
    const { result } = renderHook(() => useSendMessage("/api/v1/chat"), { wrapper });
    const onComplete = vi.fn();

    await act(async () => {
      await result.current.sendMessage("conv-1", "hi", undefined, onComplete);
    });

    expect(onComplete).toHaveBeenCalledTimes(1);
    expect(onComplete).toHaveBeenCalledWith("Hello, world.");
  });

  it("does not invoke onComplete when the stream reports an error", async () => {
    const fetchMock = vi.mocked(fetch);
    fetchMock.mockResolvedValue(
      sseResponse([JSON.stringify({ type: "error", detail: "boom" })]),
    );
    const { result } = renderHook(() => useSendMessage("/api/v1/chat"), { wrapper });
    const onComplete = vi.fn();

    await act(async () => {
      await result.current.sendMessage("conv-1", "hi", undefined, onComplete);
    });

    await waitFor(() => expect(result.current.error).toBe("boom"));
    expect(onComplete).not.toHaveBeenCalled();
  });
});
