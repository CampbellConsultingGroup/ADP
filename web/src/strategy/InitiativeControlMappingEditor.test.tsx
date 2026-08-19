// 925-strategy-compliance-linkage (COMPLY-05). Mirrors InitiativeObjectiveLinkEditor.test.tsx's
// vi.mock(hooks-module) convention, adapted for the control_id/target_type/target_id input trio
// and the live-status badge (research.md D3 -- the badge's value is whatever the mocked
// initiative prop's control_mappings entry carries, exercising the "read live off the ref" shape
// without needing a real backend round-trip).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import InitiativeControlMappingEditor from "./InitiativeControlMappingEditor";
import * as strategyApi from "../api/strategy";
import type { StrategyInitiative } from "../api/strategy";

vi.mock("../api/strategy");

const mockedStrategyApi = vi.mocked(strategyApi);

const INITIATIVE: StrategyInitiative = {
  id: "init-1",
  name: "Remediate MFA gap",
  description: null,
  owner: null,
  status: "planned",
  objective_ids: [],
  control_mappings: [
    {
      control_id: "CTRL-1",
      target_type: "application",
      target_id: "APP-1",
      compliance_status: "non_compliant",
      evidence_ref: null,
      assessed_at: null,
    },
  ],
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useLinkInitiativeControlMapping.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeControlMapping>);
  mockedStrategyApi.useUnlinkInitiativeControlMapping.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkInitiativeControlMapping>);
});

describe("InitiativeControlMappingEditor", () => {
  it("lists a linked control mapping with its live status", () => {
    render(<InitiativeControlMappingEditor initiative={INITIATIVE} />);

    expect(screen.getByText("CTRL-1 → Application: APP-1")).toBeTruthy();
    expect(screen.getByText("Non-compliant")).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
  });

  it("shows 'No compliance gaps linked yet' when there are none", () => {
    render(<InitiativeControlMappingEditor initiative={{ ...INITIATIVE, control_mappings: [] }} />);

    expect(screen.getByText("No compliance gaps linked yet.")).toBeTruthy();
  });

  it("hides the target-id input for the organization target type", async () => {
    const user = userEvent.setup();
    render(<InitiativeControlMappingEditor initiative={{ ...INITIATIVE, control_mappings: [] }} />);

    expect(screen.getByPlaceholderText("Application id")).toBeTruthy();
    await user.selectOptions(screen.getByRole("combobox"), "organization");
    expect(screen.queryByPlaceholderText("Application id")).toBeNull();
    expect(screen.queryByPlaceholderText("Estate-wide (organization) id")).toBeNull();
    // The control-id input is unaffected -- only the target-id input disappears.
    expect(screen.getByPlaceholderText("Control id")).toBeTruthy();
  });

  it("calls the link hook with control id, target type, and target id", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkInitiativeControlMapping.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeControlMapping>);

    const user = userEvent.setup();
    render(<InitiativeControlMappingEditor initiative={{ ...INITIATIVE, control_mappings: [] }} />);

    await user.type(screen.getByPlaceholderText("Control id"), "CTRL-2");
    await user.type(screen.getByPlaceholderText("Application id"), "APP-2");
    await user.click(screen.getByText("Link"));

    expect(mutate).toHaveBeenCalledWith(
      { controlId: "CTRL-2", targetType: "application", targetId: "APP-2" },
      expect.anything(),
    );
  });

  it("calls the unlink hook when Remove is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkInitiativeControlMapping.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkInitiativeControlMapping>);

    const user = userEvent.setup();
    render(<InitiativeControlMappingEditor initiative={INITIATIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(mutate).toHaveBeenCalledWith(
      { controlId: "CTRL-1", targetType: "application", targetId: "APP-1" },
      expect.anything(),
    );
  });

  it("surfaces a 404 as a not-yet-assessed message", async () => {
    const mutate = vi.fn((_args, opts) => opts?.onError?.({ message: "not found", status: 404 }));
    mockedStrategyApi.useLinkInitiativeControlMapping.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeControlMapping>);

    const user = userEvent.setup();
    render(<InitiativeControlMappingEditor initiative={{ ...INITIATIVE, control_mappings: [] }} />);

    await user.type(screen.getByPlaceholderText("Control id"), "CTRL-2");
    await user.type(screen.getByPlaceholderText("Application id"), "APP-2");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText(/No assessed mapping exists yet/)).toBeTruthy();
  });

  it("surfaces a 409 as 'Already linked'", async () => {
    const mutate = vi.fn((_args, opts) => opts?.onError?.({ message: "conflict", status: 409 }));
    mockedStrategyApi.useLinkInitiativeControlMapping.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeControlMapping>);

    const user = userEvent.setup();
    render(<InitiativeControlMappingEditor initiative={{ ...INITIATIVE, control_mappings: [] }} />);

    await user.type(screen.getByPlaceholderText("Control id"), "CTRL-1");
    await user.type(screen.getByPlaceholderText("Application id"), "APP-1");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText("Already linked")).toBeTruthy();
  });

  it("shows a confirmation once linking succeeds", async () => {
    const mutate = vi.fn((_args, opts) => opts?.onSuccess?.());
    mockedStrategyApi.useLinkInitiativeControlMapping.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkInitiativeControlMapping>);

    const user = userEvent.setup();
    render(<InitiativeControlMappingEditor initiative={{ ...INITIATIVE, control_mappings: [] }} />);

    await user.type(screen.getByPlaceholderText("Control id"), "CTRL-2");
    await user.type(screen.getByPlaceholderText("Application id"), "APP-2");
    await user.click(screen.getByText("Link"));

    expect(screen.getByText(/Linked "Application compliance gap"/)).toBeTruthy();
  });
});
