// 949 GEO-04: the place matrix, adding a subdivision, and an application's footprint.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import GeoPlaces from "./GeoPlaces";
import { Footprint } from "../application/ApplicationGeography";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useGeoHierarchies: vi.fn(),
  useGeographies: vi.fn(),
  usePlaceMatrix: vi.fn(),
  useSubdivisionCatalog: vi.fn(),
  useAddSubdivision: vi.fn(),
  useGeoFootprint: vi.fn(),
}));

const api = vi.mocked(orgApi);
const DE = { id: "geo-DE", name: "Germany", code: "DE", place_type: "country" as const, parent_place_id: null };
const BY = { id: "geo-DE-BY", name: "Bavaria", code: "DE-BY", place_type: "subdivision" as const, parent_place_id: "geo-DE" };
const LLOYDS = { id: "geo-lloyds", name: "Lloyd's of London", code: null, place_type: "authority" as const, parent_place_id: "geo-GB" };
const EU = { id: "geo-bloc-eu", name: "European Union" };

let add: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  add = vi.fn().mockResolvedValue({ name: "California", code: "US-CA" });
  api.useGeoHierarchies.mockReturnValue({
    data: {
      items: [
        { id: "geoh-m49", name: "UN M49 regions", kind: "reference" },
        { id: "geoh-regulatory-blocs", name: "Regulatory blocs", kind: "regulatory" },
      ],
      total: 2,
    },
  } as never);
  api.useGeographies.mockReturnValue({
    data: {
      items: [
        { ...DE, entity: "place", level: 3, kind: "country", m49: null, parent_id: null, path: [], org_unit_count: 0 },
        { id: "geo-US", name: "United States of America", code: "US", entity: "place", place_type: "country", level: 3, kind: "country", m49: null, parent_id: null, path: [], org_unit_count: 0 },
        { ...EU, code: null, entity: "node", level: 2, kind: "region", m49: null, parent_id: null, path: [], org_unit_count: 0 },
      ],
      total: 3,
    },
  } as never);
  api.usePlaceMatrix.mockReturnValue({
    data: {
      as_of: "2026-11-21",
      hierarchies: [
        { id: "geoh-m49", name: "UN M49 regions", kind: "reference" },
        { id: "geoh-regulatory-blocs", name: "Regulatory blocs", kind: "regulatory" },
      ],
      rows: [
        { place: DE, cells: { "geoh-m49": [{ id: "geo-m49-150", name: "Europe" }], "geoh-regulatory-blocs": [{ id: "eea", name: "European Economic Area" }, EU] } },
        { place: BY, cells: { "geoh-m49": [{ id: "geo-m49-150", name: "Europe" }], "geoh-regulatory-blocs": [EU] } },
        { place: LLOYDS, cells: {} },
      ],
    },
    isLoading: false,
    error: null,
  } as never);
  api.useSubdivisionCatalog.mockImplementation(
    (country) =>
      ({
        data: country
          ? {
              country_id: "geo-US",
              country_name: "United States of America",
              items: [
                { code: "US-AK", name: "Alaska", type: "State", added: true },
                { code: "US-CA", name: "California", type: "State", added: false },
              ],
            }
          : undefined,
        isLoading: false,
      }) as never,
  );
  api.useAddSubdivision.mockReturnValue({ mutateAsync: add, isPending: false } as never);
});

describe("GeoPlaces", () => {
  it("shows each place against each hierarchy", async () => {
    render(<GeoPlaces canWrite={false} />);
    const table = screen.getByRole("table", { name: "Places by hierarchy" });
    expect(within(table).getByRole("columnheader", { name: "Regulatory blocs" })).toBeTruthy();
    expect(within(table).getByText("European Economic Area · European Union")).toBeTruthy();
    expect(within(table).getByText("Authority")).toBeTruthy();
    expect(screen.queryByRole("form", { name: "Add a subdivision" })).toBeNull();

    await userEvent.click(screen.getByLabelText("UN M49 regions", { exact: false }));
    expect(within(table).queryByRole("columnheader", { name: "UN M49 regions" })).toBeNull();
    await userEvent.type(screen.getByLabelText("Filter places"), "bav");
    expect(screen.getByText("1 of 3 places")).toBeTruthy();
    await userEvent.clear(screen.getByLabelText("Filter places"));
    await userEvent.click(screen.getByLabelText(/Only\s+subdivisions/));
    expect(screen.getByText("2 of 3 places")).toBeTruthy();
  });

  it("adds a subdivision chosen from the ISO list", async () => {
    render(<GeoPlaces canWrite />);
    const form = screen.getByRole("form", { name: "Add a subdivision" });
    await userEvent.selectOptions(within(form).getByLabelText("Country"), "geo-US");
    const sub = within(form).getByLabelText("Subdivision");
    expect(within(sub).queryByText(/Alaska/)).toBeNull(); // already added
    await userEvent.selectOptions(sub, "US-CA");
    await userEvent.click(within(form).getByRole("button", { name: "Add" }));
    expect(add).toHaveBeenCalledWith("US-CA");
    expect(await screen.findByText("Added California (US-CA).")).toBeTruthy();
  });
});

describe("Footprint", () => {
  it("lists the places an application reaches with their hierarchies", () => {
    api.useGeoFootprint.mockReturnValue({
      data: {
        as_of: "2026-11-21",
        application_id: "pos",
        places: [
          {
            place: DE,
            links: [
              { relation: "licensed_in", relation_label: "Licensed in", geography: { id: "geo-DE", name: "Germany", code: "DE", entity: "place" }, via_legal_entity: { id: "g", name: "Retail GmbH" } },
            ],
            placements: [{ hierarchy_id: "geoh-m49", hierarchy_name: "UN M49 regions", hierarchy_kind: "reference", nodes: [{ id: "w", name: "Western Europe" }, { id: "g", name: "Global" }] }],
          },
        ],
        unresolved: [],
      },
      isLoading: false,
      error: null,
    } as never);
    render(<Footprint appId="pos" />);
    expect(screen.getByText("Germany (DE)")).toBeTruthy();
    expect(screen.getByText("Licensed in Germany (DE), via Retail GmbH")).toBeTruthy();
    expect(screen.getByText("UN M49 regions: Western Europe · Global")).toBeTruthy();
    expect(api.useGeoFootprint).toHaveBeenCalledWith("pos", expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/));
  });
});
