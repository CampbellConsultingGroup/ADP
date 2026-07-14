/** Component test: guided intake three-input form (ADP-zg3.1). */

import { describe, it, expect, afterEach, vi } from "vitest";
import { screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

import IntakeTextForm from "../../src/intake/IntakeTextForm";
import { mockFetch, renderWithQuery } from "./registry-test-utils";

const CONFIG = {
  endpoint: "https://api.anthropic.com",
  extraction_model: "claude-sonnet-4-6",
  recommendation_model: "claude-sonnet-4-6",
  api_key_configured: true,
  provider: "anthropic",
};

const MODELS = {
  models: [
    {
      id: "claude-sonnet-4-6",
      name: "Sonnet",
      description: "",
      tier: "balanced",
      context_window: 200000,
      recommended_for: ["extraction"],
    },
  ],
  provider: "anthropic",
  endpoint: "https://api.anthropic.com",
  api_key_configured: true,
};

function routes(extra: Record<string, unknown> = {}) {
  return {
    "GET /api/v1/config/llm": CONFIG,
    "GET /api/v1/config/models": MODELS,
    "POST /api/v1/designs/D-1/intake": {
      operation_id: "op-1",
      design_id: "D-1",
      mode: "bulk_text",
      status: "completed",
    },
    ...extra,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("IntakeTextForm (guided intake)", () => {
  it("renders the three inputs and disables submit until required fields are filled", async () => {
    mockFetch(routes());
    renderWithQuery(<IntakeTextForm designId="D-1" onOperationCreated={() => {}} />);

    expect(screen.getByLabelText(/Business Problem/i)).toBeDefined();
    expect(screen.getByLabelText(/Desired Outcome/i)).toBeDefined();
    expect(screen.getByLabelText(/Known Requirements/i)).toBeDefined();

    const button = screen.getByRole("button", { name: /Submit/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true); // required fields empty

    fireEvent.change(screen.getByLabelText(/Business Problem/i), {
      target: { value: "Peak checkout latency loses sales." },
    });
    expect(button.disabled).toBe(true); // still missing desired outcome

    fireEvent.change(screen.getByLabelText(/Desired Outcome/i), {
      target: { value: "Sub-second checkout at 10k users." },
    });
    expect(button.disabled).toBe(false); // both required filled; known requirements optional
  });

  it("submits all three fields to the intake API", async () => {
    const calls = mockFetch(routes());
    const onCreated = vi.fn();
    renderWithQuery(<IntakeTextForm designId="D-1" onOperationCreated={onCreated} />);

    fireEvent.change(screen.getByLabelText(/Business Problem/i), {
      target: { value: "Peak checkout latency loses sales." },
    });
    fireEvent.change(screen.getByLabelText(/Desired Outcome/i), {
      target: { value: "Sub-second checkout at 10k users." },
    });
    fireEvent.change(screen.getByLabelText(/Known Requirements/i), {
      target: { value: "The system must sustain 10,000 concurrent checkouts." },
    });

    fireEvent.click(screen.getByRole("button", { name: /Submit/i }));

    await waitFor(() => {
      const post = calls.find((c) => c.method === "POST");
      expect(post).toBeDefined();
      expect(post!.body).toMatchObject({
        mode: "bulk_text",
        business_problem: "Peak checkout latency loses sales.",
        desired_outcome: "Sub-second checkout at 10k users.",
        text: "The system must sustain 10,000 concurrent checkouts.",
      });
    });
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("op-1", true));
  });

  it("blocks submit when known requirements is non-empty but too short", () => {
    mockFetch(routes());
    renderWithQuery(<IntakeTextForm designId="D-1" onOperationCreated={() => {}} />);

    fireEvent.change(screen.getByLabelText(/Business Problem/i), { target: { value: "Problem." } });
    fireEvent.change(screen.getByLabelText(/Desired Outcome/i), { target: { value: "Outcome." } });
    fireEvent.change(screen.getByLabelText(/Known Requirements/i), { target: { value: "short" } });

    const button = screen.getByRole("button", { name: /Submit/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true);
    expect(screen.getByText(/at least 20 characters/i)).toBeDefined();
  });
});
