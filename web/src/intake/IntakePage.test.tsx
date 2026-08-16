// ADP: Intake must be reachable with no design selected -- IntakePage renders
// the same shell either way, only gating the design-dependent pieces
// (sidebar, Structured Form, proposal review) on a resolved designId.
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import IntakePage from "./IntakePage";

vi.mock("../api/intake", () => ({
  useIntakeStatus: () => ({ data: undefined }),
}));

vi.mock("./IntakeTextForm", () => ({
  default: () => <div>IntakeTextForm-stub</div>,
}));
vi.mock("./StructuredForm", () => ({
  default: () => <div>StructuredForm-stub</div>,
}));
vi.mock("./ProposalsList", () => ({
  default: () => <div>ProposalsList-stub</div>,
}));
vi.mock("./RequirementsList", () => ({
  default: () => <div>RequirementsList-stub</div>,
}));
vi.mock("./LLMSettings", () => ({
  default: () => <div>LLMSettings-stub</div>,
}));
vi.mock("../business/BusinessContextPanel", () => ({
  default: () => <div>BusinessContextPanel-stub</div>,
}));
vi.mock("./CapabilityGapPanel", () => ({
  default: () => <div>CapabilityGapPanel-stub</div>,
}));

describe("IntakePage with no design selected yet", () => {
  it("still renders the Intake form (not blocked or redirected)", () => {
    render(<IntakePage designId={null} onNavigate={vi.fn()} />);
    expect(screen.getByText("IntakeTextForm-stub")).toBeTruthy();
  });

  it("shows a placeholder instead of the requirements sidebar", () => {
    render(<IntakePage designId={null} onNavigate={vi.fn()} />);
    expect(screen.queryByText("RequirementsList-stub")).toBeNull();
    expect(screen.getByText(/appear here once the design starts/i)).toBeTruthy();
  });

  it("shows a placeholder instead of the Structured Form tab", () => {
    render(<IntakePage designId={null} onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByText("Structured Form"));
    expect(screen.queryByText("StructuredForm-stub")).toBeNull();
    expect(screen.getByText(/Start with Guided Intake/i)).toBeTruthy();
  });
});

describe("IntakePage with a design already selected", () => {
  it("renders the requirements sidebar and Structured Form normally", () => {
    render(<IntakePage designId="DSN-001" onNavigate={vi.fn()} />);
    expect(screen.getByText("RequirementsList-stub")).toBeTruthy();

    fireEvent.click(screen.getByText("Structured Form"));
    expect(screen.getByText("StructuredForm-stub")).toBeTruthy();
  });
});
