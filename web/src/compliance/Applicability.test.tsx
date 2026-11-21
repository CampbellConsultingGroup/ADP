// 948 GEO-03: framework jurisdiction editor, "applies to" list and the subject-side view.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as complianceApi from "../api/compliance";
import type { Applicability, ApplicabilityEvidence } from "../api/compliance";
import * as orgApi from "../api/organization";
import { evidenceText, FrameworkJurisdictionPanel, SubjectApplicability } from "./Applicability";

vi.mock("../api/compliance", async (orig) => ({
  ...(await orig<typeof import("../api/compliance")>()),
  useFrameworkJurisdiction: vi.fn(),
  useSetFrameworkJurisdiction: vi.fn(),
  useFrameworkApplicability: vi.fn(),
  useSubjectApplicability: vi.fn(),
}));
vi.mock("../api/organization", async (orig) => ({
  ...(await orig<typeof import("../api/organization")>()),
  useGeographies: vi.fn(),
  useGeoLinkRelations: vi.fn(),
}));

const capi = vi.mocked(complianceApi);
const oapi = vi.mocked(orgApi);

const EU = { id: "eu", name: "EU", code: null, entity: "node", hierarchy_name: "Regulatory blocs", hierarchy_kind: "regulatory" };
const DE = { id: "geo-DE", name: "Germany", code: "DE", entity: "place" };

const ev = (over: Partial<ApplicabilityEvidence> = {}): ApplicabilityEvidence => ({
  relation: "processes_personal_data_of",
  relation_label: "Processes personal data of people in",
  geography: DE,
  jurisdiction_geography: EU,
  how: "inside",
  path: ["Germany", "EU"],
  via_legal_entity: null,
  valid_from: null,
  valid_to: null,
  ...over,
});

const item = (status: Applicability["status"], subject: string, over: Partial<Applicability> = {}): Applicability => ({
  framework: { id: "gdpr", name: "GDPR" },
  subject_type: "application",
  subject: { id: subject.toLowerCase(), name: subject },
  status,
  reason: status === "applies" ? null : status === "unknown" ? "No processes personal data of people in links recorded" : "None of its links are in the jurisdiction",
  evidence: status === "applies" ? [ev()] : [],
  ...over,
});

let save: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  save = vi.fn().mockResolvedValue({});
  capi.useFrameworkJurisdiction.mockReturnValue({
    data: {
      framework_id: "gdpr",
      configured: true,
      geographies: [EU],
      triggers: [{ subject_type: "application", relation: "processes_personal_data_of", label: "Processes personal data of people in" }],
    },
    isLoading: false,
  } as never);
  capi.useSetFrameworkJurisdiction.mockReturnValue({ mutateAsync: save, isPending: false } as never);
  capi.useFrameworkApplicability.mockReturnValue({
    data: {
      as_of: "2026-11-20",
      framework_id: "gdpr",
      configured: true,
      counts: { applies: 1, unknown: 1, does_not_apply: 1 },
      items: [item("applies", "CRM"), item("unknown", "POS"), item("does_not_apply", "UK Loyalty")],
    },
    isLoading: false,
  } as never);
  capi.useSubjectApplicability.mockReturnValue({
    data: {
      as_of: "2026-11-20",
      subject_type: "application",
      subject_id: "crm",
      items: [
        item("applies", "CRM", { framework: { id: "ins", name: "Insurance law" }, evidence: [ev({ relation_label: "Licensed in", how: "same", jurisdiction_geography: DE, via_legal_entity: { id: "g", name: "Retail GmbH" } })] }),
        item("unknown", "CRM", { framework: { id: "dora", name: "DORA" }, reason: "No jurisdiction recorded for this framework" }),
      ],
    },
    isLoading: false,
    error: null,
  } as never);
  oapi.useGeographies.mockReturnValue({
    data: { items: [{ ...DE, level: 3, kind: "country", m49: null, parent_id: null, path: [], org_unit_count: 0 }, { ...EU, level: 2, kind: "region", m49: null, parent_id: null, path: [], org_unit_count: 0 }], total: 2 },
  } as never);
  oapi.useGeoLinkRelations.mockReturnValue({
    data: {
      subjects: {
        application: [{ relation: "processes_personal_data_of", label: "Processes personal data of people in" }, { relation: "deployed_in", label: "Deployed in" }],
        legal_entity: [{ relation: "licensed_in", label: "Licensed in" }],
      },
    },
    isLoading: false,
  } as never);
});

describe("evidenceText", () => {
  it("says how the link meets the jurisdiction", () => {
    expect(evidenceText(ev())).toBe("Processes personal data of people in Germany (DE), which is in EU · Regulatory blocs");
    expect(evidenceText(ev({ how: "same", jurisdiction_geography: DE, via_legal_entity: { id: "g", name: "Retail GmbH" }, valid_from: "2020-01-01" }))).toBe(
      "Processes personal data of people in Germany (DE), via Retail GmbH [2020-01-01 – …]",
    );
    expect(evidenceText(ev({ path: ["Bavaria", "Germany", "EU"] }))).toContain("(Bavaria › Germany › EU)");
  });
});

describe("FrameworkJurisdictionPanel", () => {
  it("summarises the jurisdiction and lists what it applies to", async () => {
    render(<FrameworkJurisdictionPanel frameworkId="gdpr" canWrite />);
    expect(screen.getByText("Covers EU · Regulatory blocs.")).toBeTruthy();
    expect(screen.getByText(/an application processes personal data of people in it/)).toBeTruthy();
    expect(screen.getByText("1 apply · 1 unknown · 1 do not apply")).toBeTruthy();
    expect(screen.getByRole("link", { name: "CRM" })).toBeTruthy();
    expect(screen.queryByText("POS")).toBeNull();
    await userEvent.click(screen.getByLabelText(/Show unknown and does not apply/));
    expect(screen.getByText("POS")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("Applicability as of"), { target: { value: "2019-06-01" } });
    expect(capi.useFrameworkApplicability).toHaveBeenLastCalledWith("gdpr", "2019-06-01");
  });

  it("edits the jurisdiction", async () => {
    render(<FrameworkJurisdictionPanel frameworkId="gdpr" canWrite />);
    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const form = screen.getByRole("form", { name: "Edit jurisdiction" });
    await userEvent.selectOptions(within(form).getByLabelText("Add to the jurisdiction"), "geo-DE");
    await userEvent.click(within(form).getByLabelText("licensed in"));
    await userEvent.click(within(form).getByRole("button", { name: "Save" }));
    expect(save).toHaveBeenCalledWith({
      geography_ids: ["eu", "geo-DE"],
      triggers: [
        { subject_type: "application", relation: "processes_personal_data_of" },
        { subject_type: "legal_entity", relation: "licensed_in" },
      ],
    });
  });

  it("explains an unrecorded jurisdiction and hides Edit for readers", () => {
    capi.useFrameworkJurisdiction.mockReturnValue({ data: { framework_id: "gdpr", configured: false, geographies: [], triggers: [] }, isLoading: false } as never);
    render(<FrameworkJurisdictionPanel frameworkId="gdpr" canWrite={false} />);
    expect(screen.getByText(/Not recorded/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
  });
});

describe("SubjectApplicability", () => {
  it("shows each framework's answer with its evidence or reason", () => {
    render(<SubjectApplicability subject="application" subjectId="crm" />);
    expect(screen.getByText("Insurance law")).toBeTruthy();
    expect(screen.getByText(/Licensed in Germany \(DE\), via Retail GmbH/)).toBeTruthy();
    expect(screen.getByText("No jurisdiction recorded for this framework")).toBeTruthy();
    expect(screen.getAllByText("Applies")).toHaveLength(1);
    expect(screen.getByText("Unknown")).toBeTruthy();
    expect(capi.useSubjectApplicability).toHaveBeenCalledWith("application", "crm", null);
  });
});
