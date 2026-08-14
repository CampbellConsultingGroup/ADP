// 919-insights-dashboard (US3): confirms the new "Insights" nav entry lives in the
// general-audience PRIMARY group (sibling to Overview), not the architect-facing
// Architecture section. No AuthProvider/useTheme mocking needed -- AppShell's
// useAuth() falls back to its context default (user: null), which every render
// path here already handles gracefully, and useTheme()'s initial render only
// touches localStorage (jsdom-provided), never matchMedia (only on toggle click).

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { AppShell } from "./AppShell";

describe("AppShell (919-insights-dashboard nav placement)", () => {
  it("renders an Insights entry in the Workspace group, before the Architecture group", () => {
    render(
      <AppShell currentView="overview" onNavigate={vi.fn()}>
        <div />
      </AppShell>,
    );

    const insights = screen.getByText("Insights");
    const architectureLabel = screen.getByText("Architecture");
    // DOM order: Insights' position precedes the Architecture group label.
    expect(
      insights.compareDocumentPosition(architectureLabel) & Node.DOCUMENT_POSITION_FOLLOWING,
    ).toBeTruthy();
  });

  it("calls onNavigate('insights') when the Insights entry is clicked", async () => {
    const onNavigate = vi.fn();
    const user = userEvent.setup();
    render(
      <AppShell currentView="overview" onNavigate={onNavigate}>
        <div />
      </AppShell>,
    );

    await user.click(screen.getByText("Insights"));

    expect(onNavigate).toHaveBeenCalledWith("insights");
  });
});
