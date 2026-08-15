/** Component tests for the application registry UI (ADP-SPEC-036). */

import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

import ApplicationForm from "../../src/application/ApplicationForm";
import TechCapForm from "../../src/application/TechCapForm";
import IntegrationForm from "../../src/application/IntegrationForm";
import ApplicationList from "../../src/application/ApplicationList";
import TechCapTree from "../../src/application/TechCapTree";
import IntegrationList from "../../src/application/IntegrationList";
import CapabilityLinksEditor from "../../src/application/CapabilityLinksEditor";
import TechCapLinkEditor from "../../src/application/TechCapLinkEditor";
import StageLinkEditor from "../../src/application/StageLinkEditor";
import DomainIntegrationEditor from "../../src/application/DomainIntegrationEditor";
import DesignLinkEditor from "../../src/application/DesignLinkEditor";
import ApplicationDetail from "../../src/application/ApplicationDetail";
import ApplicationPage from "../../src/application/ApplicationPage";
import type { Application, TechnicalCapability } from "../../src/api/application";

import { mockFetch, renderWithQuery, lastCall } from "./registry-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const APP: Application = {
  id: "app-1", name: "CRM", description: "Customer platform", vendor: "Acme",
  primary_owner: "jane", time_classification: "Invest", r_strategy: "Refactor",
  pace_layer: "Differentiation", health_score: 4,
  business_value: null, business_criticality: null,
  owning_business_unit: null, business_owner: null, technical_owner: null, lifecycle_status: "active",
  hosting_model: null, architecture_pattern: null, tech_debt_flags: [],
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

const APP2: Application = { ...APP, id: "app-2", name: "Ledger", vendor: null, time_classification: null, health_score: null };

const TC: TechnicalCapability = {
  id: "tc-1", name: "Messaging", description: null, parent_id: null, level: 1,
  created_at: "2026-01-01T00:00:00Z", strategic_relevance: null,
};
const TC_CHILD: TechnicalCapability = { ...TC, id: "tc-2", name: "Queues", parent_id: "tc-1", level: 2 };

describe("ApplicationForm", () => {
  it("submits trimmed fields via onSave", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderWithQuery(<ApplicationForm onSave={onSave} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("My Application"), {
      target: { value: "  CRM  " },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(expect.objectContaining({ name: "CRM" })),
    );
  });

  it("disables Assess Health and Assess Business Value with no application to assess against yet (New mode)", () => {
    renderWithQuery(<ApplicationForm onSave={vi.fn()} onCancel={vi.fn()} />);

    // Both Health's and Business Value's read-only displays show this text
    // when unassessed -- two matches, not one.
    expect(screen.getAllByText("— not assessed —")).toHaveLength(2);
    expect(screen.getByRole("button", { name: "Assess Health" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Assess Business Value" }).hasAttribute("disabled")).toBe(true);
  });

  it("shows the current health score and business value read-only (not editable) in Edit mode", () => {
    renderWithQuery(<ApplicationForm initial={APP} onSave={vi.fn()} onCancel={vi.fn()} />);

    expect(screen.getByText(/★★★★☆ \(4\)/)).toBeDefined(); // health_score: 4
    expect(screen.queryByLabelText(/Health Score/)).toBeNull();
    expect(screen.queryByLabelText(/Business Value/)).toBeNull();
    expect(screen.getByRole("button", { name: "Assess Health" }).hasAttribute("disabled")).toBe(false);
    expect(screen.getByRole("button", { name: "Assess Business Value" }).hasAttribute("disabled")).toBe(false);
  });
});

describe("TechCapForm", () => {
  it("submits with the parent id when nesting", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderWithQuery(<TechCapForm parent={TC} onSave={onSave} onCancel={vi.fn()} />);

    expect(screen.getByText(/Under: Messaging \(L1\)/)).toBeDefined();
    fireEvent.change(screen.getByPlaceholderText("Capability name *"), {
      target: { value: "Queues" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({ name: "Queues", parent_id: "tc-1" }),
      ),
    );
  });
});

describe("IntegrationForm", () => {
  it("rejects a self-integration before calling onSave", () => {
    const onSave = vi.fn();
    renderWithQuery(
      <IntegrationForm apps={[APP, APP2]} onSave={onSave} onCancel={vi.fn()} />,
    );
    const [source, target] = screen.getAllByRole("combobox");
    fireEvent.change(source, { target: { value: "app-1" } });
    fireEvent.change(target, { target: { value: "app-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(screen.getByText("Source and target must be different")).toBeDefined();
    expect(onSave).not.toHaveBeenCalled();
  });

  it("submits a valid integration", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    renderWithQuery(
      <IntegrationForm apps={[APP, APP2]} onSave={onSave} onCancel={vi.fn()} />,
    );
    const [source, target] = screen.getAllByRole("combobox");
    fireEvent.change(source, { target: { value: "app-1" } });
    fireEvent.change(target, { target: { value: "app-2" } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(onSave).toHaveBeenCalledWith(
        expect.objectContaining({
          source_app_id: "app-1",
          target_app_id: "app-2",
          integration_type: "API",
        }),
      ),
    );
  });
});

describe("ApplicationList", () => {
  it("renders apps with TIME badge and health stars; fires callbacks", () => {
    const onSelect = vi.fn();
    const onAdd = vi.fn();
    renderWithQuery(
      <ApplicationList apps={[APP, APP2]} selectedId={null} onSelect={onSelect} onAdd={onAdd} />,
    );

    expect(screen.getByText("Applications (2)")).toBeDefined();
    expect(screen.getByText("Invest")).toBeDefined();
    expect(screen.getByText("★★★★☆")).toBeDefined();

    fireEvent.click(screen.getByText("Ledger"));
    expect(onSelect).toHaveBeenCalledWith("app-2");
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(onAdd).toHaveBeenCalled();
  });
});

describe("TechCapTree", () => {
  it("renders the hierarchy and creates a root capability", async () => {
    const calls = mockFetch({
      "GET /api/v1/technical-capabilities": { items: [TC, TC_CHILD], total: 2 },
      "POST /api/v1/technical-capabilities": { ...TC, id: "tc-3", name: "Storage" },
    });
    renderWithQuery(<TechCapTree />);

    await waitFor(() => expect(screen.getByText("Messaging")).toBeDefined());
    expect(screen.getByText("Queues")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "+ Root" }));
    fireEvent.change(screen.getByPlaceholderText("Capability name *"), {
      target: { value: "Storage" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(lastCall(calls, "POST")?.body).toMatchObject({ name: "Storage", parent_id: null }),
    );
  });
});

describe("IntegrationList", () => {
  it("renders integrations and deletes after confirm", async () => {
    vi.stubGlobal("confirm", vi.fn(() => true));
    const calls = mockFetch({
      "GET /api/v1/integrations": {
        items: [{
          id: "int-1", source_app_id: "app-1", target_app_id: "app-2",
          source_app_name: "CRM", target_app_name: "Ledger",
          integration_type: "API", description: "sync",
          created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
        }],
        total: 1,
      },
      "DELETE /api/v1/integrations/int-1": [204, null],
    });
    renderWithQuery(<IntegrationList apps={[APP, APP2]} />);

    expect(await screen.findByText("CRM → Ledger")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "✕" }));
    await waitFor(() =>
      expect(lastCall(calls, "DELETE")?.url).toBe("/api/v1/integrations/int-1"),
    );
  });
});

describe("CapabilityLinksEditor", () => {
  it("links a business capability with a fit score", async () => {
    const calls = mockFetch({
      "GET /api/v1/applications/app-1/capability-links": { items: [], total: 0 },
      "GET /api/v1/business/capabilities": {
        items: [{
          id: "cap-1", name: "Billing", description: null, level: 1, parent_id: null,
          position: 0, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
          domain_id: null, domain_name: null,
        }],
        total: 1,
      },
      "POST /api/v1/applications/app-1/capability-links": {
        app_id: "app-1", capability_id: "cap-1", capability_name: "Billing", fit_score: 5,
      },
    });
    renderWithQuery(<CapabilityLinksEditor appId="app-1" />);

    expect(await screen.findByText("No linked capabilities.")).toBeDefined();
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "cap-1" } });
    fireEvent.change(screen.getByTitle("Fit score 1–5"), { target: { value: "5" } });
    fireEvent.click(screen.getByRole("button", { name: "Link" }));

    await waitFor(() =>
      expect(lastCall(calls, "POST")?.body).toEqual({ capability_id: "cap-1", fit_score: 5 }),
    );
  });
});

describe("TechCapLinkEditor", () => {
  it("groups links by usage and links a tech capability", async () => {
    const calls = mockFetch({
      "GET /api/v1/applications/app-1/technical-capability-links": {
        items: [{ app_id: "app-1", tech_cap_id: "tc-1", tech_cap_name: "Messaging", usage_type: "provides" }],
        total: 1,
      },
      "GET /api/v1/technical-capabilities": { items: [TC, TC_CHILD], total: 2 },
      "POST /api/v1/applications/app-1/technical-capability-links": {
        app_id: "app-1", tech_cap_id: "tc-2", tech_cap_name: "Queues", usage_type: "consumes",
      },
    });
    renderWithQuery(<TechCapLinkEditor appId="app-1" />);

    expect(await screen.findByText("Messaging")).toBeDefined();

    const [capSelect, usageSelect] = screen.getAllByRole("combobox");
    fireEvent.change(capSelect, { target: { value: "tc-2" } });
    fireEvent.change(usageSelect, { target: { value: "consumes" } });
    fireEvent.click(screen.getByRole("button", { name: "Link" }));

    await waitFor(() =>
      expect(lastCall(calls, "POST")?.body).toEqual({ tech_cap_id: "tc-2", usage_type: "consumes" }),
    );
  });
});

describe("StageLinkEditor", () => {
  it("renders stage links and unlinks one", async () => {
    const calls = mockFetch({
      "GET /api/v1/applications/app-1/stage-links": {
        items: [{ app_id: "app-1", stage_id: "stg-1", stage_name: "Quote", value_stream_name: "O2C" }],
        total: 1,
      },
      "GET /api/v1/business/value-streams": { items: [], total: 0 },
      "DELETE /api/v1/applications/app-1/stage-links/stg-1": [204, null],
    });
    renderWithQuery(<StageLinkEditor appId="app-1" />);

    expect(await screen.findByText("Quote")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "✕" }));
    await waitFor(() => expect(lastCall(calls, "DELETE")).toBeDefined());
  });
});

describe("DomainIntegrationEditor", () => {
  it("adds a domain integration", async () => {
    const calls = mockFetch({
      "GET /api/v1/applications/app-1/domain-integrations": { items: [], total: 0 },
      "GET /api/v1/business/domains": {
        items: [{ id: "dom-1", name: "Finance", classification: "strategic", org_unit: null, risk_flags: [], capability_count: 0 }],
        total: 1,
      },
      "POST /api/v1/applications/app-1/domain-integrations": {
        id: "adi-1", app_id: "app-1", domain_id: "dom-1", domain_name: "Finance",
        integration_type: "API", direction: "outbound", created_at: "2026-01-01T00:00:00Z",
      },
    });
    renderWithQuery(<DomainIntegrationEditor appId="app-1" />);

    expect(await screen.findByText("No domain integrations.")).toBeDefined();
    const [domainSelect, dirSelect] = screen.getAllByRole("combobox");
    fireEvent.change(domainSelect, { target: { value: "dom-1" } });
    fireEvent.change(dirSelect, { target: { value: "outbound" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(lastCall(calls, "POST")?.body).toMatchObject({
        domain_id: "dom-1", direction: "outbound",
      }),
    );
  });
});

describe("DesignLinkEditor (application)", () => {
  it("links a design to the application", async () => {
    const calls = mockFetch({
      "GET /api/v1/applications/app-1/design-links": { items: [], total: 0 },
      "GET /api/v1/designs?page=1&page_size=100": {
        designs: [{ id: "DSN-1", title: "Payments Design" }],
      },
      "POST /api/v1/applications/app-1/design-links": { app_id: "app-1", design_id: "DSN-1" },
    });
    renderWithQuery(<DesignLinkEditor appId="app-1" />);

    expect(await screen.findByText("No designs linked.")).toBeDefined();
    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "DSN-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Link" }));

    await waitFor(() =>
      expect(lastCall(calls, "POST")?.body).toEqual({ design_id: "DSN-1" }),
    );
  });
});

describe("ApplicationDetail", () => {
  it("renders the overview and switches sections", async () => {
    mockFetch({
      "GET /api/v1/applications/app-1": APP,
      "GET /api/v1/applications/app-1/capability-links": { items: [], total: 0 },
      "GET /api/v1/business/capabilities": { items: [], total: 0 },
    });
    renderWithQuery(<ApplicationDetail appId="app-1" allApps={[APP]} onDeleted={vi.fn()} />);

    expect(await screen.findByText("CRM")).toBeDefined();
    expect(screen.getByText("Invest")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Capabilities" }));
    expect(await screen.findByText("Business Capabilities")).toBeDefined();
  });
});

describe("ApplicationPage", () => {
  it("lists applications and opens the create form", async () => {
    mockFetch({
      "GET /api/v1/applications": { items: [APP], total: 1 },
    });
    renderWithQuery(<ApplicationPage />);

    expect(await screen.findByText("CRM")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(await screen.findByText("New Application")).toBeDefined();
  });
});
