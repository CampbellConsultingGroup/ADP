import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import InspectionPanel from "../../src/inspection/InspectionPanel";
import type { ArchitectureDescription } from "../../src/types";

const baseDesign: ArchitectureDescription = {
  id: "D-001",
  schema_version: "1.0.0",
  title: "Test Design",
  elements: [
    {
      id: "ELM-001",
      name: "API Gateway",
      kind: "container",
      satisfies: ["REQ-001"],
      provenance: "opt-001",
    },
    {
      id: "ELM-002",
      name: "User",
      kind: "person",
      satisfies: [],
      provenance: undefined,
    },
  ],
  relationships: [],
  requirements: [
    { id: "REQ-001", title: "Stateless handling" },
    { id: "REQ-002", title: "Auth at gateway" },
  ],
};

describe("InspectionPanel", () => {
  it("test_inspection_panel_shows_satisfies — renders requirement title", () => {
    render(
      <InspectionPanel elementId="ELM-001" design={baseDesign} onClose={vi.fn()} />,
    );
    expect(screen.getByText(/Stateless handling/i)).toBeDefined();
    expect(screen.getByText(/REQ-001/i)).toBeDefined();
  });

  it("test_inspection_panel_shows_provenance — renders recommendation reference", () => {
    render(
      <InspectionPanel elementId="ELM-001" design={baseDesign} onClose={vi.fn()} />,
    );
    expect(screen.getByText(/recommendation/i)).toBeDefined();
    expect(screen.getByText(/OPT-001/i)).toBeDefined();
  });

  it("test_inspection_panel_shows_no_requirements_message — empty satisfies", () => {
    render(
      <InspectionPanel elementId="ELM-002" design={baseDesign} onClose={vi.fn()} />,
    );
    expect(screen.getByText(/No requirements satisfied/i)).toBeDefined();
  });

  it("returns null when elementId is null", () => {
    const { container } = render(
      <InspectionPanel elementId={null} design={baseDesign} onClose={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it("manually placed element shows correct provenance", () => {
    render(
      <InspectionPanel elementId="ELM-002" design={baseDesign} onClose={vi.fn()} />,
    );
    expect(screen.getByText(/Manually placed/i)).toBeDefined();
  });
});
