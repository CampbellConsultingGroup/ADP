// 941-capability-org-mappings: owner/performer chips and the Organization expander (US1, US2).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { CapabilityOrgView, Geography, OrgUnit } from "../api/organization";
import { CapabilityOrgChips, CapabilityOrgEditor } from "./CapabilityOrgPanel";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useCapabilityOrgMappings: vi.fn(),
  useOrgUnits: vi.fn(),
  useGeographies: vi.fn(),
  useSetCapabilityOwner: vi.fn(),
  useAddCapabilityMapping: vi.fn(),
  useRemoveCapabilityMapping: vi.fn(),
}));

const api = vi.mocked(orgApi);

const ref = (id: string, name: string, level = 2) => ({ id, name, level });
const ou = (id: string, name: string, geos: string[] = []): OrgUnit => ({
  id, name, description: null, parent_id: null, level: 2, kind: "division", primary_geography_id: null,
  geography_ids: geos, path: [], application_count: 0, created_at: "", updated_at: "",
});
const geo = (id: string, name: string, kind: Geography["kind"] = "country"): Geography => ({
  id, name, code: null, m49: null, parent_id: null, level: kind === "country" ? 3 : 2, kind, path: [], org_unit_count: 0,
});

const VIEWS: CapabilityOrgView[] = [
  { capability_id: "pay", level: 2, owner: ref("st", "Stores"), effective_owner: ref("st", "Stores"), owner_inherited_from: null, performers: [], contributors: [] },
  {
    capability_id: "accept",
    level: 3,
    owner: null,
    effective_owner: ref("st", "Stores"),
    owner_inherited_from: ref("pay", "Payments"),
    performers: [
      { id: "m1", capability_id: "accept", org_unit: ref("st", "Stores"), role: "performer", geography: ref("geo-DE", "Germany", 3), outside_operating_geographies: false },
      { id: "m2", capability_id: "accept", org_unit: ref("st", "Stores"), role: "performer", geography: ref("geo-BR", "Brazil", 3), outside_operating_geographies: true },
      { id: "m3", capability_id: "accept", org_unit: ref("ec", "E-commerce"), role: "performer", geography: null, outside_operating_geographies: false },
    ],
    contributors: [{ id: "m4", capability_id: "accept", org_unit: ref("fin", "Finance"), role: "contributor", geography: null, outside_operating_geographies: false }],
  },
];

let setOwner: ReturnType<typeof vi.fn>;
let add: ReturnType<typeof vi.fn>;
let remove: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  setOwner = vi.fn().mockResolvedValue({});
  add = vi.fn().mockResolvedValue({});
  remove = vi.fn().mockResolvedValue(undefined);
  api.useCapabilityOrgMappings.mockReturnValue({ data: { items: VIEWS } } as never);
  api.useOrgUnits.mockReturnValue({ data: { items: [ou("st", "Stores", ["geo-DE"]), ou("ec", "E-commerce"), ou("fin", "Finance")], total: 3 } } as never);
  api.useGeographies.mockReturnValue({ data: { items: [geo("geo-001", "Global", "global"), geo("geo-DE", "Germany"), geo("geo-BR", "Brazil")], total: 3 } } as never);
  api.useSetCapabilityOwner.mockReturnValue({ mutateAsync: setOwner, isPending: false } as never);
  api.useAddCapabilityMapping.mockReturnValue({ mutateAsync: add, isPending: false } as never);
  api.useRemoveCapabilityMapping.mockReturnValue({ mutateAsync: remove, isPending: false } as never);
});

describe("CapabilityOrgChips", () => {
  it("shows the capability's own owner", () => {
    render(<CapabilityOrgChips capabilityId="pay" level={2} />);
    expect(screen.getByTestId("owner-chip").textContent).toBe("Owner: Stores");
  });

  it("marks an inherited owner and lists distinct performers", () => {
    render(<CapabilityOrgChips capabilityId="accept" level={3} />);
    expect(screen.getByTestId("owner-chip").textContent).toBe("Owner: Stores (inherited)");
    expect(screen.getByTestId("owner-chip").getAttribute("title")).toBe("Owner: Stores, inherited from Payments");
    expect(screen.getByTestId("performer-chip").getAttribute("title")).toBe("Performed by: Stores, E-commerce");
    // Bounded width: a long list must not widen the capability row.
    expect(screen.getByTestId("performer-chip").style.maxWidth).toBe("100%");
    expect(screen.getByTestId("performer-chip").textContent).toBe("Performed by: Stores, E-commerce");
  });

  it("renders nothing when nothing is mapped", () => {
    const { container } = render(<CapabilityOrgChips capabilityId="other" level={1} />);
    expect(container.textContent).toBe("");
  });
});

describe("CapabilityOrgEditor — loading", () => {
  it("says Loading, not 'no org units yet', while org units load", () => {
    api.useOrgUnits.mockReturnValue({ data: undefined, isLoading: true } as never);
    render(<CapabilityOrgEditor capabilityId="pay" level={2} canWrite />);
    expect(screen.getByText("Loading…")).toBeTruthy();
    expect(screen.queryByText(/No org units yet/)).toBeNull();
  });

  it("points to the Organization tab when there are genuinely no org units", () => {
    api.useOrgUnits.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false } as never);
    render(<CapabilityOrgEditor capabilityId="pay" level={2} canWrite />);
    expect(screen.getByText(/No org units yet/)).toBeTruthy();
  });
});

describe("CapabilityOrgEditor — owner (L1/L2)", () => {
  it("sets and clears the owner", async () => {
    render(<CapabilityOrgEditor capabilityId="pay" level={2} canWrite />);
    const select = screen.getByLabelText("Owner") as HTMLSelectElement;
    expect(select.value).toBe("st");
    await userEvent.selectOptions(select, "ec");
    expect(setOwner).toHaveBeenCalledWith({ capabilityId: "pay", orgUnitId: "ec" });
    await userEvent.selectOptions(select, "");
    expect(setOwner).toHaveBeenLastCalledWith({ capabilityId: "pay", orgUnitId: null });
  });

  it("warns when no owner applies, and shows the API's rule on failure", async () => {
    setOwner.mockRejectedValueOnce(new Error("Owners are set at L2 or L1, not L3"));
    render(<CapabilityOrgEditor capabilityId="sell" level={1} canWrite />);
    expect(screen.getByText(/No accountable owner/)).toBeTruthy();
    await userEvent.selectOptions(screen.getByLabelText("Owner"), "st");
    expect(await screen.findByRole("alert")).toBeTruthy();
  });

  it("is read-only for readers", () => {
    render(<CapabilityOrgEditor capabilityId="pay" level={2} canWrite={false} />);
    expect(screen.queryByLabelText("Owner")).toBeNull();
    expect(screen.getByText("Stores")).toBeTruthy();
  });
});

describe("CapabilityOrgEditor — performers and contributors (L3)", () => {
  it("lists performers with geographies, the outside note and contributors", () => {
    render(<CapabilityOrgEditor capabilityId="accept" level={3} canWrite />);
    expect(screen.getByText("Owner: Stores (inherited from Payments)")).toBeTruthy();
    expect(screen.getByText("Stores (Germany)")).toBeTruthy();
    expect(screen.getByText("Stores (Brazil)")).toBeTruthy();
    expect(screen.getAllByText("outside where it operates")).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Remove contributor Finance" })).toBeTruthy();
  });

  it("adds a performer with a geography, offering the unit's operating places first", async () => {
    render(<CapabilityOrgEditor capabilityId="accept" level={3} canWrite />);
    await userEvent.selectOptions(screen.getByLabelText("Org unit"), "st");
    const geos = screen.getByLabelText("Geography") as HTMLSelectElement;
    expect(Array.from(geos.querySelectorAll("optgroup")).map((g) => g.label)).toEqual(["Where it operates", "Elsewhere"]);
    expect(Array.from(geos.options).map((o) => o.textContent)).not.toContain("Global");
    await userEvent.selectOptions(geos, "geo-DE");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(add).toHaveBeenCalledWith({ capability_id: "accept", org_unit_id: "st", role: "performer", geography_id: "geo-DE" });
  });

  it("adds a contributor without a geography and removes a mapping", async () => {
    render(<CapabilityOrgEditor capabilityId="accept" level={3} canWrite />);
    await userEvent.selectOptions(screen.getByLabelText("Role"), "contributor");
    expect(screen.queryByLabelText("Geography")).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText("Org unit"), "ec");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(add).toHaveBeenCalledWith({ capability_id: "accept", org_unit_id: "ec", role: "contributor", geography_id: null });
    await userEvent.click(screen.getByRole("button", { name: "Remove contributor Finance" }));
    expect(remove).toHaveBeenCalledWith("m4");
  });

  it("shows the server's rule when adding fails", async () => {
    add.mockRejectedValueOnce(new Error("That org unit is already a performer of this capability"));
    render(<CapabilityOrgEditor capabilityId="accept" level={3} canWrite />);
    await userEvent.selectOptions(screen.getByLabelText("Org unit"), "ec");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect((await screen.findByRole("alert")).textContent).toContain("already a performer");
  });

  it("hides controls for readers", () => {
    render(<CapabilityOrgEditor capabilityId="accept" level={3} canWrite={false} />);
    expect(screen.queryByRole("button", { name: "Add" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Remove/ })).toBeNull();
  });
});
