/** Component tests for PromptEditor (ADP-SPEC-042 US2). */

import { describe, it, expect, vi, afterEach } from "vitest";
import { screen, fireEvent, waitFor, cleanup } from "@testing-library/react";

import PromptEditor from "../../src/admin/PromptEditor";
import type { AgentPromptView } from "../../src/api/adminPrompts";

import { mockFetch, renderWithQuery } from "./registry-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const AGENT: AgentPromptView = {
  agent_id: "chat_assistant", display_name: "Chat Assistant",
  active_text: "Original text.", is_override: false, version: 0,
};

describe("PromptEditor", () => {
  it("disables Save until the text is actually edited", () => {
    renderWithQuery(<PromptEditor agent={AGENT} onDirtyChange={vi.fn()} />);
    const save = screen.getByRole("button", { name: "Save" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);

    fireEvent.change(screen.getByDisplayValue("Original text."), { target: { value: "Edited text." } });
    expect(save.disabled).toBe(false);
  });

  it("rejects empty/whitespace text client-side (FR-004)", () => {
    renderWithQuery(<PromptEditor agent={AGENT} onDirtyChange={vi.fn()} />);
    fireEvent.change(screen.getByDisplayValue("Original text."), { target: { value: "   " } });
    const save = screen.getByRole("button", { name: "Save" }) as HTMLButtonElement;
    expect(save.disabled).toBe(true);
    expect(screen.getByText("Prompt cannot be empty.")).toBeTruthy();
  });

  it("requires the confirm dialog before actually saving (FR-010)", async () => {
    const calls = mockFetch({
      "POST /api/v1/admin/agent-prompts/chat_assistant/confirm": {
        agent_id: "chat_assistant", active_text: "Edited text.", version: 1,
      },
    });
    renderWithQuery(<PromptEditor agent={AGENT} onDirtyChange={vi.fn()} />);

    fireEvent.change(screen.getByDisplayValue("Original text."), { target: { value: "Edited text." } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));

    // The mutation must NOT fire just from clicking Save -- only from
    // confirming the dialog that appears.
    expect(calls.length).toBe(0);
    expect(screen.getByText(/changes.*live AI behavior/i)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Confirm & Save" }));
    await waitFor(() => expect(calls.length).toBe(1));
    expect(calls[0].body).toMatchObject({ new_text: "Edited text.", expected_version: 0 });
  });

  it("shows the newer text on a 409 conflict instead of overwriting it (FR-012)", async () => {
    mockFetch({
      "POST /api/v1/admin/agent-prompts/chat_assistant/confirm": [
        409,
        {
          detail: {
            detail: "The prompt changed since you loaded it.",
            current_active_text: "Someone else's newer edit.",
            current_version: 5,
          },
        },
      ],
    });
    renderWithQuery(<PromptEditor agent={AGENT} onDirtyChange={vi.fn()} />);

    fireEvent.change(screen.getByDisplayValue("Original text."), { target: { value: "My edit." } });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    fireEvent.click(screen.getByRole("button", { name: "Confirm & Save" }));

    expect(await screen.findByText(/changed since you loaded it/i)).toBeTruthy();
    // The admin's own edit is NOT silently discarded by being overwritten --
    // it's still visible until they explicitly choose to load the latest.
    expect(screen.getByDisplayValue("My edit.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Load latest version" }));
    expect(screen.getByDisplayValue("Someone else's newer edit.")).toBeTruthy();
  });
});
