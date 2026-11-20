// 940-org-units-geography: Business Architecture -> Organization (US1 tree, US3 detail panel).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { Geography, OrgUnit, OrgUnitDetail } from "../api/organization";
import * as authApi from "../auth/AuthProvider";
import OrganizationTab from "./OrganizationTab";
import { buildOrgUnitTree } from "./OrgUnitTree";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useOrgUnits: vi.fn(),
  useOrgUnit: vi.fn(),
  useGeographies: vi.fn(),
  useUnmatched: vi.fn(),
  useCreateOrgUnit: vi.fn(),
  useUpdateOrgUnit: vi.fn(),
  useDeleteOrgUnit: vi.fn(),
  useLinkGeography: vi.fn(),
  useUnlinkGeography: vi.fn(),
  useDeleteGeography: vi.fn(),
  useResolveUnmatched: vi.fn(),
  useOrgUnitFootprint: vi.fn(),
  useCapabilityOrgFindings: vi.fn(),
}));
vi.mock("../auth/AuthProvider", async (orig) => ({
  ...(await orig<typeof import("../auth/AuthProvider")>()),
  useAuth: vi.fn(),
}));

const api = vi.mocked(orgApi);
const auth = vi.mocked(authApi);

function ou(id: string, name: string, level: number, parent: string | null, over: Partial<OrgUnit> = {}): OrgUnit {
  const kind = (["enterprise", "division", "function"] as const)[level - 1];
  return {
    id, name, description: null, parent_id: parent, level, kind, primary_geography_id: null,
    geography_ids: [], path: [], application_count: 0, created_at: "", updated_at: "", ...over,
  };
}

const geo = (id: string, name: string, kind: Geography["kind"], parent: string | null, code: string | null = null): Geography => ({
  id, name, code, m49: null, parent_id: parent, level: kind === "global" ? 1 : kind === "region" ? 2 : 3, kind, path: [], org_unit_count: 0,
});

const UNITS = [
  ou("rc", "Retail Co", 1, null),
  ou("st", "Stores", 2, "rc", { path: [{ id: "rc", name: "Retail Co", level: 1 }], application_count: 2 }),
  ou("corp", "Corporate", 2, "rc"),
  ou("fin", "Finance", 3, "corp"),
];
const GEOS = [geo("geo-001", "Global", "global", null), geo("geo-m49-150", "Europe", "region", "geo-001"), geo("geo-DE", "Germany", "country", "geo-m49-150", "DE"), geo("geo-FR", "France", "country", "geo-m49-150", "FR")];

let mutate: Record<string, ReturnType<typeof vi.fn>>;

function m(name: string) {
  mutate[name] = vi.fn().mockResolvedValue({ id: "new", name: "x", org_unit: UNITS[1], updated_count: 0 });
  return { mutateAsync: mutate[name], mutate: mutate[name], isPending: false } as never;
}

function setup(role = "enterprise_architect", detail: Partial<OrgUnitDetail> = {}) {
  mutate = {};
  auth.useAuth.mockReturnValue({ user: { role } } as never);
  api.useOrgUnits.mockReturnValue({ data: { items: UNITS, total: UNITS.length }, isLoading: false, error: null } as never);
  api.useGeographies.mockReturnValue({ data: { items: GEOS, total: GEOS.length }, isLoading: false, error: null } as never);
  api.useUnmatched.mockReturnValue({ data: { items: [{ value: "Store Systems", application_count: 3, sample_applications: [] }], total: 1 }, isLoading: false, error: null } as never);
  api.useOrgUnit.mockReturnValue({
    data: { ...UNITS[1], applications: [{ id: "pos", name: "Xstore POS", level: 0 }], geographies: [{ id: "geo-DE", name: "Germany", level: 3 }], geography_ids: ["geo-DE"], ...detail },
    isLoading: false,
  } as never);
  api.useCreateOrgUnit.mockReturnValue(m("create"));
  api.useUpdateOrgUnit.mockReturnValue(m("update"));
  api.useDeleteOrgUnit.mockReturnValue(m("delete"));
  api.useLinkGeography.mockReturnValue(m("link"));
  api.useUnlinkGeography.mockReturnValue(m("unlink"));
  api.useDeleteGeography.mockReturnValue(m("deleteGeo"));
  api.useResolveUnmatched.mockReturnValue(m("resolve"));
  api.useOrgUnitFootprint.mockReturnValue({
    data: { org_unit: UNITS[1], includes_descendants: true, l3_total: 0, performs: [], owns: [], contributes: [] },
    isLoading: false,
    error: null,
  } as never);
  api.useCapabilityOrgFindings.mockReturnValue({
    data: {
      no_owner: [{ id: "c1", name: "Merchandising", level: 1, path: [] }],
      shared_service: [],
      unmapped: [],
      owned_no_performer: [],
      counts: { no_owner: 1, shared_service: 0, unmapped: 0, owned_no_performer: 0, l1_l2_total: 1, l3_total: 0 },
    },
    isLoading: false,
    error: null,
  } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  setup();
});

describe("buildOrgUnitTree", () => {
  it("nests by parent and sorts siblings by name", () => {
    const tree = buildOrgUnitTree(UNITS);
    expect(tree.map((n) => n.name)).toEqual(["Retail Co"]);
    expect(tree[0].children.map((n) => n.name)).toEqual(["Corporate", "Stores"]);
    expect(tree[0].children[0].children.map((n) => n.name)).toEqual(["Finance"]);
  });
});

describe("OrganizationTab — org units (US1)", () => {
  it("renders the tree with kinds and application counts, and the unmatched count on its tab", () => {
    render(<OrganizationTab />);
    expect(screen.getByText("Retail Co")).toBeTruthy();
    expect(screen.getByText("Finance")).toBeTruthy();
    expect(screen.getAllByText("Division / BU")).toHaveLength(2);
    expect(screen.getByText("2 apps")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "Unmatched (1)" })).toBeTruthy();
  });

  it("offers + child only below level 3, and adds an enterprise", async () => {
    render(<OrganizationTab />);
    expect(screen.getByRole("button", { name: "Add child to Corporate" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add child to Finance" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "+ Enterprise" }));
    await userEvent.type(screen.getByLabelText("New org unit name"), "Other Co");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(mutate.create).toHaveBeenCalledWith({ name: "Other Co", parent_id: null });
  });

  it("says Adding… while the create is in flight", async () => {
    api.useCreateOrgUnit.mockReturnValue({ mutateAsync: vi.fn(), mutate: vi.fn(), isPending: true } as never);
    render(<OrganizationTab />);
    await userEvent.click(screen.getByRole("button", { name: "+ Enterprise" }));
    const busy = screen.getByRole("button", { name: "Adding…" }) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
  });

  it("is read-only for reviewers", () => {
    setup("reviewer");
    render(<OrganizationTab />);
    expect(screen.queryByRole("button", { name: "+ Enterprise" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Add child/ })).toBeNull();
  });

  it("shows an empty state", () => {
    api.useOrgUnits.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false, error: null } as never);
    render(<OrganizationTab />);
    expect(screen.getByText(/No org units yet/)).toBeTruthy();
  });
});

describe("OrganizationTab — detail panel (US3)", () => {
  it("shows geographies and applications, links and unlinks, sets the primary geography", async () => {
    render(<OrganizationTab />);
    await userEvent.click(screen.getByRole("button", { name: "Stores" }));
    const panel = screen.getByLabelText("Org unit Stores");
    expect(within(panel).getByText("Germany")).toBeTruthy();
    expect(within(panel).getByText("Xstore POS")).toBeTruthy();
    const add = within(panel).getByLabelText("Add geography") as HTMLSelectElement;
    expect(Array.from(add.options).map((o) => o.textContent)).toEqual(["Add a region or country…", "Europe — region", "France (FR)"]);
    await userEvent.selectOptions(add, "geo-FR");
    await userEvent.click(within(panel).getByRole("button", { name: "Link" }));
    expect(mutate.link).toHaveBeenCalledWith({ id: "st", geographyId: "geo-FR" });
    await userEvent.click(within(panel).getByRole("button", { name: "Remove Germany" }));
    expect(mutate.unlink).toHaveBeenCalledWith({ id: "st", geographyId: "geo-DE" });
    await userEvent.selectOptions(within(panel).getByLabelText("Primary geography"), "geo-m49-150");
    expect(mutate.update).toHaveBeenCalledWith({ id: "st", body: { primary_geography_id: "geo-m49-150" } });
  });

  it("deletes after confirming and shows the server's rule on failure", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<OrganizationTab />);
    await userEvent.click(screen.getByRole("button", { name: "Stores" }));
    mutate.delete.mockRejectedValueOnce(new Error("Org unit 'st' has 1 child(ren). Remove them first."));
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});

describe("OrganizationTab — 941 footprint and findings", () => {
  it("shows the footprint in the detail panel", async () => {
    render(<OrganizationTab />);
    await userEvent.click(screen.getByRole("button", { name: "Stores" }));
    expect(screen.getByRole("region", { name: "Capability footprint" })).toBeTruthy();
    expect(api.useOrgUnitFootprint).toHaveBeenCalledWith("st");
  });

  it("has a Findings sub-tab whose entries open the capability", async () => {
    const open = vi.fn();
    render(<OrganizationTab onOpenCapability={open} />);
    await userEvent.click(screen.getByRole("tab", { name: "Findings" }));
    await userEvent.click(screen.getByRole("button", { name: "Merchandising" }));
    expect(open).toHaveBeenCalledWith("c1");
  });
});
