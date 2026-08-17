// App.tsx's state machine (view / currentDesignId / pendingView, and the
// onNavigate/onSelectDesign/onStartNewDesign redirect logic) had zero test
// coverage before this file -- it was exercised only indirectly via
// AppShell.test.tsx, IntakePage.test.tsx, and manual/Playwright walkthroughs.
// Filed as a follow-up (ADP-57z) during the Design-section nav restructure
// (2026-08-17) and built out here.
//
// Every page App.tsx can render is mocked to a minimal stub exposing just the
// props relevant to routing (designId, continueTo, onSelectDesign, ...) --
// mirrors IntakePage.test.tsx's own established convention of stubbing its
// child components one level down, and OverviewPage.test.tsx's documented
// preference for mocking over standing up a real QueryClientProvider. Since
// every page is stubbed, none of their real API hooks ever fire, so no
// QueryClientProvider/fetch mocking is needed here at all. AppShell itself is
// NOT mocked -- its useAuth()/useTheme() already tolerate no provider
// (confirmed by AppShell.test.tsx's own header comment), and exercising the
// real nav is the point of these tests.
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import App from "./App";

vi.mock("./overview/OverviewPage", () => ({
  default: () => <div>OverviewPage-stub</div>,
}));
vi.mock("./insights/InsightsPage", () => ({
  default: () => <div>InsightsPage-stub</div>,
}));
vi.mock("./designs/DesignsPage", () => ({
  default: ({
    onSelectDesign,
    continueTo,
  }: {
    onSelectDesign: (id: string) => void;
    onNavigate: () => void;
    continueTo?: string | null;
  }) => (
    <div>
      DesignsPage-stub
      {continueTo && <div>continueTo:{continueTo}</div>}
      <button onClick={() => onSelectDesign("DSN-1")}>Open DSN-1</button>
    </div>
  ),
}));
vi.mock("./canvas-v2/C4DesignView", () => ({
  C4DesignView: ({ designId }: { designId: string | null }) => (
    <div>C4DesignView-stub designId={String(designId)}</div>
  ),
}));
vi.mock("./intake/IntakePage", () => ({
  default: ({ designId }: { designId: string | null; onNavigate: () => void; onDesignCreated?: (id: string) => void }) => (
    <div>IntakePage-stub designId={String(designId)}</div>
  ),
}));
vi.mock("./knowledge/KnowledgePage", () => ({
  default: () => <div>KnowledgePage-stub</div>,
}));
vi.mock("./portfolio/PortfolioPage", () => ({
  default: () => <div>PortfolioPage-stub</div>,
}));
vi.mock("./governance/GovernancePage", () => ({
  default: () => <div>GovernancePage-stub</div>,
}));
vi.mock("./business/BusinessPage", () => ({
  default: () => <div>BusinessPage-stub</div>,
}));
vi.mock("./application/ApplicationPage", () => ({
  default: () => <div>ApplicationPage-stub</div>,
}));
vi.mock("./application/TechCapPage", () => ({
  default: () => <div>TechCapPage-stub</div>,
}));
vi.mock("./diagrams/DiagramsPage", () => ({
  DiagramsPage: () => <div>DiagramsPage-stub</div>,
}));
vi.mock("./strategy/StrategyPage", () => ({
  default: () => <div>StrategyPage-stub</div>,
}));
vi.mock("./admin/AdminPage", () => ({
  default: () => <div>AdminPage-stub</div>,
}));

describe("App: onSelectDesign (regression -- opening a design lands on a populated Intake)", () => {
  it("selecting a design from Designs navigates to Intake with that designId", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Designs" }));
    expect(screen.getByText("DesignsPage-stub")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Open DSN-1" }));

    expect(screen.getByText(/IntakePage-stub designId=DSN-1/)).toBeTruthy();
    expect(screen.getByText("Design · DSN-1")).toBeTruthy();
  });
});

describe("App: onStartNewDesign (nav 'Intake' click == New Design)", () => {
  it("resets currentDesignId to null and shows a blank Intake, even with a design already selected", async () => {
    const user = userEvent.setup();
    render(<App />);

    // Get into a "design selected, viewing Intake" state first.
    await user.click(screen.getByRole("button", { name: "Designs" }));
    await user.click(screen.getByRole("button", { name: "Open DSN-1" }));
    expect(screen.getByText(/IntakePage-stub designId=DSN-1/)).toBeTruthy();

    // Clicking the nav bar's "Intake" (not "Open a design") resets to blank.
    await user.click(screen.getByRole("button", { name: "Intake" }));

    expect(screen.getByText(/IntakePage-stub designId=null/)).toBeTruthy();
    expect(screen.getByText("Design")).toBeTruthy();
    expect(screen.queryByText("Design · DSN-1")).toBeNull();
  });

  it("does not affect onSelectDesign's own onNavigate('intake') path (no regression)", async () => {
    const user = userEvent.setup();
    render(<App />);

    // Opening a design still lands on a populated Intake -- onStartNewDesign
    // is wired only to the nav bar's Intake button, not the generic
    // onNavigate("intake") used by onSelectDesign.
    await user.click(screen.getByRole("button", { name: "Designs" }));
    await user.click(screen.getByRole("button", { name: "Open DSN-1" }));

    expect(screen.getByText(/IntakePage-stub designId=DSN-1/)).toBeTruthy();
  });
});

describe("App: DESIGN_ONLY_VIEWS redirect (C4 Design with no design selected)", () => {
  it("redirects to Designs with a continueTo hint instead of rendering C4 Design directly", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "C4 Design" }));

    expect(screen.getByText("DesignsPage-stub")).toBeTruthy();
    expect(screen.getByText("continueTo:C4 Design")).toBeTruthy();
  });

  it("consumes the pending view once a design is picked -- lands directly on C4 Design, not Intake", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "C4 Design" }));
    await user.click(screen.getByRole("button", { name: "Open DSN-1" }));

    expect(screen.getByText(/C4DesignView-stub designId=DSN-1/)).toBeTruthy();
    expect(screen.queryByText(/IntakePage-stub/)).toBeNull();
  });

  it("Intake itself is never redirect-gated -- reachable directly with no design selected", async () => {
    const user = userEvent.setup();
    render(<App />);

    await user.click(screen.getByRole("button", { name: "Intake" }));

    expect(screen.getByText(/IntakePage-stub designId=null/)).toBeTruthy();
    expect(screen.queryByText("DesignsPage-stub")).toBeNull();
  });
});
