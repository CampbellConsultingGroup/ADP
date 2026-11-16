// 941-capability-org-mappings US4: the org unit footprint.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { OrgUnitFootprint as Footprint } from "../api/organization";
import OrgUnitFootprint from "./OrgUnitFootprint";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useOrgUnitFootprint: vi.fn(),
}));

const api = vi.mocked(orgApi);
const ref = (id: string, name: string, level = 2) => ({ id, name, level });

const FP: Footprint = {
  org_unit: ref("st", "Stores"),
  includes_descendants: true,
  l3_total: 3,
  performs: [
    {
      capability: ref("sales", "Sales", 1),
      l3_count: 3,
      l2s: [
        {
          capability: ref("pos", "In-Store Transactions"),
          l3_count: 2,
          l3s: [
            { capability: ref("accept", "Accept Payment", 3), performed_by: [{ org_unit: ref("st", "Stores"), geographies: [ref("geo-DE", "Germany", 3)] }] },
            { capability: ref("returns", "Process Returns", 3), performed_by: [{ org_unit: ref("ops", "Store Ops", 3), geographies: [] }] },
          ],
        },
        { capability: ref("promo", "Promotions"), l3_count: 1, l3s: [{ capability: ref("apply", "Apply Promotions", 3), performed_by: [{ org_unit: ref("st", "Stores"), geographies: [] }] }] },
      ],
    },
  ],
  owns: [{ capability: { ...ref("pos", "In-Store Transactions"), path: [] }, org_unit: ref("st", "Stores") }],
  contributes: [{ capability: { ...ref("repl", "Replenishment", 3), path: [] }, org_unit: ref("ops", "Store Ops", 3) }],
};

beforeEach(() => {
  vi.clearAllMocks();
  api.useOrgUnitFootprint.mockReturnValue({ data: FP, isLoading: false, error: null } as never);
});

describe("OrgUnitFootprint", () => {
  it("groups L1 -> L2 -> L3 with counts", () => {
    render(<OrgUnitFootprint orgUnitId="st" />);
    expect(screen.getByText("Performs (3 L3 capabilities, including sub-units)")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Sales" }).parentElement?.textContent).toContain("(3)");
    expect(screen.getAllByRole("button", { name: "In-Store Transactions" })).toHaveLength(2);
    expect(screen.getByText("— Germany")).toBeTruthy();
  });

  it("attributes sub-units' work to them", () => {
    render(<OrgUnitFootprint orgUnitId="st" />);
    const returns = screen.getByRole("button", { name: "Process Returns" }).closest("li");
    expect(returns?.textContent).toBe("Process Returns — Store Ops");
    // Work the unit does itself isn't labelled with its own name.
    const promos = screen.getByRole("button", { name: "Apply Promotions" }).closest("li");
    expect(promos?.textContent).toBe("Apply Promotions");
  });

  it("lists what it owns and contributes to", () => {
    render(<OrgUnitFootprint orgUnitId="st" />);
    expect(screen.getByText("Owns (1)")).toBeTruthy();
    expect(screen.getByText("Contributes to (1)")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Replenishment" })).toBeTruthy();
  });

  it("opens capabilities", async () => {
    const open = vi.fn();
    render(<OrgUnitFootprint orgUnitId="st" onOpenCapability={open} />);
    await userEvent.click(screen.getByRole("button", { name: "Accept Payment" }));
    expect(open).toHaveBeenCalledWith("accept");
  });

  it("says so when there are no mappings", () => {
    api.useOrgUnitFootprint.mockReturnValue({
      data: { ...FP, l3_total: 0, performs: [], owns: [], contributes: [] },
      isLoading: false,
      error: null,
    } as never);
    render(<OrgUnitFootprint orgUnitId="st" />);
    expect(screen.getByText(/no capability mappings yet/)).toBeTruthy();
    expect(screen.getByText("Performs (0 L3 capabilities, including sub-units)")).toBeTruthy();
  });

  it("uses the singular for one capability", () => {
    api.useOrgUnitFootprint.mockReturnValue({ data: { ...FP, l3_total: 1 }, isLoading: false, error: null } as never);
    render(<OrgUnitFootprint orgUnitId="st" />);
    expect(screen.getByText("Performs (1 L3 capability, including sub-units)")).toBeTruthy();
  });
});
