/** Component test: reuse-candidate rendering on the recommendation OptionCard
 * (ADP-SPEC-007). Follow-up ADP-10w.5. */

import { describe, it, expect, afterEach, vi } from "vitest";
import { screen, cleanup } from "@testing-library/react";

import OptionCard from "../../src/recommend/OptionCard";
import type { SolutionOption } from "../../src/api/recommend";
import { mockFetch, renderWithQuery } from "./registry-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

function makeOption(overrides: Partial<SolutionOption> = {}): SolutionOption {
  return {
    option_id: "opt-1",
    rank: 1,
    title: "Reuse the billing platform",
    rationale: "Reuses an existing system rather than building new.",
    advisory: false,
    satisfies: ["REQ-1"],
    trade_offs: [],
    proposed_elements: [],
    grounded_on: [],
    ranking_score: 0.8,
    status: "pending",
    knowledge_source: "knowledge_base",
    ...overrides,
  };
}

describe("OptionCard reuse candidates", () => {
  it("renders reuse candidates with name, classification, and capabilities", () => {
    mockFetch({});
    const option = makeOption({
      reuse_candidates: [
        {
          app_id: "app-1",
          name: "Billing Platform",
          description: "Handles invoicing",
          capabilities: ["Invoicing", "Payment processing"],
          time_classification: "invest",
          r_strategy: null,
          relevance: 0.75,
        },
      ],
    });

    renderWithQuery(
      <OptionCard option={option} designId="d-1" operationId="op-1" onAcceptSuccess={() => {}} />,
    );

    expect(screen.getByText("Reuse Existing Applications")).toBeDefined();
    expect(screen.getByText("Billing Platform")).toBeDefined();
    expect(screen.getByText("invest")).toBeDefined();
    expect(screen.getByText(/Invoicing, Payment processing/)).toBeDefined();
  });

  it("omits the reuse section when there are no reuse candidates", () => {
    mockFetch({});
    renderWithQuery(
      <OptionCard
        option={makeOption({ reuse_candidates: [] })}
        designId="d-1"
        operationId="op-1"
        onAcceptSuccess={() => {}}
      />,
    );

    expect(screen.queryByText("Reuse Existing Applications")).toBeNull();
  });
});
