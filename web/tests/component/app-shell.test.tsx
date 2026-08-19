/**
 * Component tests for the application shell — ADP-SPEC-037.
 *
 * Covers FR-001 (single persistent left-rail shell), FR-002 (navigation
 * destinations defined in one place), FR-003 (Workspace / Architecture /
 * Oversight / Design groups), and FR-004 (active-view indication). The
 * shell owns the entire navigation surface, so exercising it here is the
 * single-source check that complements the static SC-001 grep.
 *
 * The Design group (Designs / Intake / C4 Design) is always rendered, not
 * gated on a design being selected -- it's the entry point into any design,
 * and a user reported it disappearing entirely when no design was open
 * (having to select one first to even see the menu). Only its label adapts:
 * "Design" with none selected, "Design · {id}" once inside one.
 *
 * Recommendations is deliberately NOT a nav entry here: it's a tab inside
 * the Intake screen itself (the second step of Intake's own flow), not a
 * standalone destination -- see IntakePage.tsx's own tab bar instead.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";

import { AppShell } from "../../src/ui";

afterEach(cleanup);

const WORKSPACE = ["Overview", "Insights"];
const ARCHITECTURE = ["Business", "Applications", "Technical Architecture"];
const OVERSIGHT = ["APM", "Governance", "Knowledge"];
const DESIGN_SCOPED = ["Designs", "Intake", "C4 Design"];

function rail(): HTMLElement {
  const el = document.querySelector("nav.shell-rail");
  if (!el) throw new Error("shell-rail not found");
  return el as HTMLElement;
}

function navButton(label: string): HTMLButtonElement {
  const btn = within(rail()).getByText(label).closest("button");
  if (!btn) throw new Error(`nav button "${label}" not found`);
  return btn as HTMLButtonElement;
}

describe("AppShell", () => {
  it("renders a single rail with the Workspace and Architecture groups (FR-001, FR-002, FR-003)", () => {
    render(
      <AppShell currentView="overview" onNavigate={vi.fn()} designId={null}>
        <div>page-content</div>
      </AppShell>,
    );

    // Exactly one navigation rail — the whole nav surface lives in one shell.
    expect(document.querySelectorAll("nav.shell-rail").length).toBe(1);

    expect(within(rail()).getByText("Workspace")).toBeTruthy();
    expect(within(rail()).getByText("Architecture")).toBeTruthy();
    expect(within(rail()).getByText("Oversight")).toBeTruthy();
    for (const label of [...WORKSPACE, ...ARCHITECTURE, ...OVERSIGHT]) {
      expect(navButton(label)).toBeTruthy();
    }

    // Page content renders inside the shell content area.
    expect(screen.getByText("page-content")).toBeTruthy();
  });

  it("shows the Design group, labelled plainly, when no design is selected (FR-003)", () => {
    render(
      <AppShell currentView="overview" onNavigate={vi.fn()} designId={null}>
        <div />
      </AppShell>,
    );
    expect(within(rail()).getByText("Design")).toBeTruthy();
    expect(within(rail()).queryByText(/^Design ·/)).toBeNull();
    for (const label of DESIGN_SCOPED) {
      expect(navButton(label)).toBeTruthy();
    }
    // Recommendations is no longer a standalone nav destination -- it's a
    // tab inside Intake itself.
    expect(within(rail()).queryByText("Recommendations")).toBeNull();
  });

  it("renders the Design group in Designs -> Intake -> C4 Design order", () => {
    render(
      <AppShell currentView="overview" onNavigate={vi.fn()} designId={null}>
        <div />
      </AppShell>,
    );
    const [designs, intake, canvas] = DESIGN_SCOPED.map((label) => navButton(label));
    expect(designs.compareDocumentPosition(intake) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(intake.compareDocumentPosition(canvas) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  it("shows the Design group, labelled with the design id, when one is selected (FR-003)", () => {
    render(
      <AppShell currentView="intake" onNavigate={vi.fn()} designId="DESIGN-001">
        <div />
      </AppShell>,
    );
    expect(within(rail()).getByText("Design · DESIGN-001")).toBeTruthy();
    for (const label of DESIGN_SCOPED) {
      expect(navButton(label)).toBeTruthy();
    }
  });

  it("marks only the current view active (FR-004)", () => {
    render(
      <AppShell currentView="portfolio" onNavigate={vi.fn()} designId={null}>
        <div />
      </AppShell>,
    );
    expect(navButton("APM").className).toContain("active");
    expect(navButton("Governance").className).not.toContain("active");
  });

  it("routes every destination through the shared onNavigate handler (FR-001, FR-002)", () => {
    const onNavigate = vi.fn();
    render(
      <AppShell currentView="overview" onNavigate={onNavigate} designId="DESIGN-001">
        <div />
      </AppShell>,
    );
    fireEvent.click(navButton("Business"));
    expect(onNavigate).toHaveBeenCalledWith("business");

    fireEvent.click(navButton("C4 Design"));
    expect(onNavigate).toHaveBeenCalledWith("canvas-v2");
  });

  it("clicking Intake calls onStartNewDesign, not onNavigate, when provided", () => {
    const onNavigate = vi.fn();
    const onStartNewDesign = vi.fn();
    render(
      <AppShell currentView="overview" onNavigate={onNavigate} designId="DESIGN-001" onStartNewDesign={onStartNewDesign}>
        <div />
      </AppShell>,
    );
    fireEvent.click(navButton("Intake"));
    expect(onStartNewDesign).toHaveBeenCalledTimes(1);
    expect(onNavigate).not.toHaveBeenCalled();
  });

  it("clicking Intake falls back to onNavigate('intake') when onStartNewDesign is omitted", () => {
    const onNavigate = vi.fn();
    render(
      <AppShell currentView="overview" onNavigate={onNavigate} designId={null}>
        <div />
      </AppShell>,
    );
    fireEvent.click(navButton("Intake"));
    expect(onNavigate).toHaveBeenCalledWith("intake");
  });

  it("onStartNewDesign does not leak to the other Design-group entries", () => {
    const onNavigate = vi.fn();
    const onStartNewDesign = vi.fn();
    render(
      <AppShell currentView="overview" onNavigate={onNavigate} designId="DESIGN-001" onStartNewDesign={onStartNewDesign}>
        <div />
      </AppShell>,
    );
    fireEvent.click(navButton("Designs"));
    expect(onNavigate).toHaveBeenCalledWith("designs");

    fireEvent.click(navButton("C4 Design"));
    expect(onNavigate).toHaveBeenCalledWith("canvas-v2");

    expect(onStartNewDesign).not.toHaveBeenCalled();
  });
});
