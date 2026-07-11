/** Component tests for the business architecture UI (ADP-SPEC-033/034/035). */

import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

import CapabilityForm from "../../src/business/CapabilityForm";
import ValueStreamForm from "../../src/business/ValueStreamForm";
import DomainForm from "../../src/business/DomainForm";
import ValueStreamList from "../../src/business/ValueStreamList";
import DomainList from "../../src/business/DomainList";
import BusinessContextPanel from "../../src/business/BusinessContextPanel";
import DesignLinkEditor from "../../src/business/DesignLinkEditor";
import StageCapsEditor from "../../src/business/StageCapsEditor";
import ValueStreamStageEditor from "../../src/business/ValueStreamStageEditor";
import ValueStreamDetail from "../../src/business/ValueStreamDetail";
import DomainDetail from "../../src/business/DomainDetail";

import { mockFetch, renderWithQuery, lastCall } from "./registry-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CAP = {
  id: "cap-1", name: "Billing", description: null, level: 1, parent_id: null,
  position: 0, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  domain_id: null, domain_name: null,
};

const VS = {
  id: "vs-1", name: "Order to Cash", description: "cash cycle", stakeholder: "CFO",
  position: 0, created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
};

const STAGE = { id: "stg-1", value_stream_id: "vs-1", name: "Quote", description: null, position: 0 };

const DOMAIN_SUMMARY = {
  id: "dom-1", name: "Finance", classification: "strategic", org_unit: "CFO Office",
  risk_flags: ["PII"], capability_count: 2,
};

const DOMAIN_DETAIL = {
  id: "dom-1", name: "Finance", scope_statement: "In: money. Out: fun.",
  classification: "strategic", org_unit: "CFO Office", risk_flags: ["PII"],
  created_at: "2026-01-01T00:00:00Z", updated_at: "2026-01-01T00:00:00Z",
  capabilities: [{ capability_id: "cap-1", name: "Billing", level: 1 }],
};

describe("CapabilityForm", () => {
  it("submits a new L1 capability and calls onDone", async () => {
    const calls = mockFetch({
      "POST /api/v1/business/capabilities": { ...CAP },
    });
    const onDone = vi.fn();
    renderWithQuery(
      <CapabilityForm parentId={null} level={1} onDone={onDone} onCancel={vi.fn()} />,
    );
    expect(screen.getByText(/New Strategic \(L1\) capability/)).toBeDefined();

    fireEvent.change(screen.getByPlaceholderText("Capability name"), {
      target: { value: "Billing" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    const post = lastCall(calls, "POST");
    expect(post?.body).toMatchObject({ name: "Billing", level: 1, parent_id: null });
  });
});

describe("ValueStreamForm", () => {
  it("submits a new value stream and calls onDone", async () => {
    const calls = mockFetch({
      "POST /api/v1/business/value-streams": { ...VS },
    });
    const onDone = vi.fn();
    renderWithQuery(<ValueStreamForm onDone={onDone} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Order to Cash"), {
      target: { value: "Procure to Pay" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => expect(onDone).toHaveBeenCalled());
    expect(lastCall(calls, "POST")?.body).toMatchObject({ name: "Procure to Pay" });
  });
});

describe("DomainForm", () => {
  it("parses comma-separated risk flags into a list on submit", () => {
    const onSubmit = vi.fn();
    renderWithQuery(<DomainForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    fireEvent.change(screen.getByPlaceholderText("Customer Domain"), {
      target: { value: "Finance" },
    });
    fireEvent.change(screen.getByPlaceholderText("PII, GDPR, SOX"), {
      target: { value: "PII, GDPR" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ name: "Finance", risk_flags: ["PII", "GDPR"] }),
    );
  });

  it("shows an error when name is blank", () => {
    const onSubmit = vi.fn();
    renderWithQuery(<DomainForm onSubmit={onSubmit} onCancel={vi.fn()} />);
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByText("Name is required")).toBeDefined();
    expect(onSubmit).not.toHaveBeenCalled();
  });
});

describe("ValueStreamList", () => {
  it("renders streams and fires onSelect on click", async () => {
    mockFetch({
      "GET /api/v1/business/value-streams": { items: [VS], total: 1 },
    });
    const onSelect = vi.fn();
    renderWithQuery(<ValueStreamList onSelect={onSelect} />);

    const row = await screen.findByText("Order to Cash");
    expect(screen.getByText(/1 value stream/)).toBeDefined();
    fireEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith("vs-1");
  });
});

describe("DomainList", () => {
  it("renders domains with classification badge and fires onSelect", async () => {
    mockFetch({
      "GET /api/v1/business/domains": { items: [DOMAIN_SUMMARY], total: 1 },
    });
    const onSelect = vi.fn();
    renderWithQuery(<DomainList onSelect={onSelect} />);

    const row = await screen.findByText("Finance");
    expect(screen.getByText("strategic")).toBeDefined();
    expect(screen.getByText(/2 L1 capabilities/)).toBeDefined();
    fireEvent.click(row);
    expect(onSelect).toHaveBeenCalledWith("dom-1");
  });
});

describe("BusinessContextPanel", () => {
  it("renders linked capabilities and value streams", async () => {
    mockFetch({
      "GET /api/v1/business/designs/DSN-1/context": {
        design_id: "DSN-1",
        capabilities: [{ capability_id: "cap-1", name: "Billing", level: 1 }],
        value_streams: [{ value_stream_id: "vs-1", name: "Order to Cash", stakeholder: "CFO" }],
      },
    });
    renderWithQuery(<BusinessContextPanel designId="DSN-1" onNavigate={vi.fn()} />);

    expect(await screen.findByText("Billing")).toBeDefined();
    expect(screen.getByText("Order to Cash")).toBeDefined();
  });

  it("offers navigation to Business when nothing is linked", async () => {
    mockFetch({
      "GET /api/v1/business/designs/DSN-1/context": {
        design_id: "DSN-1", capabilities: [], value_streams: [],
      },
    });
    const onNavigate = vi.fn();
    renderWithQuery(<BusinessContextPanel designId="DSN-1" onNavigate={onNavigate} />);

    fireEvent.click(await screen.findByRole("button", { name: /Go to Business/ }));
    expect(onNavigate).toHaveBeenCalledWith("business");
  });
});

describe("DesignLinkEditor (capability)", () => {
  const routes = {
    "GET /api/v1/business/capabilities/cap-1/designs": {
      items: [{ design_id: "DSN-1", title: "Payments Design", lifecycle_status: "draft" }],
    },
    "GET /api/v1/designs?page=1&page_size=100": {
      designs: [
        { id: "DSN-1", title: "Payments Design" },
        { id: "DSN-2", title: "Ledger Design" },
      ],
    },
  };

  it("lists linked designs and links an available one", async () => {
    const calls = mockFetch({
      ...routes,
      "POST /api/v1/business/capabilities/cap-1/designs": { items: [] },
    });
    renderWithQuery(<DesignLinkEditor entityType="capability" entityId="cap-1" />);

    expect(await screen.findByText("Payments Design")).toBeDefined();

    fireEvent.change(screen.getByRole("combobox"), { target: { value: "DSN-2" } });
    fireEvent.click(screen.getByRole("button", { name: "Link" }));

    await waitFor(() =>
      expect(lastCall(calls, "POST")?.body).toEqual({ design_id: "DSN-2" }),
    );
  });

  it("unlinks a linked design", async () => {
    const calls = mockFetch({
      ...routes,
      "DELETE /api/v1/business/capabilities/cap-1/designs/DSN-1": [204, null],
    });
    renderWithQuery(<DesignLinkEditor entityType="capability" entityId="cap-1" />);

    fireEvent.click(await screen.findByRole("button", { name: "Remove" }));
    await waitFor(() => expect(lastCall(calls, "DELETE")).toBeDefined());
  });
});

describe("StageCapsEditor", () => {
  it("links a capability to a stage", async () => {
    const calls = mockFetch({
      "GET /api/v1/business/value-streams/vs-1/stages/stg-1/capabilities": { items: [] },
      "GET /api/v1/business/capabilities": { items: [CAP], total: 1 },
      "POST /api/v1/business/value-streams/vs-1/stages/stg-1/capabilities": { items: [] },
    });
    renderWithQuery(<StageCapsEditor vsId="vs-1" stageId="stg-1" />);

    expect(await screen.findByText("None linked yet")).toBeDefined();

    fireEvent.change(await screen.findByRole("combobox"), { target: { value: "cap-1" } });
    fireEvent.click(screen.getByRole("button", { name: "Link" }));

    await waitFor(() =>
      expect(lastCall(calls, "POST")?.body).toEqual({ capability_id: "cap-1" }),
    );
  });
});

describe("ValueStreamStageEditor", () => {
  it("adds a stage via the add form", async () => {
    const calls = mockFetch({
      "GET /api/v1/business/value-streams/vs-1/stages/stg-1/capabilities": { items: [] },
      "GET /api/v1/business/capabilities": { items: [], total: 0 },
      "POST /api/v1/business/value-streams/vs-1/stages": { ...STAGE, id: "stg-2", name: "Bind" },
    });
    renderWithQuery(<ValueStreamStageEditor vsId="vs-1" stages={[STAGE]} />);

    expect(screen.getByText("Quote")).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "+ Add Stage" }));
    fireEvent.change(screen.getByPlaceholderText("Stage name"), { target: { value: "Bind" } });
    fireEvent.click(screen.getByRole("button", { name: "Add" }));

    await waitFor(() =>
      expect(lastCall(calls, "POST")?.body).toMatchObject({ name: "Bind", position: 1 }),
    );
  });
});

describe("ValueStreamDetail", () => {
  it("renders the stream, deletes after confirmation, and calls onBack", async () => {
    const calls = mockFetch({
      "GET /api/v1/business/value-streams/vs-1": { ...VS, stages: [STAGE] },
      "GET /api/v1/business/value-streams/vs-1/designs": { items: [] },
      "GET /api/v1/designs?page=1&page_size=100": { designs: [] },
      "GET /api/v1/business/value-streams/vs-1/stages/stg-1/capabilities": { items: [] },
      "GET /api/v1/business/capabilities": { items: [], total: 0 },
      "DELETE /api/v1/business/value-streams/vs-1": [204, null],
    });
    const onBack = vi.fn();
    renderWithQuery(<ValueStreamDetail vsId="vs-1" onBack={onBack} />);

    expect(await screen.findByText("Order to Cash")).toBeDefined();
    expect(screen.getByText(/Stakeholder: CFO/)).toBeDefined();

    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Yes, delete" }));

    await waitFor(() => expect(onBack).toHaveBeenCalled());
    expect(lastCall(calls, "DELETE")?.url).toBe("/api/v1/business/value-streams/vs-1");
  });
});

describe("DomainDetail", () => {
  it("renders domain fields and assigned capabilities", async () => {
    mockFetch({
      "GET /api/v1/business/domains/dom-1": DOMAIN_DETAIL,
      "GET /api/v1/business/capabilities": { items: [CAP], total: 1 },
    });
    renderWithQuery(<DomainDetail domainId="dom-1" onBack={vi.fn()} />);

    expect(await screen.findByText("Finance")).toBeDefined();
    expect(screen.getByText(/In: money/)).toBeDefined();
    expect(screen.getByText("PII")).toBeDefined();
    expect(screen.getByText("Billing")).toBeDefined();
  });
});
