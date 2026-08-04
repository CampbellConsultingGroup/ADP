/** Component tests for PromptHistory (ADP-SPEC-042 US3). */

import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

import PromptHistory from "../../src/admin/PromptHistory";
import type { AgentPromptView, PromptHistoryResponse } from "../../src/api/adminPrompts";

import { mockFetch, renderWithQuery } from "./registry-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const AGENT: AgentPromptView = {
  agent_id: "intake_extraction", display_name: "Intake Extraction",
  active_text: "Second edit.", is_override: true, version: 2,
};

const HISTORY: PromptHistoryResponse = {
  items: [
    {
      id: 2, agent_id: "intake_extraction", actor: "bob",
      changed_at: "2026-07-25T12:00:00Z", change_type: "edit",
      prior_text: "First edit.", new_text: "Second edit.",
    },
    {
      id: 1, agent_id: "intake_extraction", actor: "alice",
      changed_at: "2026-07-25T10:00:00Z", change_type: "edit",
      prior_text: "Original.", new_text: "First edit.",
    },
  ],
};

describe("PromptHistory", () => {
  it("renders entries newest-first with attribution", async () => {
    mockFetch({ "GET /api/v1/admin/agent-prompts/intake_extraction/history": HISTORY });
    renderWithQuery(<PromptHistory agent={AGENT} />);

    const entries = await screen.findAllByText(/Edited by/);
    expect(entries).toHaveLength(2);
    expect(entries[0].textContent).toContain("bob");
    expect(entries[1].textContent).toContain("alice");
  });

  it("requires the same confirm dialog as edit before restoring (FR-008)", async () => {
    const calls = mockFetch({
      "GET /api/v1/admin/agent-prompts/intake_extraction/history": HISTORY,
      "POST /api/v1/admin/agent-prompts/intake_extraction/restore/1": {
        agent_id: "intake_extraction", active_text: "Original.", version: 3,
      },
    });
    renderWithQuery(<PromptHistory agent={AGENT} />);

    await screen.findAllByText(/Edited by/);
    const restoreButtons = screen.getAllByRole("button", { name: "Restore this version" });
    // Restore the OLDEST entry (alice's, id=1) — the second card rendered.
    fireEvent.click(restoreButtons[1]);

    // Clicking "Restore this version" must NOT call the API directly.
    const postCalls = () => calls.filter((c) => c.method === "POST");
    expect(postCalls().length).toBe(0);
    expect(screen.getByText(/changes.*live AI behavior/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Confirm & Restore" }));
    await waitFor(() => expect(postCalls().length).toBe(1));
    expect(postCalls()[0].url).toBe("/api/v1/admin/agent-prompts/intake_extraction/restore/1");
    expect(postCalls()[0].body).toMatchObject({ expected_version: 2 });
  });
});
