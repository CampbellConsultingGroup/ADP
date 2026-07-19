/** Component test: generic Agent Review suggestion card (ADP-SPEC-039). */

import { describe, it, expect, afterEach, vi } from "vitest";
import { screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

import AgentReviewButton from "../../src/agent-review/AgentReviewButton";
import SuggestionCard from "../../src/agent-review/SuggestionCard";
import { mockFetch, renderWithQuery, lastCall } from "./registry-test-utils";

const BASE_PATH = "/api/v1/business/capabilities/CAP-1/agent-review";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("AgentReviewButton + SuggestionCard", () => {
  it("triggers a review, polls to completion, and renders suggestions", async () => {
    const calls = mockFetch({
      [`POST ${BASE_PATH}`]: { operation_id: "OP-1" },
      [`GET ${BASE_PATH}/OP-1`]: {
        operation_id: "OP-1",
        status: "completed",
        suggestions: [
          {
            suggestion_id: "SUG-1",
            rationale: "This overlaps with CAP-2.",
            citations: [{ entity_type: "business_capability", entity_id: "CAP-2" }],
            advisory: false,
            status: "pending",
          },
        ],
      },
    });

    renderWithQuery(<AgentReviewButton basePath={BASE_PATH} />);
    fireEvent.click(screen.getByRole("button", { name: /Review with AI/i }));

    await waitFor(() => {
      expect(screen.getByText(/This overlaps with CAP-2/)).toBeDefined();
    });
    expect(lastCall(calls, "POST")?.url).toBe(BASE_PATH);
  });

  it("shows a failed review's error_description", async () => {
    mockFetch({
      [`POST ${BASE_PATH}`]: { operation_id: "OP-2" },
      [`GET ${BASE_PATH}/OP-2`]: {
        operation_id: "OP-2",
        status: "failed",
        suggestions: [],
        error_description: "LLM provider timed out",
      },
    });

    renderWithQuery(<AgentReviewButton basePath={BASE_PATH} />);
    fireEvent.click(screen.getByRole("button", { name: /Review with AI/i }));

    await waitFor(() => {
      expect(screen.getByText(/LLM provider timed out/)).toBeDefined();
    });
  });

  it("accept calls the accept endpoint with a non-empty confirmation_id", async () => {
    const calls = mockFetch({
      [`POST ${BASE_PATH}/OP-1/suggestions/SUG-1/accept`]: {},
    });
    const suggestion = {
      suggestion_id: "SUG-1",
      rationale: "Set maturity to Established.",
      citations: [],
      advisory: false,
      status: "pending" as const,
    };

    renderWithQuery(
      <SuggestionCard suggestion={suggestion} basePath={BASE_PATH} operationId="OP-1" />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Accept$/i }));

    await waitFor(() => {
      const call = lastCall(calls, "POST");
      expect(call?.url).toBe(`${BASE_PATH}/OP-1/suggestions/SUG-1/accept`);
      expect(call?.body).toMatchObject({ confirmation_id: "CONFIRM-SUG-1", advisory_acknowledged: false });
    });
  });

  it("reject calls the reject endpoint", async () => {
    const calls = mockFetch({
      [`POST ${BASE_PATH}/OP-1/suggestions/SUG-1/reject`]: {},
    });
    const suggestion = {
      suggestion_id: "SUG-1",
      rationale: "Flagged as duplicate.",
      citations: [],
      advisory: false,
      status: "pending" as const,
    };

    renderWithQuery(
      <SuggestionCard suggestion={suggestion} basePath={BASE_PATH} operationId="OP-1" />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Reject$/i }));

    await waitFor(() => {
      expect(lastCall(calls, "POST")?.url).toBe(`${BASE_PATH}/OP-1/suggestions/SUG-1/reject`);
    });
  });

  it("disables Accept for an advisory suggestion until the acknowledgment checkbox is checked", () => {
    mockFetch({});
    const suggestion = {
      suggestion_id: "SUG-2",
      rationale: "Proposes a new capability, but the citation could not be verified.",
      citations: [],
      advisory: true,
      status: "pending" as const,
    };

    renderWithQuery(
      <SuggestionCard suggestion={suggestion} basePath={BASE_PATH} operationId="OP-1" />,
    );

    const acceptButton = screen.getByRole("button", { name: /^Accept$/i }) as HTMLButtonElement;
    expect(acceptButton.disabled).toBe(true);

    fireEvent.click(screen.getByRole("checkbox"));
    expect(acceptButton.disabled).toBe(false);
  });

  it("renders extra adapter-specific fields generically when no renderDetail is given", () => {
    mockFetch({});
    const suggestion = {
      suggestion_id: "SUG-3",
      rationale: "Suggest reclassifying.",
      citations: [],
      advisory: false,
      status: "pending" as const,
      strategic_relevance: 1,
    };

    renderWithQuery(
      <SuggestionCard suggestion={suggestion} basePath={BASE_PATH} operationId="OP-1" />,
    );
    expect(screen.getByText(/strategic_relevance/)).toBeDefined();
  });
});
