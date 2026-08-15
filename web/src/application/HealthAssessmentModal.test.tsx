// docs/application-health-assessment-spec.md. Mirrors this session's
// vi.mock(hooks-module) convention (e.g. CapabilityTree.test.tsx).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import HealthAssessmentModal from "./HealthAssessmentModal";
import * as applicationApi from "../api/application";

vi.mock("../api/application");

const mockedApi = vi.mocked(applicationApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useHealthAssessment.mockReturnValue({
    data: { application_id: "app-1", entries: [], health_score: null },
    isLoading: false,
  } as unknown as ReturnType<typeof applicationApi.useHealthAssessment>);
  mockedApi.useSaveHealthAssessment.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof applicationApi.useSaveHealthAssessment>);
});

describe("HealthAssessmentModal", () => {
  it("renders all six dimensions and five score columns", () => {
    render(<HealthAssessmentModal appId="app-1" onClose={vi.fn()} />);

    expect(screen.getByText("Stability & Incidents")).toBeTruthy();
    expect(screen.getByText("Technical Currency & Debt")).toBeTruthy();
    expect(screen.getByText("Security Posture")).toBeTruthy();
    expect(screen.getByText("Support & Team Capacity")).toBeTruthy();
    expect(screen.getByText("Documentation & Knowledge")).toBeTruthy();
    expect(screen.getByText("Business Value & Criticality Alignment")).toBeTruthy();
    expect(screen.getByText("1 — Critical")).toBeTruthy();
    expect(screen.getByText("5 — Thriving")).toBeTruthy();
  });

  it("disables Save until all six dimensions are answered", async () => {
    const user = userEvent.setup();
    render(<HealthAssessmentModal appId="app-1" onClose={vi.fn()} />);

    const saveButton = screen.getByRole("button", { name: /^Save$/ });
    expect(saveButton.hasAttribute("disabled")).toBe(true);

    // Answer 5 of 6 dimensions -- still disabled.
    const radios = screen.getAllByRole("radio");
    for (let i = 0; i < 25; i += 5) await user.click(radios[i]);
    expect(saveButton.hasAttribute("disabled")).toBe(true);

    // Answer the sixth -- now enabled.
    await user.click(radios[25]);
    expect(saveButton.hasAttribute("disabled")).toBe(false);
  });

  it("pre-fills radios from an existing assessment", () => {
    mockedApi.useHealthAssessment.mockReturnValue({
      data: {
        application_id: "app-1",
        entries: [
          { dimension: "stability_incidents", score: 2, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "technical_currency_debt", score: 3, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "security_posture", score: 4, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "support_team_capacity", score: 5, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "documentation_knowledge", score: 1, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
          { dimension: "business_value_criticality", score: 3, assessed_at: "2026-01-01T00:00:00Z", assessed_by: "jane" },
        ],
        health_score: 1,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof applicationApi.useHealthAssessment>);

    render(<HealthAssessmentModal appId="app-1" onClose={vi.fn()} />);

    const checkedRadios = screen.getAllByRole("radio").filter((r) => (r as HTMLInputElement).checked);
    expect(checkedRadios).toHaveLength(6);
    // All six pre-filled -- Save is already enabled.
    expect(screen.getByRole("button", { name: /^Save$/ }).hasAttribute("disabled")).toBe(false);
    expect(screen.getByText(/Resulting health score: 1/)).toBeTruthy();
  });

  it("submits all six scores and closes on success", async () => {
    const mutate = vi.fn((_body, opts) => opts?.onSuccess?.());
    mockedApi.useSaveHealthAssessment.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof applicationApi.useSaveHealthAssessment>);
    const onClose = vi.fn();

    const user = userEvent.setup();
    render(<HealthAssessmentModal appId="app-1" onClose={onClose} />);

    const radios = screen.getAllByRole("radio");
    for (let i = 0; i < 30; i += 5) await user.click(radios[i]); // first option in each row
    await user.click(screen.getByRole("button", { name: /^Save$/ }));

    expect(mutate).toHaveBeenCalledWith(
      {
        stability_incidents: 1,
        technical_currency_debt: 1,
        security_posture: 1,
        support_team_capacity: 1,
        documentation_knowledge: 1,
        business_value_criticality: 1,
      },
      expect.anything(),
    );
    expect(onClose).toHaveBeenCalled();
  });

  it("Cancel closes without saving", async () => {
    const mutate = vi.fn();
    mockedApi.useSaveHealthAssessment.mockReturnValue({
      mutate,
      isPending: false,
      isError: false,
    } as unknown as ReturnType<typeof applicationApi.useSaveHealthAssessment>);
    const onClose = vi.fn();

    const user = userEvent.setup();
    render(<HealthAssessmentModal appId="app-1" onClose={onClose} />);
    await user.click(screen.getByRole("button", { name: "Cancel" }));

    expect(onClose).toHaveBeenCalled();
    expect(mutate).not.toHaveBeenCalled();
  });
});
