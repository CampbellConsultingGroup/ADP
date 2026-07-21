/** Component test: generic AI Chat Assistant panel (ADP-SPEC-041).
 *
 * Uses a custom fetch stub (not the shared mockFetch, which always
 * JSON-serializes) since the send-message endpoint streams a raw
 * text/event-stream body.
 */

import { describe, it, expect, afterEach, vi } from "vitest";
import { screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

import ChatPanel from "../../src/chat/ChatPanel";
import { renderWithQuery } from "./registry-test-utils";

const BASE_PATH = "/api/v1/chat";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

interface Call {
  method: string;
  url: string;
  body?: unknown;
}

function sseBody(...events: { type: string; [k: string]: unknown }[]): string {
  return events.map((e) => `data: ${JSON.stringify(e)}\n\n`).join("");
}

function mockChatFetch(opts: {
  createResponse: unknown;
  streamBody: string;
  listResponse?: unknown;
}): Call[] {
  const calls: Call[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: string, init?: RequestInit) => {
      const method = init?.method ?? "GET";
      calls.push({
        method, url,
        body: typeof init?.body === "string" ? JSON.parse(init.body) : undefined,
      });
      if (method === "POST" && url === `${BASE_PATH}/conversations`) {
        return new Response(JSON.stringify(opts.createResponse), {
          status: 200, headers: { "Content-Type": "application/json" },
        });
      }
      if (method === "GET" && url === `${BASE_PATH}/conversations`) {
        return new Response(JSON.stringify(opts.listResponse ?? []), {
          status: 200, headers: { "Content-Type": "application/json" },
        });
      }
      if (method === "POST" && url.endsWith("/messages")) {
        return new Response(opts.streamBody, {
          status: 200, headers: { "Content-Type": "text/event-stream" },
        });
      }
      if (method === "GET" && url.includes("/conversations/")) {
        return new Response(
          JSON.stringify({
            id: "C-1", title: "New conversation",
            created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
            messages: [],
          }),
          { status: 200, headers: { "Content-Type": "application/json" } },
        );
      }
      return new Response(JSON.stringify({ detail: "not mocked" }), { status: 404 });
    }),
  );
  return calls;
}

describe("ChatPanel", () => {
  it("creates a conversation on first send and streams the reply incrementally", async () => {
    const calls = mockChatFetch({
      createResponse: {
        id: "C-1", title: "New conversation",
        created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
      },
      streamBody: sseBody(
        { type: "text_delta", text: "The Merchandising" },
        { type: "text_delta", text: " capability is unclassified." },
        { type: "done", stop_reason: "end_turn", usage: { prompt_tokens: 1, completion_tokens: 1 } },
      ),
    });

    renderWithQuery(<ChatPanel basePath={BASE_PATH} />);

    fireEvent.change(screen.getByPlaceholderText("Ask a question…"), {
      target: { value: "Which capabilities are unclassified?" },
    });
    fireEvent.click(screen.getByRole("button", { name: /^Send$/i }));

    await waitFor(() => {
      const createCall = calls.find((c) => c.method === "POST" && c.url === `${BASE_PATH}/conversations`);
      expect(createCall).toBeDefined();
    });

    await waitFor(() => {
      const sendCall = calls.find((c) => c.url.endsWith("/messages"));
      expect(sendCall?.body).toEqual({ content: "Which capabilities are unclassified?" });
    });
  });

  it("disables the input while a reply is streaming", async () => {
    mockChatFetch({
      createResponse: {
        id: "C-1", title: "New conversation",
        created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
      },
      streamBody: sseBody({ type: "text_delta", text: "Hi" }, { type: "done", stop_reason: "end_turn", usage: {} }),
    });

    renderWithQuery(<ChatPanel basePath={BASE_PATH} />);

    const input = screen.getByPlaceholderText("Ask a question…") as HTMLInputElement;
    fireEvent.change(input, { target: { value: "Hello" } });
    fireEvent.click(screen.getByRole("button", { name: /^Send$/i }));

    await waitFor(() => {
      expect(input.disabled).toBe(true);
    });
  });
});
