// ADP-68z: mirrors the vi.mock(hooks-module) convention established by
// BusinessValueAssessmentModal.test.tsx -- no AdminPage.test.tsx exists to
// mirror instead (research.md D6).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ScoringRubricsPage from "./ScoringRubricsPage";
import * as adminRubricsApi from "../api/adminRubrics";
import type { RubricListResponse } from "../api/adminRubrics";

vi.mock("../api/adminRubrics");

const mockedApi = vi.mocked(adminRubricsApi);

const RUBRICS: RubricListResponse = {
  items: [
    {
      rubric_id: "business_value",
      display_name: "Business Value Assessment",
      dimension_labels: { strategic_alignment: "Strategic Alignment" },
      active_weights: { strategic_alignment: 0.25 },
      is_override: false,
      version: 0,
    },
  ],
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useRubrics.mockReturnValue({
    data: RUBRICS,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof adminRubricsApi.useRubrics>);
  mockedApi.useRubricHistory.mockReturnValue({
    data: { items: [] },
    isLoading: false,
  } as unknown as ReturnType<typeof adminRubricsApi.useRubricHistory>);
  mockedApi.useConfirmRubricEdit.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof adminRubricsApi.useConfirmRubricEdit>);
  mockedApi.useRestoreRubricVersion.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof adminRubricsApi.useRestoreRubricVersion>);
});

describe("ScoringRubricsPage", () => {
  it("lists registered rubrics with a Default/Custom badge", () => {
    render(<ScoringRubricsPage />);
    expect(screen.getByText("Business Value Assessment")).toBeTruthy();
    expect(screen.getByText("Default")).toBeTruthy();
  });

  it("prompts to select a rubric before any tabs are shown", () => {
    render(<ScoringRubricsPage />);
    expect(screen.getByText(/Select a rubric/)).toBeTruthy();
    expect(screen.queryByText("Edit")).toBeNull();
  });

  it("selecting a rubric shows Edit/History tabs, defaulting to Edit", async () => {
    const user = userEvent.setup();
    render(<ScoringRubricsPage />);

    await user.click(screen.getByText("Business Value Assessment"));

    expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "History" })).toBeTruthy();
    // The Edit tab's own content (a numeric input) renders by default.
    expect(screen.getByRole("spinbutton")).toBeTruthy();
  });

  it("switching to the History tab renders the empty-history message", async () => {
    const user = userEvent.setup();
    render(<ScoringRubricsPage />);

    await user.click(screen.getByText("Business Value Assessment"));
    await user.click(screen.getByRole("button", { name: "History" }));

    expect(screen.getByText("No changes recorded yet.")).toBeTruthy();
  });
});
