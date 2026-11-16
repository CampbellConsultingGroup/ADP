// 941-capability-org-mappings US3: the Findings sub-tab.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { CapabilityOrgFindings } from "../api/organization";
import OrgFindings from "./OrgFindings";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useCapabilityOrgFindings: vi.fn(),
}));

const api = vi.mocked(orgApi);
const ref = (id: string, name: string, level = 2) => ({ id, name, level });
const cap = (id: string, name: string, level: number, path: string[] = []) => ({
  id, name, level, path: path.map((p, i) => ref(`p${i}`, p, i + 1)),
});

const FINDINGS: CapabilityOrgFindings = {
  no_owner: [cap("merch", "Merchandising", 1)],
  shared_service: [
    {
      capability: cap("accept", "Accept Payment", 3, ["Sales", "In-Store"]),
      branches: 2,
      performers: [
        { org_unit: ref("dg", "Digital"), org_unit_path: [], geographies: [], folded_into: null },
        { org_unit: ref("st", "Stores"), org_unit_path: [], geographies: [ref("geo-DE", "Germany", 3), ref("geo-US", "United States", 3)], folded_into: null },
        { org_unit: ref("ops", "Store Ops", 3), org_unit_path: [], geographies: [], folded_into: ref("st", "Stores") },
      ],
    },
  ],
  unmapped: [cap("range", "Range Planning", 3, ["Merchandising", "Assortment"])],
  owned_no_performer: [],
  counts: { no_owner: 1, shared_service: 1, unmapped: 1, owned_no_performer: 0, l1_l2_total: 12, l3_total: 20 },
};

beforeEach(() => {
  vi.clearAllMocks();
  api.useCapabilityOrgFindings.mockReturnValue({ data: FINDINGS, isLoading: false, error: null } as never);
});

describe("OrgFindings", () => {
  it("shows the four lists with counts", () => {
    render(<OrgFindings />);
    expect(within(screen.getByRole("region", { name: "No accountable owner" })).getByText("(1 of 12)")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Unmapped" })).getByText("(1 of 20)")).toBeTruthy();
    expect(within(screen.getByRole("region", { name: "Shared-service candidates" })).getByText("(1)")).toBeTruthy();
    expect(screen.getByText("Merchandising")).toBeTruthy();
    expect(screen.getByText("Merchandising › Assortment")).toBeTruthy();
  });

  it("lists each shared-service performer with geographies and folded units", () => {
    render(<OrgFindings />);
    const shared = screen.getByRole("region", { name: "Shared-service candidates" });
    expect(within(shared).getByText("2 independent performers")).toBeTruthy();
    expect(within(shared).getByText(/Germany, United States/)).toBeTruthy();
    expect(within(shared).getByText("(part of Stores)")).toBeTruthy();
  });

  it("opens a capability when an entry is clicked", async () => {
    const open = vi.fn();
    render(<OrgFindings onOpenCapability={open} />);
    await userEvent.click(screen.getByRole("button", { name: "Accept Payment" }));
    expect(open).toHaveBeenCalledWith("accept");
    await userEvent.click(screen.getByRole("button", { name: "Range Planning" }));
    expect(open).toHaveBeenLastCalledWith("range");
  });

  it("shows an empty message per list", () => {
    render(<OrgFindings />);
    expect(screen.getByText("Every owned L3 capability has a performer.")).toBeTruthy();
  });

  it("shows loading and error states", () => {
    api.useCapabilityOrgFindings.mockReturnValue({ data: undefined, isLoading: true, error: null } as never);
    const { unmount } = render(<OrgFindings />);
    expect(screen.getByText("Loading…")).toBeTruthy();
    unmount();
    api.useCapabilityOrgFindings.mockReturnValue({ data: undefined, isLoading: false, error: new Error("x") } as never);
    render(<OrgFindings />);
    expect(screen.getByRole("alert").textContent).toContain("Failed to load findings");
  });
});
