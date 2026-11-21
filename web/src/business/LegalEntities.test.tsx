// 947 GEO-02: Business -> Organization -> Legal entities, and an application's Geography tab.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { LegalEntity, LegalEntityDetail } from "../api/organization";
import * as capNav from "../application/appCapNav";
import ApplicationGeography from "../application/ApplicationGeography";
import LegalEntities from "./LegalEntities";

// 948: the applicability panels have their own tests (compliance/Applicability.test.tsx).
vi.mock("../compliance/Applicability", () => ({ FrameworkJurisdictionPanel: () => null, SubjectApplicability: () => null }));
vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useLegalEntities: vi.fn(),
  useLegalEntity: vi.fn(),
  useCreateLegalEntity: vi.fn(),
  useUpdateLegalEntity: vi.fn(),
  useDeleteLegalEntity: vi.fn(),
  useLinkLegalEntityOrgUnit: vi.fn(),
  useUnlinkLegalEntityOrgUnit: vi.fn(),
  useOrgUnits: vi.fn(),
  useApplicationLegalEntities: vi.fn(),
  useLinkApplicationLegalEntity: vi.fn(),
  useUnlinkApplicationLegalEntity: vi.fn(),
  // The geography links editor inside both screens.
  useGeoLinkRelations: vi.fn(),
  useGeoLinks: vi.fn(),
  useGeographies: vi.fn(),
  useAddGeoLink: vi.fn(),
  useUpdateGeoLink: vi.fn(),
  useDeleteGeoLink: vi.fn(),
}));
vi.mock("../application/appCapNav", async (orig) => ({
  ...(await orig<typeof import("../application/appCapNav")>()),
  useApplicationWrite: vi.fn(),
}));

const api = vi.mocked(orgApi);
const nav = vi.mocked(capNav);

const le = (id: string, name: string, parent: string | null = null, over: Partial<LegalEntity> = {}): LegalEntity => ({
  id, name, parent_id: parent, registration_number: null, lei: null, description: null, path: [], org_unit_ids: [],
  application_count: 0, child_count: 0, created_at: "", updated_at: "", ...over,
});
const PLC = le("plc", "Retail Co plc", null, { child_count: 1 });
const GMBH = le("gmbh", "Retail Co GmbH", "plc", { path: [{ id: "plc", name: "Retail Co plc", level: 1 }], application_count: 1 });
const SA = le("sa", "Retail Co SA", "gmbh");
const ITEMS = [PLC, GMBH, SA];

let calls: Record<string, ReturnType<typeof vi.fn>>;
function m(name: string, result: unknown = {}) {
  calls[name] = vi.fn().mockResolvedValue(result);
  return { mutateAsync: calls[name], mutate: calls[name], isPending: false } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
  calls = {};
  api.useLegalEntities.mockReturnValue({ data: { items: ITEMS, total: 3 }, isLoading: false, error: null } as never);
  api.useLegalEntity.mockImplementation(((id: string) => {
    const base = ITEMS.find((i) => i.id === id)!;
    const detail: LegalEntityDetail = {
      ...base,
      registration_number: id === "gmbh" ? "HRB 1" : null,
      org_units: id === "gmbh" ? [{ id: "st", name: "Stores", level: 2 }] : [],
      org_unit_ids: id === "gmbh" ? ["st"] : [],
      applications: id === "gmbh" ? [{ id: "pos", name: "Store POS", level: 0 }] : [],
      children: id === "gmbh" ? [{ id: "sa", name: "Retail Co SA", level: 3 }] : [],
    };
    return { data: detail, isLoading: false };
  }) as never);
  api.useOrgUnits.mockReturnValue({
    data: { items: [{ id: "st", name: "Stores", path: [] }, { id: "fin", name: "Finance", path: [{ id: "c", name: "Corporate", level: 2 }] }], total: 2 },
  } as never);
  api.useCreateLegalEntity.mockReturnValue(m("create", { id: "new" }));
  api.useUpdateLegalEntity.mockReturnValue(m("update"));
  api.useDeleteLegalEntity.mockReturnValue(m("delete"));
  api.useLinkLegalEntityOrgUnit.mockReturnValue(m("linkOu"));
  api.useUnlinkLegalEntityOrgUnit.mockReturnValue(m("unlinkOu"));
  api.useApplicationLegalEntities.mockReturnValue({ data: [GMBH], isLoading: false } as never);
  api.useLinkApplicationLegalEntity.mockReturnValue(m("linkApp"));
  api.useUnlinkApplicationLegalEntity.mockReturnValue(m("unlinkApp"));
  api.useGeoLinkRelations.mockReturnValue({ data: { subjects: { legal_entity: [], application: [{ relation: "deployed_in", label: "Deployed in" }] } }, isLoading: false } as never);
  api.useGeoLinks.mockReturnValue({ data: { as_of: "2026-11-20", items: [] }, isLoading: false, error: null } as never);
  api.useGeographies.mockReturnValue({ data: { items: [], total: 0 } } as never);
  api.useAddGeoLink.mockReturnValue(m("addLink"));
  api.useUpdateGeoLink.mockReturnValue(m("updateLink"));
  api.useDeleteGeoLink.mockReturnValue(m("deleteLink"));
  nav.useApplicationWrite.mockReturnValue({ allowed: true, reason: undefined } as never);
});

describe("LegalEntities", () => {
  it("shows the ownership tree and opens an entity", async () => {
    render(<LegalEntities canWrite />);
    const tree = screen.getByRole("navigation", { name: "Legal entities" });
    expect(within(tree).getAllByRole("button").map((b) => b.textContent)).toEqual(["Retail Co plc", "Retail Co GmbH1 app", "Retail Co SA"]);
    await userEvent.click(within(tree).getByRole("button", { name: /Retail Co GmbH/ }));
    const panel = screen.getByLabelText("Legal entity Retail Co GmbH");
    expect(within(panel).getByText("Owned by Retail Co plc")).toBeTruthy();
    expect(within(panel).getByText("Registration number: HRB 1")).toBeTruthy();
    expect(within(panel).getByRole("link", { name: "Store POS" }).getAttribute("href")).toContain("pos");
    expect(within(panel).getByRole("region", { name: "Geography links" })).toBeTruthy();
  });

  it("creates a legal entity owned by another", async () => {
    render(<LegalEntities canWrite />);
    await userEvent.click(screen.getByRole("button", { name: "+ Legal entity" }));
    const form = screen.getByRole("form", { name: "New legal entity" });
    await userEvent.type(within(form).getByLabelText("Legal entity name"), "Retail Co BV");
    await userEvent.type(within(form).getByLabelText("LEI"), "529900T8BM49AURSDO55");
    await userEvent.selectOptions(within(form).getByLabelText("Owned by"), "plc");
    await userEvent.click(within(form).getByRole("button", { name: "Add" }));
    expect(calls.create).toHaveBeenCalledWith({ name: "Retail Co BV", registration_number: null, lei: "529900T8BM49AURSDO55", description: null, parent_id: "plc" });
  });

  it("can't make an entity owned by itself or a subsidiary", async () => {
    render(<LegalEntities canWrite />);
    await userEvent.click(screen.getByRole("button", { name: /Retail Co GmbH/ }));
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const owners = Array.from((screen.getByLabelText("Owned by") as HTMLSelectElement).options).map((o) => o.value);
    expect(owners).toEqual(["", "plc"]);
  });

  it("links and unlinks org units, and deletes after confirming", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(true);
    render(<LegalEntities canWrite />);
    await userEvent.click(screen.getByRole("button", { name: /Retail Co GmbH/ }));
    const select = screen.getByLabelText("Link an org unit") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.textContent)).toEqual(["Link an org unit…", "Corporate › Finance"]);
    await userEvent.selectOptions(select, "fin");
    expect(calls.linkOu).toHaveBeenCalledWith({ id: "gmbh", orgUnitId: "fin" });
    await userEvent.click(screen.getByRole("button", { name: "Unlink Stores" }));
    expect(calls.unlinkOu).toHaveBeenCalledWith({ id: "gmbh", orgUnitId: "st" });
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(calls.delete).toHaveBeenCalledWith("gmbh");
  });

  it("is read-only for readers", async () => {
    render(<LegalEntities canWrite={false} />);
    expect(screen.queryByRole("button", { name: "+ Legal entity" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Retail Co GmbH/ }));
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByLabelText("Link an org unit")).toBeNull();
  });
});

describe("ApplicationGeography", () => {
  it("links and unlinks legal entities and shows the application's geography links", async () => {
    render(<ApplicationGeography appId="pos" />);
    expect(screen.getByText("Retail Co GmbH")).toBeTruthy();
    const select = screen.getByLabelText("Link a legal entity") as HTMLSelectElement;
    expect(Array.from(select.options).map((o) => o.value)).toEqual(["", "plc", "sa"]);
    await userEvent.selectOptions(select, "plc");
    expect(calls.linkApp).toHaveBeenCalledWith({ appId: "pos", legalEntityId: "plc" });
    await userEvent.click(screen.getByRole("button", { name: "Unlink Retail Co GmbH" }));
    expect(calls.unlinkApp).toHaveBeenCalledWith({ appId: "pos", legalEntityId: "gmbh" });
    expect(api.useGeoLinks).toHaveBeenCalledWith("application", "pos", null, false);
    expect(screen.getByRole("term").textContent).toBe("Deployed in");
  });

  it("is read-only without write_application", () => {
    nav.useApplicationWrite.mockReturnValue({ allowed: false, reason: "No" } as never);
    render(<ApplicationGeography appId="pos" />);
    expect(screen.queryByLabelText("Link a legal entity")).toBeNull();
    expect(screen.queryByRole("button", { name: "Unlink Retail Co GmbH" })).toBeNull();
  });
});
