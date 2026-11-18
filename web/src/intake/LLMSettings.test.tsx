// ADP-blp.13: model choices are saved on the server; the API key is not set on this screen.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as configApi from "../api/config";
import * as permissions from "../auth/permissions";
import LLMSettings from "./LLMSettings";

vi.mock("../api/config");
vi.mock("../auth/permissions");
const api = vi.mocked(configApi);
const mutate = vi.fn();

function setup(apiKeyConfigured: boolean, allowed = true) {
  vi.mocked(permissions.useCan).mockReturnValue(
    allowed ? { allowed: true } : { allowed: false, reason: "Your role (Reviewer) cannot do this." },
  );
  api.useLLMConfig.mockReturnValue({
    data: {
      endpoint: "https://api.anthropic.com",
      extraction_model: "claude-sonnet-4-6",
      recommendation_model: "claude-opus-4-8",
      validation_model: "claude-sonnet-4-6",
      api_key_configured: apiKeyConfigured,
      provider: apiKeyConfigured ? "anthropic" : "not_configured",
    },
    isLoading: false,
  } as never);
  api.useAvailableModels.mockReturnValue({
    data: {
      models: [
        { id: "claude-sonnet-4-6", name: "Sonnet", tier: "standard", description: "Fast." },
        { id: "claude-opus-4-8", name: "Opus", tier: "premium", description: "Most capable." },
      ],
    },
  } as never);
  api.useUpdateLLMConfig.mockReturnValue({ mutate, isPending: false, isSuccess: false, isError: false } as never);
  render(<LLMSettings />);
}

beforeEach(() => vi.clearAllMocks());

describe("LLMSettings", () => {
  it("offers no API key field and says where the key is set", () => {
    setup(false);
    expect(document.querySelector('input[type="password"]')).toBeNull();
    expect(screen.getByText(/API key not configured/)).toBeTruthy();
    expect(screen.getByText(/set when the platform is deployed/)).toBeTruthy();
  });

  it("saves a model choice for each of the three steps, with or without a key", async () => {
    setup(false);
    const validation = screen.getByLabelText("Validation Model") as HTMLSelectElement;
    expect(validation.disabled).toBe(false);
    await userEvent.selectOptions(validation, "claude-opus-4-8");
    expect(mutate).toHaveBeenCalledWith({ validation_model: "claude-opus-4-8" });
    expect((screen.getByLabelText("Recommendation Model") as HTMLSelectElement).value).toBe("claude-opus-4-8");
    expect(screen.getByLabelText("Extraction Model")).toBeTruthy();
  });

  it("is read-only for a role that cannot manage configuration", () => {
    setup(true, false);
    expect(permissions.useCan).toHaveBeenCalledWith("manage_config");
    const select = screen.getByLabelText("Extraction Model") as HTMLSelectElement;
    expect(select.disabled).toBe(true);
    expect(select.title).toMatch(/Reviewer/);
  });
});
