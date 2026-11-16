// 942-regional-assessments US1/US2: the Regions expander (assessments + region-specific scope).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as orgApi from "../api/organization";
import type { Geography, RegionalAssessment } from "../api/organization";
import { RegionalAssessmentsPanel, assessableGeographies } from "./RegionalAssessmentEditor";

vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useRegionalAssessments: vi.fn(),
  useGeographies: vi.fn(),
  useRegionScope: vi.fn(),
  useSetRegionalAssessment: vi.fn(),
  useRemoveRegionalAssessment: vi.fn(),
  useSetRegionScope: vi.fn(),
}));

const api = vi.mocked(orgApi);
const geo = (id: string, name: string, kind: Geography["kind"], code: string | null = null): Geography => ({
  id, name, code, m49: null, parent_id: null, level: kind === "global" ? 1 : kind === "region" ? 2 : 3, kind, path: [], org_unit_count: 0,
});
const GEOS = [geo("g", "Global", "global"), geo("eu", "Europe", "region"), geo("br", "Brazil", "country", "BR"), geo("am", "Americas", "region"), geo("de", "Germany", "country", "DE")];
const ASSESSMENTS: RegionalAssessment[] = [
  { id: "a1", capability_id: "accept", geography: { id: "br", name: "Brazil", level: 3, code: "BR" }, maturity_level: 2, note: "Pix handled locally", updated_at: "" },
  { id: "a2", capability_id: "accept", geography: { id: "eu", name: "Europe", level: 2, code: null }, maturity_level: null, note: "Varies", updated_at: "" },
];

let save: ReturnType<typeof vi.fn>;
let remove: ReturnType<typeof vi.fn>;
let setScope: ReturnType<typeof vi.fn>;

function scope(region_specific: boolean, ids: string[] = [], needsUpdate = false) {
  api.useRegionScope.mockReturnValue({
    data: {
      capability_id: "accept",
      region_specific,
      scope_needs_update: needsUpdate,
      geographies: ids.map((id) => {
        const g = GEOS.find((x) => x.id === id)!;
        return { id: g.id, name: g.name, level: g.level, code: g.code };
      }),
    },
  } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  save = vi.fn().mockResolvedValue({});
  remove = vi.fn().mockResolvedValue(undefined);
  setScope = vi.fn().mockResolvedValue({});
  api.useRegionalAssessments.mockReturnValue({ data: { items: ASSESSMENTS, total: 2 }, isLoading: false } as never);
  api.useGeographies.mockReturnValue({ data: { items: GEOS, total: GEOS.length } } as never);
  api.useSetRegionalAssessment.mockReturnValue({ mutateAsync: save, isPending: false } as never);
  api.useRemoveRegionalAssessment.mockReturnValue({ mutateAsync: remove, isPending: false } as never);
  api.useSetRegionScope.mockReturnValue({ mutateAsync: setScope, isPending: false } as never);
  scope(false);
});

const panel = (canWrite = true) =>
  render(<RegionalAssessmentsPanel capabilityId="accept" capabilityName="Accept Payment" baseline={3} canWrite={canWrite} />);

describe("assessableGeographies", () => {
  it("drops Global and lists regions before countries", () => {
    expect(assessableGeographies(GEOS).map((g) => g.name)).toEqual(["Americas", "Europe", "Brazil", "Germany"]);
  });
});

describe("RegionalAssessmentsPanel — assessments (US1)", () => {
  it("shows the baseline and lists assessments with label and note", () => {
    panel();
    expect(screen.getByText(/Global baseline: 3 · Established/)).toBeTruthy();
    expect(screen.getByText("Brazil (BR)")).toBeTruthy();
    expect(screen.getByText("2 · Emerging")).toBeTruthy();
    expect(screen.getByText("Pix handled locally")).toBeTruthy();
    expect(screen.getByText("Not assessed")).toBeTruthy(); // Europe has a note only
  });

  it("adds an assessment, offering only geographies not yet assessed", async () => {
    panel();
    const pick = screen.getByLabelText("Assess in") as HTMLSelectElement;
    expect(Array.from(pick.options).map((o) => o.textContent)).toEqual(["Assess in a region or country…", "Americas", "Germany (DE)"]);
    await userEvent.selectOptions(pick, "de");
    const form = screen.getByRole("form", { name: "Assess Accept Payment in Germany" });
    expect(within(form).getByRole("button", { name: "Save" }).hasAttribute("disabled")).toBe(true);
    await userEvent.selectOptions(within(form).getByLabelText("Regional maturity"), "5");
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));
    expect(save).toHaveBeenCalledWith({ capabilityId: "accept", geographyId: "de", maturity_level: 5, note: null });
  });

  it("edits and removes an assessment", async () => {
    panel();
    await userEvent.click(screen.getByRole("button", { name: "Edit Brazil" }));
    const form = screen.getByRole("form", { name: "Assess Accept Payment in Brazil" });
    expect((within(form).getByLabelText("Regional maturity") as HTMLSelectElement).value).toBe("2");
    await userEvent.click(within(form).getByRole("button", { name: "Remove" }));
    expect(remove).toHaveBeenCalledWith({ capabilityId: "accept", geographyId: "br" });
  });

  it("shows the server's rule on failure", async () => {
    save.mockRejectedValueOnce(new Error("Global is the capability's baseline maturity"));
    panel();
    await userEvent.selectOptions(screen.getByLabelText("Assess in"), "am");
    await userEvent.type(screen.getByLabelText("Regional variant note"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByRole("alert")).toBeTruthy();
  });

  it("is read-only for readers", () => {
    panel(false);
    expect(screen.queryByLabelText("Assess in")).toBeNull();
    expect(screen.queryByRole("button", { name: /Edit/ })).toBeNull();
    expect(screen.getByText("Applies in every region.")).toBeTruthy();
  });
});

describe("RegionScopeEditor (US2)", () => {
  it("flags a capability region-specific and requires at least one geography", async () => {
    panel();
    await userEvent.click(screen.getByLabelText(/Region-specific/));
    expect(screen.getByText("Add at least one region or country.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Save scope" }).hasAttribute("disabled")).toBe(true);
    await userEvent.selectOptions(screen.getByLabelText("Add scope geography"), "br");
    await userEvent.click(screen.getAllByRole("button", { name: "Add" })[0]);
    await userEvent.click(screen.getByRole("button", { name: "Save scope" }));
    expect(setScope).toHaveBeenCalledWith({ capabilityId: "accept", region_specific: true, geography_ids: ["br"] });
  });

  it("clears the flag and its geographies", async () => {
    scope(true, ["br"]);
    panel();
    await userEvent.click(screen.getByLabelText(/Region-specific/));
    await userEvent.click(screen.getByRole("button", { name: "Save scope" }));
    expect(setScope).toHaveBeenCalledWith({ capabilityId: "accept", region_specific: false, geography_ids: [] });
  });

  it("warns when the scope needs updating, and shows the scope to readers", () => {
    scope(true, [], true);
    const { unmount } = panel();
    expect(screen.getByText(/Scope needs updating/)).toBeTruthy();
    unmount();
    scope(true, ["br"]);
    panel(false);
    expect(screen.getByText("Region-specific: applies in Brazil.")).toBeTruthy();
  });
});
