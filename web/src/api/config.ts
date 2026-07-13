/** LLM configuration hooks (ADP-SPEC-015). */
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiGet, apiMutation } from "./client";

export interface ModelInfo {
  id: string;
  name: string;
  description: string;
  tier: string;
  context_window: number;
  recommended_for: string[];
}

export interface ModelsResponse {
  models: ModelInfo[];
  provider: string;
  endpoint: string;
  api_key_configured: boolean;
}

export interface LLMConfig {
  endpoint: string;
  extraction_model: string;
  recommendation_model: string;
  api_key_configured: boolean;
  provider: "anthropic" | "openai_compatible" | "not_configured";
}

export interface LLMConfigUpdate {
  extraction_model?: string;
  recommendation_model?: string;
  api_key?: string;
}

export function useAvailableModels() {
  return useQuery<ModelsResponse>({
    queryKey: ["config", "models"],
    queryFn: () => apiGet<ModelsResponse>("/api/v1/config/models"),
    staleTime: 60_000,
  });
}

export function useLLMConfig() {
  return useQuery<LLMConfig>({
    queryKey: ["config", "llm"],
    queryFn: () => apiGet<LLMConfig>("/api/v1/config/llm"),
    staleTime: 30_000,
  });
}

export function useUpdateLLMConfig() {
  const qc = useQueryClient();
  return useMutation<LLMConfig, Error, LLMConfigUpdate>({
    mutationFn: (update) =>
      apiMutation<LLMConfig, LLMConfigUpdate>("PUT", "/api/v1/config/llm", update),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["config", "llm"] });
    },
  });
}
