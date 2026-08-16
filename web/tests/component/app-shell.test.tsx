/**
 * Component tests for the application shell — ADP-SPEC-037.
 *
 * Covers FR-001 (single persistent left-rail shell), FR-002 (navigation
 * destinations defined in one place), FR-003 (Workspace / Architecture /
 * Oversight / Design groups), and FR-004 (active-view indication). The
 * shell owns the entire navigation surface, so exercising it here is the
 * single-source check that complements the static SC-001 grep.
 *
 * The Design group (Intake / Recommendations / Designs / C4 Design) is
 * always rendered, not gated on a design being selected -- it's the entry
 * point into any design, and a user reported it disappearing entirely when
 * no design was open (having to select one first to even see the menu).
 * Only its label adapts: "Design" with none selected, "Design · {id}" once
 * inside one.
 */
import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";

import { AppShell } from "../../src/ui";

afterEach(cleanup);

const WORKSPACE = ["Overview", "Insights"];
const ARCHITECTURE = ["Business", "Applications", "Technical Architecture"];
const OVERSIGHT = ["APM", "Governance", "Knowledge"];
const DESIGN_SCOPED = ["Intake", "Recommendations", "Designs", "C4 Design"];

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
});
