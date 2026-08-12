/** Generic AI Chat Assistant hooks (ADP-SPEC-041).
 *
 * Parameterized the same way agentReview.ts is (by basePath), so a future
 * second entry point reuses these unmodified. SSE consumption uses fetch()
 * + a manual stream reader rather than the browser's EventSource, since
 * EventSource cannot send the Authorization header this API requires.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, useCallback, useRef } from "react";
import { apiGet, apiMutation } from "./client";

export interface ChatCitation {
  entity_type: string;
  entity_id: string;
  verified: boolean;
}

export type ChatRole = "user" | "assistant";

export interface ChatMessage {
  id: string;
  conversation_id: string;
  role: ChatRole;
  content: string;
  citations: ChatCitation[];
  created_at: string;
}

export interface ChatConversationSummary {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
}

export interface ChatConversationDetail extends ChatConversationSummary {
  messages: ChatMessage[];
}

async function getAuthHeader(): Promise<Record<string, string>> {
  const authEnabled = import.meta.env.VITE_AUTH_ENABLED !== "false";
  if (!authEnabled) return {};
  try {
    const { getValidToken } = await import("../auth/keycloak");
    const token = await getValidToken(30);
    return token ? { Authorization: `Bearer ${token}` } : {};
  } catch {
    return {};
  }
}

export function useCreateConversation(basePath: string) {
  const qc = useQueryClient();
  return useMutation<ChatConversationSummary, Error, void>({
    mutationFn: () => apiMutation<ChatConversationSummary>("POST", `${basePath}/conversations`),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["chat-conversations", basePath] });
    },
  });
}

export function useConversations(basePath: string, enabled: boolean) {
  return useQuery<ChatConversationSummary[]>({
    queryKey: ["chat-conversations", basePath],
    queryFn: () => apiGet<ChatConversationSummary[]>(`${basePath}/conversations`),
    enabled,
  });
}

export function useConversation(basePath: string, conversationId: string | null) {
  return useQuery<ChatConversationDetail>({
    queryKey: ["chat-conversation", basePath, conversationId],
    queryFn: () => apiGet<ChatConversationDetail>(`${basePath}/conversations/${conversationId}`),
    enabled: !!conversationId,
  });
}

/** Streams a reply to a message. Not a plain useMutation since a single
 * promise resolution can't represent incremental chunks -- exposes
 * streamedText/isStreaming state directly, and invalidates the conversation
 * detail query once the persisted final message is in.
 *
 * sendMessage takes conversationId as an explicit argument rather than
 * closing over a prop/state value: a caller that creates a conversation and
 * immediately sends its first message in the same handler would otherwise
 * capture the pre-update (null) id, since a just-called setState doesn't
 * take effect until the next render -- a real stale-closure bug caught
 * while writing ChatPanel's own "create then send" flow. */
export function useSendMessage(basePath: string) {
  const qc = useQueryClient();
  const [isStreaming, setIsStreaming] = useState(false);
  const [streamedText, setStreamedText] = useState("");
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const sendMessage = useCallback(
    async (
      conversationId: string,
      content: string,
      diagramContext?: string,
      onComplete?: (fullText: string) => void,
    ) => {
      setIsStreaming(true);
      setStreamedText("");
      setError(null);
      const controller = new AbortController();
      abortRef.current = controller;
      let fullText = "";
      let hadError = false;

      try {
        const authHeader = await getAuthHeader();
        const res = await fetch(`${basePath}/conversations/${conversationId}/messages`, {
          method: "POST",
          headers: { ...authHeader, "Content-Type": "application/json" },
          body: JSON.stringify(
            diagramContext !== undefined ? { content, diagram_context: diagramContext } : { content },
          ),
          signal: controller.signal,
        });
        if (!res.ok || !res.body) {
          throw new Error(`Send message failed: ${res.status}`);
        }

        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        for (;;) {
          const { done, value } = await reader.read();
          if (done) break;
          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split("\n");
          buffer = lines.pop() ?? "";
          for (const line of lines) {
            if (!line.startsWith("data:")) continue;
            const event = JSON.parse(line.slice("data:".length).trim());
            if (event.type === "text_delta") {
              fullText += event.text;
              setStreamedText((prev) => prev + event.text);
            } else if (event.type === "error") {
              hadError = true;
              setError(event.detail ?? "The assistant hit an error.");
            }
          }
        }
      } catch (err) {
        if ((err as Error).name !== "AbortError") {
          hadError = true;
          setError((err as Error).message);
        }
      } finally {
        setIsStreaming(false);
        setStreamedText("");
        void qc.invalidateQueries({ queryKey: ["chat-conversation", basePath, conversationId] });
        if (!hadError) onComplete?.(fullText);
      }
    },
    [basePath, qc],
  );

  const cancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  return { sendMessage, cancel, isStreaming, streamedText, error };
}
