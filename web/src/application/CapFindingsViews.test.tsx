// 938-capability-model-analysis US5: overlaps, gaps and shared views.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as capAnalysisApi from "../api/capAnalysis";
import type { CapabilityFindings } from "../api/capAnalysis";
import { AppCapNavContext, CapabilityNavContext } from "./appCapNav";
import CapFindingsViews from "./CapFindingsViews";

vi.mock("../api/capAnalysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/capAnalysis")>()),
  useCapabilityFindings: vi.fn(),
}));

const api = vi.mocked(capAnalysisApi);
const ref = (id: string, name: string, level = 3) => ({ id, name, level });
const path = [ref("b1", "Sales", 1), ref("b2", "In-Store", 2)];

const FINDINGS: CapabilityFindings = {
  overlaps: [
    {
      business: { ...ref("b4", "Apply Promotions"), path },
      applications: [
        { id: "commerce", name: "Commerce Cloud", via: [ref("ac9", "Online Promotion Evaluation")] },
        { id: "pos", name: "Store POS", via: [ref("ac2", "Price Rule Evaluation")] },
      ],
    },
  ],
  gaps: {
    business_without_app_capability: [{ ...ref("b5", "Process Returns"), path }],
    app_capability_without_business: [{ ...ref("ac7", "Loyalty Points Accrual"), path: [] }],
    app_capability_without_application: [],
  },
  shared: [{ app_capability: { ...ref("ac3", "Customer Lookup"), path: [] }, business: [ref("x", "A"), ref("y", "B"), ref("z", "C")], count: 3 }],
  shared_threshold: 3,
};

function mockFindings(data: CapabilityFindings) {
  api.useCapabilityFindings.mockReturnValue({ data, isLoading: false, error: null } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockFindings(FINDINGS);
});

describe("CapFindingsViews", () => {
  it("lists overlaps with each application and the capability it acts through", () => {
    render(<CapFindingsViews mode="overlaps" />);
    const view = screen.getByLabelText("Overlaps");
    expect(within(view).getByText("Apply Promotions")).toBeTruthy();
    expect(within(view).getByText("Commerce Cloud")).toBeTruthy();
    expect(within(view).getByText("Online Promotion Evaluation")).toBeTruthy();
    expect(within(view).getByText("Price Rule Evaluation")).toBeTruthy();
  });

  it("shows the three gap lists with paths and empty states", () => {
    render(<CapFindingsViews mode="gaps" />);
    expect(screen.getByRole("region", { name: "Business capabilities with no application capability" })).toBeTruthy();
    expect(screen.getByText("Process Returns")).toBeTruthy();
    expect(screen.getAllByText(/Sales › In-Store/).length).toBeGreaterThan(0);
    expect(screen.getByText("Loyalty Points Accrual")).toBeTruthy();
    expect(screen.getByText("Every Level 3 application capability is realized by an application.")).toBeTruthy();
  });

  it("labels shared as informational", () => {
    render(<CapFindingsViews mode="shared" />);
    expect(screen.getByText(/Informational, not a problem/)).toBeTruthy();
    expect(screen.getByText("Customer Lookup")).toBeTruthy();
    expect(screen.getByText(/supports 3/)).toBeTruthy();
  });

  it("shows empty states", () => {
    mockFindings({ ...FINDINGS, overlaps: [], shared: [] });
    const { rerender } = render(<CapFindingsViews mode="overlaps" />);
    expect(screen.getByText("No business capability is realized by more than one application.")).toBeTruthy();
    rerender(<CapFindingsViews mode="shared" />);
    expect(screen.getByText(/No application capability supports 3 or more/)).toBeTruthy();
  });

  it("navigates from every item", async () => {
    const nav = { openBusinessCapability: vi.fn(), openApplication: vi.fn(), openTechnicalCapability: vi.fn() };
    const openAppCap = vi.fn();
    const user = userEvent.setup();
    render(
      <AppCapNavContext.Provider value={openAppCap}>
        <CapabilityNavContext.Provider value={nav}>
          <CapFindingsViews mode="overlaps" />
        </CapabilityNavContext.Provider>
      </AppCapNavContext.Provider>,
    );
    await user.click(screen.getByRole("button", { name: "Apply Promotions" }));
    await user.click(screen.getByRole("button", { name: "Store POS" }));
    await user.click(screen.getByRole("button", { name: "Price Rule Evaluation" }));
    expect(nav.openBusinessCapability).toHaveBeenCalledWith("b4");
    expect(nav.openApplication).toHaveBeenCalledWith("pos");
    expect(openAppCap).toHaveBeenCalledWith("ac2");
  });
});
