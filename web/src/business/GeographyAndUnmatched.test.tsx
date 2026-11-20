// 940-org-units-geography: the review queue (US4). The geography screen is tested in GeoHierarchies.test.tsx (946).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { Geography, OrgUnit } from "../api/organization";
import UnmatchedList from "./UnmatchedList";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useGeographies: vi.fn(),
  useDeleteGeography: vi.fn(),
  useUnmatched: vi.fn(),
  useOrgUnits: vi.fn(),
  useResolveUnmatched: vi.fn(),
}));

const api = vi.mocked(orgApi);

const geo = (id: string, name: string, kind: Geography["kind"], parent: string | null, code: string | null = null): Geography => ({
  id, name, code, m49: null, parent_id: parent, level: kind === "global" ? 1 : kind === "region" ? 2 : 3, kind, path: [], org_unit_count: id === "geo-DE" ? 1 : 0,
});
const GEOS = [
  geo("geo-001", "Global", "global", null),
  geo("geo-m49-150", "Europe", "region", "geo-001"),
  geo("geo-m49-019", "Americas", "region", "geo-001"),
  geo("geo-DE", "Germany", "country", "geo-m49-150", "DE"),
  geo("geo-FR", "France", "country", "geo-m49-150", "FR"),
  geo("geo-BR", "Brazil", "country", "geo-m49-019", "BR"),
  geo("geo-TW", "Taiwan", "country", "geo-001", "TW"),
];

const ou = (id: string, name: string, level: number, path: string[] = []): OrgUnit => ({
  id, name, description: null, parent_id: null, level, kind: (["enterprise", "division", "function"] as const)[level - 1],
  primary_geography_id: null, geography_ids: [], path: path.map((p) => ({ id: p, name: p, level: 1 })), application_count: 0, created_at: "", updated_at: "",
});

let deleteGeo: ReturnType<typeof vi.fn>;
let resolve: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  deleteGeo = vi.fn().mockResolvedValue(undefined);
  resolve = vi.fn().mockResolvedValue({ org_unit: ou("st", "Stores", 2), updated_count: 3 });
  api.useGeographies.mockReturnValue({ data: { items: GEOS, total: GEOS.length }, isLoading: false, error: null } as never);
  api.useDeleteGeography.mockReturnValue({ mutateAsync: deleteGeo, isPending: false } as never);
  api.useOrgUnits.mockReturnValue({ data: { items: [ou("rc", "Retail Co", 1), ou("st", "Stores", 2, ["Retail Co"])], total: 2 } } as never);
  api.useResolveUnmatched.mockReturnValue({ mutateAsync: resolve, isPending: false } as never);
  api.useUnmatched.mockReturnValue({
    data: {
      items: [
        { value: "Store Systems", application_count: 3, sample_applications: [{ id: "a1", name: "POS", level: 0 }] },
        { value: "Store systems", application_count: 1, sample_applications: [] },
      ],
      total: 2,
    },
    isLoading: false,
    error: null,
  } as never);
});

describe("UnmatchedList (US4)", () => {
  it("lists exact values with counts and sample applications", () => {
    render(<UnmatchedList canWrite />);
    expect(screen.getByText("“Store Systems”")).toBeTruthy();
    expect(screen.getByText("“Store systems”")).toBeTruthy();
    expect(screen.getByText(/3 applications: POS/)).toBeTruthy();
  });

  it("maps a value to an existing org unit and reports the count", async () => {
    render(<UnmatchedList canWrite />);
    await userEvent.selectOptions(screen.getByLabelText("Org unit for Store Systems"), "st");
    await userEvent.click(screen.getAllByRole("button", { name: "Map" })[0]);
    expect(resolve).toHaveBeenCalledWith({ value: "Store Systems", org_unit_id: "st" });
    expect(await screen.findByText("Linked 3 applications with “Store Systems” to Stores.")).toBeTruthy();
  });

  it("keeps the confirmation after the resolved value leaves the list", async () => {
    const { rerender } = render(<UnmatchedList canWrite />);
    await userEvent.selectOptions(screen.getAllByLabelText("Org unit for Store Systems")[0], "st");
    await userEvent.click(screen.getAllByRole("button", { name: "Map" })[0]);
    api.useUnmatched.mockReturnValue({
      data: { items: [{ value: "Store systems", application_count: 1, sample_applications: [] }], total: 1 },
      isLoading: false,
      error: null,
    } as never);
    rerender(<UnmatchedList canWrite />);
    expect(screen.getByRole("status").textContent).toContain("Linked 3 applications");
    expect(screen.queryByText("“Store Systems”")).toBeNull();
  });

  it("creates an org unit and maps in one step", async () => {
    render(<UnmatchedList canWrite />);
    await userEvent.selectOptions(screen.getByLabelText("Action for Store systems"), "create");
    const name = screen.getByLabelText("New org unit name for Store systems");
    await userEvent.clear(name);
    await userEvent.type(name, "Store Ops");
    await userEvent.selectOptions(screen.getByLabelText("Parent for Store systems"), "rc");
    await userEvent.click(screen.getByRole("button", { name: "Create & map" }));
    expect(resolve).toHaveBeenCalledWith({ value: "Store systems", create: { name: "Store Ops", parent_id: "rc" } });
  });

  it("shows the empty state, and no actions for readers", () => {
    render(<UnmatchedList canWrite={false} />);
    expect(screen.queryByRole("button", { name: "Map" })).toBeNull();
    api.useUnmatched.mockReturnValue({ data: { items: [], total: 0 }, isLoading: false, error: null } as never);
    render(<UnmatchedList canWrite />);
    expect(screen.getByText("Every business unit value is matched.")).toBeTruthy();
  });
});
