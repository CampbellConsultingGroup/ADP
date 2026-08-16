// ADP: Intake must be reachable with no design selected -- IntakePage renders
// the same shell either way, only gating the design-dependent pieces
// (the requirements sidebar) on a resolved designId. There is no longer a
// Structured Form tab or an AI-extraction review step (both removed).
import { describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import IntakePage from "./IntakePage";

vi.mock("./IntakeTextForm", () => ({
  default: ({ onSubmitted }: { onSubmitted: (requirementCount: number, capabilityCount: number) => void }) => (
    <button onClick={() => onSubmitted(2, 1)}>IntakeTextForm-stub submit</button>
  ),
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
    expect(screen.getByText("IntakeTextForm-stub submit")).toBeTruthy();
  });

  it("shows a placeholder instead of the requirements sidebar", () => {
    render(<IntakePage designId={null} onNavigate={vi.fn()} />);
    expect(screen.queryByText("RequirementsList-stub")).toBeNull();
    expect(screen.getByText(/appear here once the design starts/i)).toBeTruthy();
  });

  it("only offers Intake and LLM Settings tabs (no Structured Form)", () => {
    render(<IntakePage designId={null} onNavigate={vi.fn()} />);
    expect(screen.queryByText("Structured Form")).toBeNull();
    expect(screen.getByText("Intake")).toBeTruthy();
    expect(screen.getByText("⚙ LLM Settings")).toBeTruthy();
  });
});

describe("IntakePage with a design already selected", () => {
  it("renders the requirements sidebar", () => {
    render(<IntakePage designId="DSN-001" onNavigate={vi.fn()} />);
    expect(screen.getByText("RequirementsList-stub")).toBeTruthy();
  });

  it("shows a confirmation banner once the form reports a successful submit", () => {
    render(<IntakePage designId="DSN-001" onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByText("IntakeTextForm-stub submit"));
    expect(screen.getByText(/2 requirements added/i)).toBeTruthy();
    expect(screen.getByText(/1 business capability linked/i)).toBeTruthy();
  });

  it("switches to the LLM Settings tab", () => {
    render(<IntakePage designId="DSN-001" onNavigate={vi.fn()} />);
    fireEvent.click(screen.getByText("⚙ LLM Settings"));
    expect(screen.getByText("LLMSettings-stub")).toBeTruthy();
  });
});
