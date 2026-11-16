// 936-pattern-conformance: adoptions, conformance, pins, discovery, evaluate, Save as diagram.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as patternsApi from "../api/patterns";
import type { Adoption, ConformanceReport } from "../api/patterns";
import { ApiError } from "../api/client";
import * as auth from "../auth/AuthProvider";
import AdoptionForm from "./AdoptionForm";
import AdoptionPage from "./AdoptionPage";
import AdoptionsList from "./AdoptionsList";
import DiscoveryTab from "./DiscoveryTab";
import EvaluatePanel from "./EvaluatePanel";
import PinsEditor from "./PinsEditor";
import { flowchartToSeed } from "./saveAsDiagram";
import { mutation } from "./testFixtures";

vi.mock("../api/patterns", async (orig) => {
  const actual = await orig<typeof import("../api/patterns")>();
  return {
    ...actual,
    useAdoptions: vi.fn(),
    useAdoption: vi.fn(),
    useConformance: vi.fn(),
    useAdoptionView: vi.fn(),
    useCandidates: vi.fn(),
    useCreateAdoption: vi.fn(),
    useSetPins: vi.fn(),
    useDeleteAdoption: vi.fn(),
    useDiscovery: vi.fn(),
    useEvaluate: vi.fn(),
    usePatternFamilies: vi.fn(),
    useApplicationChoices: vi.fn(),
  };
});
vi.mock("../auth/AuthProvider", () => ({ useAuth: vi.fn() }));
vi.mock("../api/business", () => ({
  useDomains: () => ({ data: { items: [{ id: "d1", name: "Claims" }, { id: "d2", name: "Billing" }] } }),
}));

const api = vi.mocked(patternsApi);
const useAuth = vi.mocked(auth.useAuth);

const GOLDEN = readFileSync(
  resolve(process.cwd(), "..", "tests", "unit", "patterns", "goldens",
    "conformance__ea.integration.domain-event-backbone_1.0.0__non_conformant.mmd"),
  "utf-8",
);

function adoption(overrides: Partial<Adoption> = {}): Adoption {
  return {
    id: "ad1", pattern_key: "ea.integration.domain-event-backbone", pattern_name: "Domain Event Backbone",
    kind: "reference-architecture", name: "Claims backbone", scope_type: "business_domain",
    scope_ref: "d1", scope_name: "Claims", member_ids: [], pinned_version: null, resolved_version: "1.0.0",
    pins: [{ role_key: "backbone", element_type: "application", element_id: "hub" }],
    created_at: "", created_by: "ea", updated_at: "", status: "non_conformant", ...overrides,
  };
}

function report(overrides: Partial<ConformanceReport> = {}): ConformanceReport {
  return {
    adoption_id: "ad1", pattern_key: "ea.integration.domain-event-backbone", version: "1.0.0", digest: "d",
    evaluated_at: "", scope: { scope_type: "business_domain", scope_ref: "d1", member_ids: [] },
    bindings: [
      { role_key: "backbone", element_type: "application", label: "Backbone", count: 1,
        elements: [{ type: "application", id: "hub", name: "Event Hub" }] },
      { role_key: "domain_app", element_type: "application", label: "Domain App", count: 0, elements: [] },
    ],
    findings: [{
      code: "C1", kind: "violation", severity: "error", rule: "Must use the backbone.",
      element_refs: [{ type: "integration", id: "i1", name: "Claims Core → Billing" }],
      element_count: 1, truncated: false,
    }],
    status: "non_conformant", plateau: null, ...overrides,
  };
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({ user: { role: "enterprise_architect" } } as never);
  api.useAdoptions.mockReturnValue({ data: { items: [adoption()], total: 1 }, isLoading: false } as never);
  api.useAdoption.mockReturnValue({ data: adoption(), isLoading: false, error: null } as never);
  api.useConformance.mockReturnValue({ data: report() } as never);
  api.useAdoptionView.mockReturnValue({
    data: { view: "conformance", flowchart: GOLDEN, digest: "d", generated_at: "", truncated: [] },
    isLoading: false, error: null,
  } as never);
  api.useCandidates.mockReturnValue({ data: [
    { type: "application", id: "hub", name: "Event Hub" },
    { type: "application", id: "a1", name: "Claims Core" },
  ] } as never);
  api.useSetPins.mockReturnValue(mutation());
  api.useDeleteAdoption.mockReturnValue(mutation());
  api.useCreateAdoption.mockReturnValue(mutation());
  api.useEvaluate.mockReturnValue(mutation());
  api.usePatternFamilies.mockReturnValue({ families: [
    { key: "ea.integration.domain-event-backbone", name: "Domain Event Backbone", kind: "reference-architecture", versions: ["1.0.0"] },
  ] } as never);
  api.useApplicationChoices.mockReturnValue({ data: [
    { type: "application", id: "a1", name: "Claims Core" }, { type: "application", id: "a2", name: "Billing" },
  ] } as never);
});

describe("AdoptionsList", () => {
  it("lists adoptions with their derived status and hides Adopt for reviewers", () => {
    render(<AdoptionsList />);
    expect(screen.getByText("Claims backbone")).toBeTruthy();
    expect(screen.getByText("Non-conformant")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Adopt a pattern" })).toBeTruthy();
    useAuth.mockReturnValue({ user: { role: "reviewer" } } as never);
    render(<AdoptionsList />);
    expect(screen.getAllByRole("button", { name: "Adopt a pattern" })).toHaveLength(1);
  });

  it("opens straight onto an adoption when given initialSelected (939, from Governance)", () => {
    render(<AdoptionsList initialSelected="ad-1" />);
    expect(api.useAdoption).toHaveBeenCalledWith("ad-1");
    expect(screen.queryByRole("button", { name: "Adopt a pattern" })).toBeNull();
  });
});

describe("AdoptionForm", () => {
  it("switches scope pickers and submits the right body", async () => {
    const create = vi.fn().mockResolvedValue(adoption());
    api.useCreateAdoption.mockReturnValue(mutation(create));
    const onCreated = vi.fn();
    render(<AdoptionForm onCreated={onCreated} onCancel={() => {}} />);
    await userEvent.selectOptions(screen.getByLabelText("Pattern"), "ea.integration.domain-event-backbone");
    await userEvent.type(screen.getByLabelText("Adoption name"), "Set A");
    expect(screen.getByLabelText("Business domain")).toBeTruthy();
    await userEvent.selectOptions(screen.getByLabelText("Scope type"), "application_set");
    expect(screen.queryByLabelText("Business domain")).toBeNull();
    await userEvent.selectOptions(screen.getByLabelText("Applications"), ["a1", "a2"]);
    await userEvent.selectOptions(screen.getByLabelText("Version"), "1.0.0");
    await userEvent.click(screen.getByRole("button", { name: "Adopt pattern" }));
    expect(create).toHaveBeenCalledWith({
      pattern_key: "ea.integration.domain-event-backbone", name: "Set A", scope_type: "application_set",
      scope_ref: null, member_ids: ["a1", "a2"], pinned_version: "1.0.0",
    });
    expect(onCreated).toHaveBeenCalled();
  });
});

describe("AdoptionPage", () => {
  it("shows status, bindings, findings and the conformance diagram", () => {
    render(<AdoptionPage adoptionId="ad1" onBack={() => {}} />);
    expect(screen.getByText("Non-conformant")).toBeTruthy();
    const findings = screen.getByRole("table", { name: "Findings" });
    expect(within(findings).getByText("Claims Core → Billing")).toBeTruthy();
    expect(screen.getByLabelText("Bindings").textContent).toContain("Event Hub");
    expect(screen.getByRole("img", { name: /conformance/ })).toBeTruthy();
  });

  it("shows migration progress for a transition", () => {
    api.useAdoption.mockReturnValue({ data: adoption({ kind: "transition" }), isLoading: false, error: null } as never);
    api.useConformance.mockReturnValue({ data: report({ plateau: { reached: "PL1", next: "PL2", blocking: ["C2"] } }) } as never);
    render(<AdoptionPage adoptionId="ad1" onBack={() => {}} />);
    expect(screen.getByLabelText("Plateau").textContent).toContain("reached PL1");
    expect(screen.getByLabelText("Plateau").textContent).toContain("blocked by C2");
    expect(screen.getByLabelText("Adoption view")).toBeTruthy();
  });

  it("Save as diagram hands a flowchart seed to the Diagrams editor", async () => {
    const onGenerateDiagram = vi.fn();
    render(<AdoptionPage adoptionId="ad1" onBack={() => {}} onGenerateDiagram={onGenerateDiagram} />);
    await userEvent.click(screen.getByRole("button", { name: "Save as diagram" }));
    const seed = onGenerateDiagram.mock.calls[0][0];
    expect(seed.diagramType).toBe("flowchart");
    expect(seed.title).toBe("Claims backbone — conformance");
    expect(seed.model.nodes.length).toBeGreaterThan(3);
  });

  it("hides pins and delete for reviewers", () => {
    useAuth.mockReturnValue({ user: { role: "reviewer" } } as never);
    render(<AdoptionPage adoptionId="ad1" onBack={() => {}} />);
    expect(screen.queryByRole("button", { name: "Delete adoption" })).toBeNull();
    expect(screen.queryByLabelText("Pin role")).toBeNull();
  });
});

describe("PinsEditor", () => {
  it("adds a pin from the role's candidates and shows 422 reasons", async () => {
    const setPins = vi.fn().mockRejectedValue(
      new ApiError(422, "PUT failed", { detail: { message: "1 invalid pin(s)", reasons: ["application 'x' does not exist"] } }),
    );
    api.useSetPins.mockReturnValue(mutation(setPins));
    render(<PinsEditor adoption={adoption({ pins: [] })} roles={report().bindings} />);
    await userEvent.selectOptions(screen.getByLabelText("Pin element"), "a1");
    await userEvent.click(screen.getByRole("button", { name: "Pin" }));
    expect(setPins).toHaveBeenCalledWith([{ role_key: "backbone", element_type: "application", element_id: "a1" }]);
    expect((await screen.findByRole("alert")).textContent).toContain("does not exist");
  });
});

describe("DiscoveryTab and EvaluatePanel", () => {
  it("lists discovery matches", () => {
    api.useDiscovery.mockReturnValue({ data: { pattern_key: "k", version: "1.0.0", digest: "d", evaluated_at: "",
      match_count: 1, matches: report().findings }, isLoading: false, error: null } as never);
    render(<DiscoveryTab patternKey="k" version="1.0.0" />);
    expect(screen.getByText(/occurrence of this anti-pattern/)).toBeTruthy();
    expect(screen.getByText("Claims Core → Billing")).toBeTruthy();
  });

  it("evaluates a draft against a domain", async () => {
    const run = vi.fn().mockResolvedValue(report());
    api.useEvaluate.mockReturnValue(mutation(run));
    render(<EvaluatePanel yaml="pattern: x" />);
    await userEvent.selectOptions(screen.getByLabelText("Evaluate scope"), "business_domain");
    await userEvent.selectOptions(screen.getByLabelText("Evaluate domain"), "d2");
    await userEvent.click(screen.getByRole("button", { name: "Evaluate" }));
    expect(run).toHaveBeenCalledWith({ yaml: "pattern: x", scope: { scope_type: "business_domain", scope_ref: "d2", member_ids: [] } });
    expect(await screen.findByText("Non-conformant")).toBeTruthy();
  });
});

describe("flowchartToSeed", () => {
  it("returns null for unparsable text", () => {
    expect(flowchartToSeed("not a flowchart", "x")).toBeNull();
  });
});
