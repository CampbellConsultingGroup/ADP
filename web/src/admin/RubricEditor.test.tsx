// ADP-68z: mirrors BusinessValueAssessmentModal.test.tsx's vi.mock(hooks-module)
// convention -- no PromptEditor.test.tsx exists to mirror instead (research.md D6).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RubricEditor from "./RubricEditor";
import * as adminRubricsApi from "../api/adminRubrics";
import { ApiError } from "../api/client";
import type { RubricView } from "../api/adminRubrics";

vi.mock("../api/adminRubrics");

const mockedApi = vi.mocked(adminRubricsApi);

const RUBRIC: RubricView = {
  rubric_id: "business_value",
  display_name: "Business Value Assessment",
  dimension_labels: {
    strategic_alignment: "Strategic Alignment",
    revenue_cost_impact: "Revenue/Cost Impact",
    customer_stakeholder_impact: "Customer/Stakeholder Impact",
    competitive_differentiation: "Competitive Differentiation",
    risk_compliance_contribution: "Risk/Compliance Contribution",
    evidence_measurability: "Evidence & Measurability",
  },
  active_weights: {
    strategic_alignment: 0.25,
    revenue_cost_impact: 0.25,
    customer_stakeholder_impact: 0.15,
    competitive_differentiation: 0.10,
    risk_compliance_contribution: 0.15,
    evidence_measurability: 0.10,
  },
  is_override: false,
  version: 0,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useConfirmRubricEdit.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof adminRubricsApi.useConfirmRubricEdit>);
});

describe("RubricEditor", () => {
  it("renders all six dimensions with their current percentage weights", () => {
    render(<RubricEditor rubric={RUBRIC} onDirtyChange={vi.fn()} />);

    expect(screen.getByText("Strategic Alignment")).toBeTruthy();
    expect(screen.getByText("Evidence & Measurability")).toBeTruthy();
    const inputs = screen.getAllByRole("spinbutton") as HTMLInputElement[];
    expect(inputs.map((i) => i.value)).toEqual(["25", "25", "15", "10", "15", "10"]);
    expect(screen.getByText("100%")).toBeTruthy();
  });

  it("disables Save until a weight actually changes", async () => {
    render(<RubricEditor rubric={RUBRIC} onDirtyChange={vi.fn()} />);
    const saveButton = screen.getByRole("button", { name: "Save" });
    expect(saveButton.hasAttribute("disabled")).toBe(true);
  });

  it("blocks Save when the weights don't sum to 100%", async () => {
    const user = userEvent.setup();
    render(<RubricEditor rubric={RUBRIC} onDirtyChange={vi.fn()} />);

    const inputs = screen.getAllByRole("spinbutton");
    await user.clear(inputs[0]);
    await user.type(inputs[0], "30"); // now sums to 105

    expect(screen.getByText(/must sum to 100%/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save" }).hasAttribute("disabled")).toBe(true);
  });

  it("enables Save and shows the confirmation dialog once weights change and still sum to 100%", async () => {
    const user = userEvent.setup();
    render(<RubricEditor rubric={RUBRIC} onDirtyChange={vi.fn()} />);

    const inputs = screen.getAllByRole("spinbutton");
    await user.clear(inputs[0]); // strategic_alignment 25 -> 35
    await user.type(inputs[0], "35");
    await user.clear(inputs[1]); // revenue_cost_impact 25 -> 15
    await user.type(inputs[1], "15");

    const saveButton = screen.getByRole("button", { name: "Save" });
    expect(saveButton.hasAttribute("disabled")).toBe(false);
    await user.click(saveButton);

    expect(screen.getByText("Confirm weight change")).toBeTruthy();
  });

  it("calls confirmEdit.mutate with the converted 0-1 fraction weights on confirm", async () => {
    const mutate = vi.fn();
    mockedApi.useConfirmRubricEdit.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof adminRubricsApi.useConfirmRubricEdit>);

    const user = userEvent.setup();
    render(<RubricEditor rubric={RUBRIC} onDirtyChange={vi.fn()} />);

    const inputs = screen.getAllByRole("spinbutton");
    await user.clear(inputs[0]);
    await user.type(inputs[0], "35");
    await user.clear(inputs[1]);
    await user.type(inputs[1], "15");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await user.click(screen.getByRole("button", { name: "Confirm & Save" }));

    expect(mutate).toHaveBeenCalledWith(
      expect.objectContaining({
        weights: expect.objectContaining({
          strategic_alignment: 0.35,
          revenue_cost_impact: 0.15,
        }),
        expectedVersion: 0,
      }),
      expect.anything(),
    );
  });

  it("shows a reload option on a 409 version conflict, not a generic error", async () => {
    const mutate = vi.fn((_body, opts) => {
      opts?.onError?.(
        new ApiError(409, "conflict", {
          detail: {
            current_active_weights: { ...RUBRIC.active_weights, strategic_alignment: 0.40 },
            current_version: 2,
          },
        }),
      );
    });
    mockedApi.useConfirmRubricEdit.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof adminRubricsApi.useConfirmRubricEdit>);

    const user = userEvent.setup();
    render(<RubricEditor rubric={RUBRIC} onDirtyChange={vi.fn()} />);

    const inputs = screen.getAllByRole("spinbutton");
    await user.clear(inputs[0]);
    await user.type(inputs[0], "35");
    await user.clear(inputs[1]);
    await user.type(inputs[1], "15");
    await user.click(screen.getByRole("button", { name: "Save" }));
    await user.click(screen.getByRole("button", { name: "Confirm & Save" }));

    expect(screen.getByText(/changed since you loaded them/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Load latest version" })).toBeTruthy();
  });
});
