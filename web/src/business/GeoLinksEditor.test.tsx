// 947 GEO-02: the typed, dated geography links editor (applications, legal entities, org units).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { Geography, GeoLink } from "../api/organization";
import GeoLinksEditor from "./GeoLinksEditor";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useGeoLinkRelations: vi.fn(),
  useGeoLinks: vi.fn(),
  useGeographies: vi.fn(),
  useAddGeoLink: vi.fn(),
  useUpdateGeoLink: vi.fn(),
  useDeleteGeoLink: vi.fn(),
}));

const api = vi.mocked(orgApi);

const g = (id: string, name: string, code: string | null, entity: "place" | "node", level: number, hierarchy?: [string, string]): Geography => ({
  id, name, code, m49: null, parent_id: null, level, kind: level === 1 ? "global" : level === 2 ? "region" : "country", path: [], org_unit_count: 0,
  entity, hierarchy_id: hierarchy ? hierarchy[0] : null, hierarchy_name: hierarchy ? hierarchy[1] : null, hierarchy_kind: hierarchy ? (hierarchy[0] === "ref" ? "reference" : "sales") : null,
});
const GEOS = [
  g("geo-001", "Global", null, "node", 1, ["ref", "UN M49 regions"]),
  g("geo-m49-150", "Europe", null, "node", 2, ["ref", "UN M49 regions"]),
  g("apac", "APAC", null, "node", 2, ["sales", "Sales"]),
  g("geo-DE", "Germany", "DE", "place", 3),
  g("geo-GB", "United Kingdom", "GB", "place", 3),
];

const link = (id: string, relation: string, geo: Geography, over: Partial<GeoLink> = {}): GeoLink => ({
  id, subject_type: "legal_entity", subject_id: "le", relation, active: true, valid_from: null, valid_to: null, created_at: "", updated_at: "",
  geography: { id: geo.id, name: geo.name, code: geo.code, entity: geo.entity ?? "place", hierarchy_name: geo.hierarchy_name, hierarchy_kind: geo.hierarchy_kind },
  ...over,
});

let calls: Record<string, ReturnType<typeof vi.fn>>;
function m(name: string) {
  calls[name] = vi.fn().mockResolvedValue({});
  return { mutateAsync: calls[name], mutate: calls[name], isPending: false } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
  calls = {};
  api.useGeoLinkRelations.mockReturnValue({
    data: {
      subjects: {
        legal_entity: [
          { relation: "incorporated_in", label: "Incorporated in", place_only: true, single_active: true },
          { relation: "licensed_in", label: "Licensed in" },
        ],
      },
    },
    isLoading: false,
  } as never);
  api.useGeoLinks.mockImplementation(((_s: string, _id: string, _asOf: string | null, all: boolean) => ({
    data: {
      as_of: "2026-11-20",
      items: [
        link("l1", "incorporated_in", GEOS[3], { valid_from: "2020-01-31" }),
        link("l2", "licensed_in", GEOS[2]),
        ...(all ? [link("l3", "incorporated_in", GEOS[4], { valid_to: "2020-01-31", active: false })] : []),
      ],
    },
    isLoading: false,
    error: null,
  })) as never);
  api.useGeographies.mockReturnValue({ data: { items: GEOS, total: GEOS.length } } as never);
  api.useAddGeoLink.mockReturnValue(m("add"));
  api.useUpdateGeoLink.mockReturnValue(m("update"));
  api.useDeleteGeoLink.mockReturnValue(m("remove"));
});

describe("GeoLinksEditor", () => {
  it("lists links under each relation, labelling nodes by hierarchy", () => {
    render(<GeoLinksEditor subject="legal_entity" subjectId="le" canWrite />);
    const terms = screen.getAllByRole("term").map((t) => t.textContent);
    expect(terms).toEqual(["Incorporated in", "Licensed in"]);
    expect(screen.getByText("from 2020-01-31")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Remove APAC · Sales" })).toBeTruthy();
  });

  it("asks for the links as of a date, and from other periods on request", async () => {
    render(<GeoLinksEditor subject="legal_entity" subjectId="le" canWrite />);
    fireEvent.change(screen.getByLabelText("Links as of"), { target: { value: "2019-06-01" } });
    expect(api.useGeoLinks).toHaveBeenLastCalledWith("legal_entity", "le", "2019-06-01", false);
    await userEvent.click(screen.getByLabelText(/Show links from other periods/));
    expect(screen.getByText("until 2020-01-31")).toBeTruthy();
  });

  it("offers only countries for a country-only relation, and adds a dated link", async () => {
    render(<GeoLinksEditor subject="legal_entity" subjectId="le" canWrite />);
    const geo = screen.getByLabelText("Geography") as HTMLSelectElement;
    expect(Array.from(geo.options).map((o) => o.value)).toEqual(["", "geo-DE", "geo-GB"]);
    await userEvent.selectOptions(screen.getByLabelText("Relation"), "licensed_in");
    const options = Array.from((screen.getByLabelText("Geography") as HTMLSelectElement).options).map((o) => o.textContent);
    expect(options.slice(1)).toEqual(["Germany (DE)", "United Kingdom (GB)", "APAC · Sales", "Europe", "Global"]);
    await userEvent.selectOptions(screen.getByLabelText("Geography"), "geo-GB");
    fireEvent.change(screen.getByLabelText("Link from"), { target: { value: "2024-01-01" } });
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(calls.add).toHaveBeenCalledWith({ subject: "legal_entity", id: "le", relation: "licensed_in", geographyId: "geo-GB", validFrom: "2024-01-01", validTo: null });
  });

  it("shows the server's rule when a link is refused", async () => {
    render(<GeoLinksEditor subject="legal_entity" subjectId="le" canWrite />);
    calls.add.mockRejectedValueOnce(new Error("Only one incorporated in link at a time; end the current one first"));
    await userEvent.selectOptions(screen.getByLabelText("Geography"), "geo-GB");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect((await screen.findByRole("alert")).textContent).toContain("one incorporated in link at a time");
  });

  it("changes a link's dates and removes one", async () => {
    render(<GeoLinksEditor subject="legal_entity" subjectId="le" canWrite />);
    await userEvent.click(screen.getByRole("button", { name: "Change dates of Germany (DE)" }));
    const form = screen.getByRole("form", { name: "Dates for Germany (DE)" });
    fireEvent.change(within(form).getByLabelText("Germany (DE) until"), { target: { value: "2030-01-01" } });
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));
    expect(calls.update).toHaveBeenCalledWith({ subject: "legal_entity", id: "le", linkId: "l1", validFrom: "2020-01-31", validTo: "2030-01-01" });
    await userEvent.click(screen.getByRole("button", { name: "Remove APAC · Sales" }));
    expect(calls.remove).toHaveBeenCalledWith({ subject: "legal_entity", id: "le", linkId: "l2" });
  });

  it("is read-only without the permission", () => {
    render(<GeoLinksEditor subject="legal_entity" subjectId="le" canWrite={false} />);
    expect(screen.queryByRole("form", { name: "Add a geography link" })).toBeNull();
    expect(screen.queryByRole("button", { name: /Remove/ })).toBeNull();
  });
});
