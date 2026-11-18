/** Admin Agent Prompt Management API client (ADP-SPEC-042).
 *
 * See specs/042-admin-prompt-management/contracts/agent-prompts-api.md.
 */

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";
import { QK } from "./queryKeys";

const BASE_PATH = "/api/v1/admin/agent-prompts";

export interface AgentPromptView {
  agent_id: string;
  display_name: string;
  active_text: string;
  is_override: boolean;
  version: number;
}

export interface AgentPromptListResponse {
  items: AgentPromptView[];
}

export interface PromptHistoryEntry {
  id: number;
  agent_id: string;
  actor: string;
  changed_at: string;
  change_type: "edit" | "restore";
  prior_text: string;
  new_text: string;
}

export interface PromptHistoryResponse {
  items: PromptHistoryEntry[];
}

export interface PromptChangeResult {
  agent_id: string;
  active_text: string;
  version: number;
}

export function useAgentPrompts() {
  return useQuery<AgentPromptListResponse>({
    queryKey: [QK.adminAgentPrompts],
    queryFn: () => apiGet<AgentPromptListResponse>(BASE_PATH),
  });
}

export function useAgentPromptHistory(agentId: string | null) {
  return useQuery<PromptHistoryResponse>({
    queryKey: [QK.adminAgentPromptHistory, agentId],
    queryFn: () => apiGet<PromptHistoryResponse>(`${BASE_PATH}/${agentId}/history`),
    enabled: !!agentId,
  });
}

export function useConfirmPromptEdit(agentId: string) {
  const qc = useQueryClient();
  return useMutation<
    PromptChangeResult,
    Error,
    { newText: string; expectedVersion: number; confirmationId: string }
  >({
    mutationFn: ({ newText, expectedVersion, confirmationId }) =>
      apiMutation<PromptChangeResult>("POST", `${BASE_PATH}/${agentId}/confirm`, {
        new_text: newText,
        expected_version: expectedVersion,
        confirmation_id: confirmationId,
      }),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QK.adminAgentPrompts] });
      void qc.invalidateQueries({ queryKey: [QK.adminAgentPromptHistory, agentId] });
    },
  });
}

export function useRestorePromptVersion(agentId: string) {
  const qc = useQueryClient();
  return useMutation<
    PromptChangeResult,
    Error,
    { historyId: number; expectedVersion: number; confirmationId: string }
  >({
    mutationFn: ({ historyId, expectedVersion, confirmationId }) =>
      apiMutation<PromptChangeResult>(
        "POST",
        `${BASE_PATH}/${agentId}/restore/${historyId}`,
        { expected_version: expectedVersion, confirmation_id: confirmationId },
      ),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: [QK.adminAgentPrompts] });
      void qc.invalidateQueries({ queryKey: [QK.adminAgentPromptHistory, agentId] });
    },
  });
}
