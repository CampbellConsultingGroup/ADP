// docs/application-business-value-assessment-spec.md. Mirrors
// HealthAssessmentModal.test.tsx's vi.mock(hooks-module) convention --
// both popups render through the shared AssessmentModal.tsx now, so this
// file exercises the BusinessValueAssessmentModal wrapper's own rubric,
// hooks, and weighted-average+cap result copy specifically.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import BusinessValueAssessmentModal from "./BusinessValueAssessmentModal";
import * as applicationApi from "../api/application";

vi.mock("../api/application");

const mockedApi = vi.mocked(applicationApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useBusinessValueAssessment.mockReturnValue({
    data: { application_id: "app-1", entries: [], result: null },
    isLoading: false,
  } as unknown as ReturnType<typeof applicationApi.useBusinessValueAssessment>);
  mockedApi.useSaveBusinessValueAssessment.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof applicationApi.useSaveBusinessValueAssessment>);
});

describe("BusinessValueAssessmentModal", () => {
  it("renders all six dimensions and five score columns", () => {
    render(<BusinessValueAssessmentModal appId="app-1" onClose={vi.fn()} />);

    expect(screen.getByText("Strategic Alignment")).toBeTruthy();
    expect(screen.getByText("Revenue / Cost Impact")).toBeTruthy();
    expect(screen.getByText("Customer / Stakeholder Impact")).toBeTruthy();
    expect(screen.getByText("Competitive Differentiation")).toBeTruthy();
    expect(screen.getByText("Risk / Compliance Contribution")).toBeTruthy();
    expect(screen.getByText("Evidence & Measurability")).toBeTruthy();
    expect(screen.getByText("1 — Minimal")).toBeTruthy();
    expect(screen.getByText("5 — Exceptional")).toBeTruthy();
  });

  it("disables Save until all six dimensions are answered", async () => {
    const user = userEvent.setup();
    render(<BusinessValueAssessmentModal appId="app-1" onClose={vi.fn()} />);

    const saveButton = screen.getByRole("button", { name: /^Save$/ });
    expect(saveButton.hasAttribute("disabled")).toBe(true);

    const radios = screen.getAllByRole("radio");
    for (let i = 0; i < 25; i += 5) await user.click(radios[i]);
    expect(saveButton.hasAttribute("disabled")).toBe(true);

    await user.click(radios[25]);
    expect(saveButton.hasAttribute("disabled")).toBe(false);
  });

  it("pre-fills radios from an existing assessment", () => {
    mockedApi.useBusinessValueAssessment.mockReturnValue({
      data: {
        application_id: "app-1",
        entries: [
          { dimension: "strategic_alignment", score: 5, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "revenue_cost_impact", score: 5, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "customer_stakeholder_impact", score: 4, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "competitive_differentiation", score: 4, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "risk_compliance_contribution", score: 3, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "evidence_measurability", score: 1, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
        ],
        result: { business_value: 2, weighted_average: 4.05, evidence_score: 1, cap: 2, capped: true },
      },
      isLoading: false,
    } as unknown as ReturnType<typeof applicationApi.useBusinessValueAssessment>);

    render(<BusinessValueAssessmentModal appId="app-1" onClose={vi.fn()} />);

    const checkedRadios = screen.getAllByRole("radio").filter((r) => (r as HTMLInputElement).checked);
    expect(checkedRadios).toHaveLength(6);
    expect(screen.getByRole("button", { name: /^Save$/ }).hasAttribute("disabled")).toBe(false);
  });

  it("shows the weighted average and cap math -- spec's own worked example, always shown", () => {
    mockedApi.useBusinessValueAssessment.mockReturnValue({
      data: {
        application_id: "app-1",
        entries: [
          { dimension: "strategic_alignment", score: 5, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "revenue_cost_impact", score: 5, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "customer_stakeholder_impact", score: 4, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "competitive_differentiation", score: 4, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "risk_compliance_contribution", score: 3, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "evidence_measurability", score: 1, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
        ],
        result: { business_value: 2, weighted_average: 4.05, evidence_score: 1, cap: 2, capped: true },
      },
      isLoading: false,
    } as unknown as ReturnType<typeof applicationApi.useBusinessValueAssessment>);

    render(<BusinessValueAssessmentModal appId="app-1" onClose={vi.fn()} />);

    expect(screen.getByText(/Resulting business value: 2/)).toBeTruthy();
    expect(screen.getByText(/weighted average 4\.05/)).toBeTruthy();
    expect(screen.getByText(/capped by Evidence & Measurability \(score 1\) at 2/)).toBeTruthy();
  });

  it("shows 'no cap applied' when evidence is strong, even though the cap math is always displayed", async () => {
    const user = userEvent.setup();
    render(<BusinessValueAssessmentModal appId="app-1" onClose={vi.fn()} />);

    // Select the 5th option (score 5) in every row, including Evidence.
    const radios = screen.getAllByRole("radio");
    for (let i = 4; i < 30; i += 5) await user.click(radios[i]);

    expect(screen.getByText(/Resulting business value: 5/)).toBeTruthy();
    expect(screen.getByText(/no cap applied/)).toBeTruthy();
  });

  it("submits all six scores and closes on success", async () => {
    const mutate = vi.fn((_body, opts) => opts?.onSuccess?.());
    mockedApi.useSaveBusinessValueAssessment.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof applicationApi.useSaveBusinessValueAssessment>);
    const onClose = vi.fn();

    const user = userEvent.setup();
    render(<BusinessValueAssessmentModal appId="app-1" onClose={onClose} />);

    const radios = screen.getAllByRole("radio");
    for (let i = 0; i < 30; i += 5) await user.click(radios[i]); // first option in each row
    await user.click(screen.getByRole("button", { name: /^Save$/ }));

    expect(mutate).toHaveBeenCalledWith(
      {
        strategic_alignment: 1,
        revenue_cost_impact: 1,
        customer_stakeholder_impact: 1,
        competitive_differentiation: 1,
        risk_compliance_contribution: 1,
        evidence_measurability: 1,
      },
      expect.anything(),
    );
    expect(onClose).toHaveBeenCalled();
  });

  it("Cancel closes without saving", async () => {
    const mutate = vi.fn();
    mockedApi.useSaveBusinessValueAssessment.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof applicationApi.useSaveBusinessValueAssessment>);
    const onClose = vi.fn();

    const user = userEvent.setup();
    render(<BusinessValueAssessmentModal appId="app-1" onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(mutate).not.toHaveBeenCalled();
  });
});
