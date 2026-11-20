// 946 GEO-01: the geography hierarchy screen (Business -> Organization -> Geography).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { Geography, GeoHierarchy, GeoHierarchyDetail } from "../api/organization";
import GeoHierarchies from "./GeoHierarchies";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useGeoHierarchies: vi.fn(),
  useGeoHierarchy: vi.fn(),
  useGeographies: vi.fn(),
  useCreateGeoHierarchy: vi.fn(),
  useDeleteGeoHierarchy: vi.fn(),
  useCreateGeoNode: vi.fn(),
  useAddGeoMemberships: vi.fn(),
  useUpdateGeoMembership: vi.fn(),
  useDeleteGeoMembership: vi.fn(),
  useUpdateGeography: vi.fn(),
  useDeleteGeography: vi.fn(),
}));

const api = vi.mocked(orgApi);

const geo = (id: string, name: string, kind: Geography["kind"], parent: string | null, code: string | null = null): Geography => ({
  id, name, code, m49: null, parent_id: parent, level: kind === "global" ? 1 : kind === "region" ? 2 : 3, kind, path: [], org_unit_count: 0,
  entity: kind === "country" ? "place" : "node", hierarchy_id: kind === "country" ? null : "ref", hierarchy_kind: kind === "country" ? null : "reference",
});
const GEOS = [
  geo("g", "Global", "global", null),
  geo("eu-r", "Europe", "region", "g"),
  geo("de", "Germany", "country", "eu-r", "DE"),
  geo("fr", "France", "country", "eu-r", "FR"),
  geo("gb", "United Kingdom", "country", "eu-r", "GB"),
];

const h = (id: string, name: string, kind: GeoHierarchy["kind"], over: Partial<GeoHierarchy> = {}): GeoHierarchy => ({
  id, name, kind, shape: "dag", system_of_record: null, description: null, read_only: false, node_count: 1, membership_count: 0, created_at: "", updated_at: "", ...over,
});
const REF = h("ref", "UN M49 regions", "reference", { read_only: true, system_of_record: "UN M49", shape: "strict_tree" });
const REG = h("reg", "Regulatory blocs", "regulatory");
const SALES = h("sales", "Sales", "sales", { shape: "strict_tree", node_count: 0 });

const REG_DETAIL: GeoHierarchyDetail = {
  ...REG,
  as_of: "2026-11-20",
  nodes: [{ id: "eu", name: "EU" }],
  memberships: [
    { id: "m1", hierarchy_id: "reg", parent_id: "eu", child_id: "de", child_entity: "place", valid_from: null, valid_to: null, active: true },
    { id: "m2", hierarchy_id: "reg", parent_id: "eu", child_id: "gb", child_entity: "place", valid_from: null, valid_to: "2020-01-31", active: false },
  ],
};

let calls: Record<string, ReturnType<typeof vi.fn>>;
function m(name: string, result: unknown = {}) {
  calls[name] = vi.fn().mockResolvedValue(result);
  return { mutateAsync: calls[name], mutate: calls[name], isPending: false } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
  calls = {};
  api.useGeoHierarchies.mockReturnValue({ data: { items: [REF, REG, SALES], total: 3 }, isLoading: false, error: null } as never);
  api.useGeoHierarchy.mockImplementation(((id: string) => {
    const detail = id === "reg" ? REG_DETAIL : id === "sales" ? { ...SALES, as_of: "2026-11-20", nodes: [], memberships: [] } : { ...REF, as_of: "2026-11-20", nodes: [{ id: "g", name: "Global" }], memberships: [] };
    return { data: detail, isLoading: false, error: null };
  }) as never);
  api.useGeographies.mockReturnValue({ data: { items: GEOS, total: GEOS.length } } as never);
  api.useCreateGeoHierarchy.mockReturnValue(m("createH", { id: "new" }));
  api.useDeleteGeoHierarchy.mockReturnValue(m("deleteH"));
  api.useCreateGeoNode.mockReturnValue(m("createNode"));
  api.useAddGeoMemberships.mockReturnValue(m("add", [{}, {}]));
  api.useUpdateGeoMembership.mockReturnValue(m("updateM"));
  api.useDeleteGeoMembership.mockReturnValue(m("deleteM"));
  api.useUpdateGeography.mockReturnValue(m("rename"));
  api.useDeleteGeography.mockReturnValue(m("deleteNode"));
});

describe("GeoHierarchies", () => {
  it("lists hierarchies by kind and opens the first non-reference one", () => {
    render(<GeoHierarchies canWrite canWriteCompliance />);
    const nav = screen.getByRole("navigation", { name: "Geography hierarchies" });
    expect(within(nav).getByText("Reference")).toBeTruthy();
    expect(within(nav).getByText("Regulatory")).toBeTruthy();
    expect(screen.getByRole("region", { name: "Hierarchy Regulatory blocs" })).toBeTruthy();
  });

  it("shows members active on the date, and other periods on request", async () => {
    render(<GeoHierarchies canWrite canWriteCompliance />);
    expect(screen.getByText("Germany (DE)")).toBeTruthy();
    expect(screen.queryByText("United Kingdom (GB)")).toBeNull();
    await userEvent.click(screen.getByLabelText(/Show memberships from other periods/));
    expect(screen.getByText("United Kingdom (GB)")).toBeTruthy();
    expect(screen.getByText("until 2020-01-31")).toBeTruthy();
  });

  it("asks for the hierarchy as of the chosen date", () => {
    render(<GeoHierarchies canWrite canWriteCompliance />);
    fireEvent.change(screen.getByLabelText("As of"), { target: { value: "2019-06-01" } });
    expect(api.useGeoHierarchy).toHaveBeenLastCalledWith("reg", "2019-06-01");
  });

  it("adds dated members to a node, and every country of a UN region", async () => {
    render(<GeoHierarchies canWrite canWriteCompliance />);
    await userEvent.click(screen.getByRole("button", { name: "+ Members" }));
    await userEvent.selectOptions(screen.getByLabelText("Add a member"), "fr");
    fireEvent.change(screen.getByLabelText("Member from"), { target: { value: "2025-01-01" } });
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(calls.add).toHaveBeenCalledWith({ hierarchyId: "reg", parentId: "eu", childIds: ["fr"], validFrom: "2025-01-01", validTo: null });
    await userEvent.selectOptions(screen.getByLabelText("Add every country of a UN region"), "eu-r");
    await userEvent.click(screen.getByRole("button", { name: "Add all" }));
    expect(calls.add).toHaveBeenLastCalledWith(expect.objectContaining({ childIds: ["fr", "de", "gb"] }));
  });

  it("shows the server's rule when a membership is refused", async () => {
    render(<GeoHierarchies canWrite canWriteCompliance />);
    calls.add.mockRejectedValueOnce(new Error("de is already under apac for part of that period"));
    await userEvent.click(screen.getByRole("button", { name: "+ Members" }));
    await userEvent.selectOptions(screen.getByLabelText("Add a member"), "fr");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect((await screen.findByRole("alert")).textContent).toContain("already under apac");
  });

  it("edits a membership's dates and removes one", async () => {
    render(<GeoHierarchies canWrite canWriteCompliance />);
    await userEvent.click(screen.getByRole("button", { name: "Change dates of Germany (DE)" }));
    fireEvent.change(screen.getByLabelText("Germany (DE) until"), { target: { value: "2030-01-01" } });
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(calls.updateM).toHaveBeenCalledWith({ id: "m1", validFrom: null, validTo: "2030-01-01" });
    await userEvent.click(screen.getByRole("button", { name: "Remove Germany (DE)" }));
    expect(calls.deleteM).toHaveBeenCalledWith("m1");
  });

  it("adds a node under another one", async () => {
    render(<GeoHierarchies canWrite canWriteCompliance />);
    await userEvent.click(screen.getByRole("button", { name: "+ Node" }));
    await userEvent.type(screen.getByLabelText("Node name"), "Schengen");
    await userEvent.selectOptions(screen.getByLabelText("Node parent"), "eu");
    await userEvent.click(within(screen.getByRole("form", { name: "New node" })).getByRole("button", { name: "Add" }));
    expect(calls.createNode).toHaveBeenCalledWith({ hierarchyId: "reg", name: "Schengen", parentId: "eu" });
  });

  it("creates a hierarchy; compliance kinds need the compliance permission", async () => {
    render(<GeoHierarchies canWrite canWriteCompliance={false} />);
    await userEvent.click(screen.getByRole("button", { name: "+ Hierarchy" }));
    const kind = screen.getByLabelText("Hierarchy kind") as HTMLSelectElement;
    const regulatory = Array.from(kind.options).find((o) => o.value === "regulatory")!;
    expect(regulatory.disabled).toBe(true);
    await userEvent.type(screen.getByLabelText("Hierarchy name"), "Sales regions");
    await userEvent.click(within(screen.getByRole("form", { name: "New hierarchy" })).getByRole("button", { name: "Add" }));
    expect(calls.createH).toHaveBeenCalledWith({ name: "Sales regions", kind: "sales", shape: "strict_tree" });
    // The regulatory hierarchy is read-only for this user.
    expect(screen.getByText(/needs the compliance permission/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "+ Members" })).toBeNull();
  });

  it("shows the reference hierarchy read-only", async () => {
    render(<GeoHierarchies canWrite canWriteCompliance />);
    await userEvent.click(screen.getByRole("button", { name: /UN M49 regions/ }));
    expect(screen.getByText("Read-only: mastered in UN M49.")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "+ Node" })).toBeNull();
  });

  it("is read-only for readers", () => {
    render(<GeoHierarchies canWrite={false} canWriteCompliance={false} />);
    expect(screen.queryByRole("button", { name: "+ Hierarchy" })).toBeNull();
    expect(screen.queryByRole("button", { name: "+ Members" })).toBeNull();
  });
});

describe("geographyLabel", () => {
  it("labels places by code, other hierarchies' nodes by hierarchy", () => {
    expect(orgApi.geographyLabel({ name: "France", code: "FR" })).toBe("France (FR)");
    expect(orgApi.geographyLabel({ name: "Europe", code: null, hierarchy_kind: "reference", hierarchy_name: "UN M49 regions" })).toBe("Europe");
    expect(orgApi.geographyLabel({ name: "APAC", code: null, hierarchy_kind: "sales", hierarchy_name: "Sales" })).toBe("APAC · Sales");
    expect(orgApi.geographyLabel(null)).toBe("Everywhere");
  });
});
