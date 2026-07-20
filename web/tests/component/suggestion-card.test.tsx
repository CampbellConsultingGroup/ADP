/** Component test: generic Agent Review suggestion card (ADP-SPEC-039). */

import { describe, it, expect, afterEach, vi } from "vitest";
import { screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

import AgentReviewButton from "../../src/agent-review/AgentReviewButton";
import SuggestionCard from "../../src/agent-review/SuggestionCard";
import CapabilityTree from "../../src/business/CapabilityTree";
import { renderCapabilitySuggestionDetail } from "../../src/business/agentReviewDetail";
import { mockFetch, renderWithQuery, lastCall } from "./registry-test-utils";

const BASE_PATH = "/api/v1/business/capabilities/CAP-1/agent-review";
const PORTFOLIO_BASE_PATH = "/api/v1/business/capabilities/agent-review";

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

  it("Close button dismisses the current review's results", async () => {
    mockFetch({
      [`POST ${BASE_PATH}`]: { operation_id: "OP-1" },
      [`GET ${BASE_PATH}/OP-1`]: {
        operation_id: "OP-1",
        status: "completed",
        suggestions: [
          {
            suggestion_id: "SUG-1",
            rationale: "This overlaps with CAP-2.",
            citations: [],
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

    fireEvent.click(screen.getByRole("button", { name: /^Close$/i }));

    expect(screen.queryByText(/This overlaps with CAP-2/)).toBeNull();
    // Close button itself disappears too -- there's nothing left to dismiss.
    expect(screen.queryByRole("button", { name: /^Close$/i })).toBeNull();
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

  it("accept calls onAccepted after a successful accept", async () => {
    mockFetch({
      [`POST ${BASE_PATH}/OP-1/suggestions/SUG-1/accept`]: {},
    });
    const suggestion = {
      suggestion_id: "SUG-1",
      rationale: "Set maturity to Established.",
      citations: [],
      advisory: false,
      status: "pending" as const,
    };
    const onAccepted = vi.fn();

    renderWithQuery(
      <SuggestionCard
        suggestion={suggestion}
        basePath={BASE_PATH}
        operationId="OP-1"
        onAccepted={onAccepted}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Accept$/i }));

    await waitFor(() => {
      expect(onAccepted).toHaveBeenCalledTimes(1);
    });
  });

  it("does not call onAccepted on reject", async () => {
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
    const onAccepted = vi.fn();

    renderWithQuery(
      <SuggestionCard
        suggestion={suggestion}
        basePath={BASE_PATH}
        operationId="OP-1"
        onAccepted={onAccepted}
      />,
    );
    fireEvent.click(screen.getByRole("button", { name: /^Reject$/i }));

    await waitFor(() => {
      expect(lastCall(calls, "POST")?.url).toBe(`${BASE_PATH}/OP-1/suggestions/SUG-1/reject`);
    });
    expect(onAccepted).not.toHaveBeenCalled();
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

  it("renders a current -> suggested transition for set_maturity_level via the Business Capabilities renderDetail", () => {
    mockFetch({});
    const suggestion = {
      suggestion_id: "SUG-4",
      type: "set_maturity_level",
      capability_id: "CAP-1",
      rationale: "Documented and standardized org-wide.",
      citations: [],
      advisory: false,
      status: "pending" as const,
      maturity_level: 3 as const,
      previous_maturity_level: 2 as const,
    };

    renderWithQuery(
      <SuggestionCard
        suggestion={suggestion}
        basePath={BASE_PATH}
        operationId="OP-1"
        renderDetail={renderCapabilitySuggestionDetail}
      />,
    );
    expect(screen.getByText("Emerging")).toBeDefined();
    expect(screen.getByText("Established")).toBeDefined();
  });

  it("renders a current -> suggested transition for reclassify_strategic_relevance via the Business Capabilities renderDetail", () => {
    mockFetch({});
    const suggestion = {
      suggestion_id: "SUG-5",
      type: "reclassify_strategic_relevance",
      capability_id: "CAP-1",
      rationale: "Now core to strategy.",
      citations: [],
      advisory: false,
      status: "pending" as const,
      strategic_relevance: 1 as const,
      previous_strategic_relevance: 3 as const,
    };

    renderWithQuery(
      <SuggestionCard
        suggestion={suggestion}
        basePath={BASE_PATH}
        operationId="OP-1"
        renderDetail={renderCapabilitySuggestionDetail}
      />,
    );
    expect(screen.getByText("Supporting")).toBeDefined();
    expect(screen.getByText("Strategic")).toBeDefined();
  });

  it("renders the proposed name/description/level distinctly for propose_new_capability via the Business Capabilities renderDetail", () => {
    mockFetch({});
    const suggestion = {
      suggestion_id: "SUG-7",
      type: "propose_new_capability",
      capability_id: null,
      rationale: "Returns Processing stage has no capability coverage.",
      citations: [{ entity_type: "value_stream_stage", entity_id: "STAGE-1" }],
      advisory: false,
      status: "pending" as const,
      proposed_name: "Returns Management",
      proposed_description: "Handles product returns.",
      proposed_level: 2 as const,
      proposed_parent_id: "CAP-1",
    };

    renderWithQuery(
      <SuggestionCard
        suggestion={suggestion}
        basePath={BASE_PATH}
        operationId="OP-1"
        renderDetail={renderCapabilitySuggestionDetail}
      />,
    );
    expect(screen.getByText("Returns Management")).toBeDefined();
    expect(screen.getByText("Handles product returns.")).toBeDefined();
    expect(screen.getByText(/L2/)).toBeDefined();
  });

  it("falls back to the generic field list for flag_duplicate when the Business Capabilities renderDetail is passed", () => {
    mockFetch({});
    const suggestion = {
      suggestion_id: "SUG-6",
      type: "flag_duplicate",
      capability_id: "CAP-1",
      rationale: "Near-identical name and description to CAP-2.",
      citations: [],
      advisory: false,
      status: "pending" as const,
      duplicate_of_capability_id: "CAP-2",
    };

    renderWithQuery(
      <SuggestionCard
        suggestion={suggestion}
        basePath={BASE_PATH}
        operationId="OP-1"
        renderDetail={renderCapabilitySuggestionDetail}
      />,
    );
    expect(screen.getByText(/duplicate_of_capability_id/)).toBeDefined();
  });

  it("renders a distinct 'Flagged for removal' notice for flag_capability_for_removal", () => {
    mockFetch({});
    const suggestion = {
      suggestion_id: "SUG-8",
      type: "flag_capability_for_removal",
      capability_id: "CAP-2",
      rationale: "Placeholder name, no description.",
      citations: [{ entity_type: "business_capability", entity_id: "CAP-2" }],
      advisory: false,
      status: "pending" as const,
    };

    renderWithQuery(
      <SuggestionCard
        suggestion={suggestion}
        basePath={PORTFOLIO_BASE_PATH}
        operationId="OP-1"
        renderDetail={renderCapabilitySuggestionDetail}
      />,
    );
    expect(screen.getByText(/Flagged for removal/)).toBeDefined();
    expect(screen.getAllByText(/CAP-2/).length).toBeGreaterThan(0);
  });
});

describe("CapabilityTree Review Portfolio button", () => {
  it("triggers a portfolio-scope review from the Capabilities tab header", async () => {
    const calls = mockFetch({
      [`GET /api/v1/business/capabilities`]: { items: [], total: 0 },
      [`POST ${PORTFOLIO_BASE_PATH}`]: { operation_id: "OP-PORTFOLIO" },
      [`GET ${PORTFOLIO_BASE_PATH}/OP-PORTFOLIO`]: {
        operation_id: "OP-PORTFOLIO",
        status: "completed",
        suggestions: [
          {
            suggestion_id: "SUG-9",
            type: "flag_capability_for_removal",
            capability_id: "CAP-3",
            rationale: "Redundant with another capability.",
            citations: [{ entity_type: "business_capability", entity_id: "CAP-3" }],
            advisory: false,
            status: "pending",
          },
        ],
      },
    });

    renderWithQuery(<CapabilityTree />);

    fireEvent.click(await screen.findByRole("button", { name: "Review Portfolio" }));
    fireEvent.click(
      screen.getByRole("button", { name: /Ask the business architecture expert to review the portfolio/ }),
    );

    await waitFor(() => {
      expect(screen.getByText(/Redundant with another capability/)).toBeDefined();
    });
    expect(lastCall(calls, "POST")?.url).toBe(PORTFOLIO_BASE_PATH);
  });
});
