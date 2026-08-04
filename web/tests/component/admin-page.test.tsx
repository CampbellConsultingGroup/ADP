/** Component tests for the Admin Agent Prompt Management page (ADP-SPEC-042 US1). */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, fireEvent, cleanup, within } from "@testing-library/react";

import AdminPage from "../../src/admin/AdminPage";
import { AppShell } from "../../src/ui";
import type { AgentPromptListResponse } from "../../src/api/adminPrompts";

import { mockFetch, renderWithQuery } from "./registry-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const LIST_RESPONSE: AgentPromptListResponse = {
  items: [
    { agent_id: "chat_assistant", display_name: "Chat Assistant", active_text: "You are helpful.", is_override: false, version: 0 },
    { agent_id: "recommendation_generation", display_name: "Recommendation — Generation", active_text: "Custom generation text.", is_override: true, version: 2 },
    { agent_id: "recommendation_generation_no_kb", display_name: "Recommendation — Generation (no knowledge base)", active_text: "No-KB text.", is_override: false, version: 0 },
    { agent_id: "recommendation_tradeoff", display_name: "Recommendation — Trade-off Analysis", active_text: "Tradeoff text.", is_override: false, version: 0 },
    { agent_id: "intake_extraction", display_name: "Intake Extraction", active_text: "Extraction text.", is_override: false, version: 0 },
    { agent_id: "agent_review_business_capability", display_name: "Agent Review — Business Capability", active_text: "Review text.", is_override: false, version: 0 },
  ],
};

describe("AdminPage", () => {
  it("renders all 6 agents with correct Default/Custom labeling (FR-001, FR-002)", async () => {
    mockFetch({ "GET /api/v1/admin/agent-prompts": LIST_RESPONSE });
    renderWithQuery(<AdminPage />);

    for (const item of LIST_RESPONSE.items) {
      expect(await screen.findByText(item.display_name)).toBeTruthy();
    }

    // Exactly one override among the six -> one "Custom", five "Default".
    expect(screen.getAllByText("Custom")).toHaveLength(1);
    expect(screen.getAllByText("Default")).toHaveLength(5);
  });

  it("shows the full prompt text and override badge when an agent is selected", async () => {
    mockFetch({ "GET /api/v1/admin/agent-prompts": LIST_RESPONSE });
    renderWithQuery(<AdminPage />);

    const custom = await screen.findByText("Recommendation — Generation");
    fireEvent.click(custom.closest("div")!.parentElement!);

    expect(await screen.findByDisplayValue("Custom generation text.")).toBeTruthy();
    expect(screen.getByText("Custom (saved override)")).toBeTruthy();
  });
});

describe("AppShell admin nav gating (FR-009)", () => {
  it("hides the Administration nav group by default (no signed-in user)", () => {
    render(
      <AppShell currentView="overview" onNavigate={vi.fn()} designId={null}>
        <div />
      </AppShell>,
    );
    const rail = document.querySelector("nav.shell-rail") as HTMLElement;
    expect(within(rail).queryByText("Administration")).toBeNull();
    expect(within(rail).queryByText("Agent Prompts")).toBeNull();
  });

  it("shows the Administration nav group for a platform_admin user", async () => {
    vi.resetModules();
    vi.doMock("../../src/auth/AuthProvider", async () => {
      const actual = await vi.importActual<typeof import("../../src/auth/AuthProvider")>(
        "../../src/auth/AuthProvider",
      );
      return {
        ...actual,
        useAuth: () => ({
          user: {
            username: "admin", email: "admin@localhost", role: "platform_admin",
            roleLabel: "Platform Admin", roleColors: { bg: "#FEF3C7", text: "#92400E" }, groups: [],
          },
          isLoading: false,
          logout: vi.fn(),
        }),
      };
    });
    const { AppShell: MockedAppShell } = await import("../../src/ui");
    render(
      <MockedAppShell currentView="overview" onNavigate={vi.fn()} designId={null}>
        <div />
      </MockedAppShell>,
    );
    const rail = document.querySelector("nav.shell-rail") as HTMLElement;
    expect(within(rail).getByText("Administration")).toBeTruthy();
    expect(within(rail).getByText("Agent Prompts")).toBeTruthy();
    vi.doUnmock("../../src/auth/AuthProvider");
    vi.resetModules();
  });
});
