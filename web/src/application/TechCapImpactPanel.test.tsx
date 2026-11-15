// 938-capability-model-analysis US3: the Impact panel on a technical capability.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as capAnalysisApi from "../api/capAnalysis";
import type { ImpactResult } from "../api/capAnalysis";
import { AppCapNavContext, CapabilityNavContext } from "./appCapNav";
import TechCapImpactPanel from "./TechCapImpactPanel";

vi.mock("../api/capAnalysis", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/capAnalysis")>()),
  useTechCapImpact: vi.fn(),
}));

const api = vi.mocked(capAnalysisApi);

const ref = (id: string, name: string, level = 3) => ({ id, name, level });

const IMPACT: ImpactResult = {
  technical_capability: { ...ref("tc", "Offline Sync"), path: [ref("t1", "Integration", 1), ref("t2", "Data Storage", 2)] },
  covered_technical: [ref("tc", "Offline Sync")],
  application_capabilities: [{ ...ref("ac", "Basket Calculation"), path: [], via_technical: [ref("tc", "Offline Sync")] }],
  applications: [
    { id: "pos", name: "Store POS", lifecycle_status: "active", via: [ref("ac", "Basket Calculation")] },
    { id: "old", name: "Legacy Till", lifecycle_status: "retired", via: [ref("ac", "Basket Calculation")] },
  ],
  business_capabilities: [
    { ...ref("b3", "Process Checkout"), path: [ref("b1", "Sales", 1), ref("b2", "In-Store", 2)], routes: [ref("ac", "Basket Calculation"), ref("ac2", "Other")] },
  ],
};

function mockImpact(data: ImpactResult | undefined) {
  api.useTechCapImpact.mockReturnValue({ data, isLoading: false, error: null } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  mockImpact(IMPACT);
});

describe("TechCapImpactPanel", () => {
  it("is collapsed until opened, and only then fetches", async () => {
    const user = userEvent.setup();
    render(<TechCapImpactPanel tcId="tc" />);
    expect(api.useTechCapImpact).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /Impact/ }));
    expect(api.useTechCapImpact).toHaveBeenCalledWith("tc");
  });

  it("lists exposed business capabilities with their path and route count, apps and app capabilities", async () => {
    const user = userEvent.setup();
    render(<TechCapImpactPanel tcId="tc" />);
    await user.click(screen.getByRole("button", { name: /Impact/ }));
    expect(screen.getByText("Process Checkout")).toBeTruthy();
    expect(screen.getByText(/Sales › In-Store/)).toBeTruthy();
    expect(screen.getByText(/2 routes/)).toBeTruthy();
    expect(screen.getByText("Basket Calculation")).toBeTruthy();
    expect(screen.getByText("Store POS")).toBeTruthy();
    expect(screen.getByText("(retired)")).toBeTruthy();
  });

  it("says when nothing depends on the capability", async () => {
    mockImpact({ ...IMPACT, application_capabilities: [], applications: [], business_capabilities: [] });
    const user = userEvent.setup();
    render(<TechCapImpactPanel tcId="tc" />);
    await user.click(screen.getByRole("button", { name: /Impact/ }));
    expect(screen.getByText("Nothing depends on this technical capability.")).toBeTruthy();
  });

  it("navigates to each item's own screen", async () => {
    const nav = { openBusinessCapability: vi.fn(), openApplication: vi.fn(), openTechnicalCapability: vi.fn() };
    const openAppCap = vi.fn();
    const user = userEvent.setup();
    render(
      <AppCapNavContext.Provider value={openAppCap}>
        <CapabilityNavContext.Provider value={nav}>
          <TechCapImpactPanel tcId="tc" />
        </CapabilityNavContext.Provider>
      </AppCapNavContext.Provider>,
    );
    await user.click(screen.getByRole("button", { name: /Impact/ }));
    await user.click(screen.getByRole("button", { name: "Process Checkout" }));
    await user.click(screen.getByRole("button", { name: "Store POS" }));
    await user.click(screen.getByRole("button", { name: "Basket Calculation" }));
    expect(nav.openBusinessCapability).toHaveBeenCalledWith("b3");
    expect(nav.openApplication).toHaveBeenCalledWith("pos");
    expect(openAppCap).toHaveBeenCalledWith("ac");
  });
});
