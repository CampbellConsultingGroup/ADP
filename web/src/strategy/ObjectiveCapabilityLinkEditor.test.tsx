// ADP-d8u.1 (T023): no existing DesignLinkEditor.tsx test file to mirror
// directly (confirmed absent during Setup); follows this codebase's
// general vi.mock(hooks-module) convention instead (web/src/chat/
// ChatPanel.test.tsx).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveCapabilityLinkEditor from "./ObjectiveCapabilityLinkEditor";
import * as strategyApi from "../api/strategy";
import * as businessApi from "../api/business";
import type { StrategicObjective } from "../api/strategy";

vi.mock("../api/strategy");
vi.mock("../api/business");

const mockedStrategyApi = vi.mocked(strategyApi);
const mockedBusinessApi = vi.mocked(businessApi);

const OBJECTIVE: StrategicObjective = {
  id: "obj-1",
  theme_id: "t1",
  owner: "Owner",
  statement: "Statement",
  metric_name: null,
  target_value: null,
  target_unit: null,
  direction: null,
  fiscal_year: 2026,
  period: "Q1",
  capability_ids: ["cap-1"],
  value_stream_ids: [],
  design_ids: [],
  application_ids: [],
  status: "proposed",
  status_reason: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedBusinessApi.useCapabilities.mockReturnValue({
    data: {
      items: [
        { id: "cap-1", name: "Claims Processing", level: 1 },
        { id: "cap-2", name: "Underwriting", level: 1 },
      ],
      total: 2,
    },
    isLoading: false,
  } as unknown as ReturnType<typeof businessApi.useCapabilities>);
  mockedStrategyApi.useLinkObjectiveCapability.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveCapability>);
  mockedStrategyApi.useUnlinkObjectiveCapability.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveCapability>);
});

describe("ObjectiveCapabilityLinkEditor", () => {
  it("lists currently-linked capabilities with a Remove action", () => {
    render(<ObjectiveCapabilityLinkEditor objective={OBJECTIVE} />);

    expect(screen.getByText("Claims Processing")).toBeTruthy();
    expect(screen.getByText("Remove")).toBeTruthy();
    // Underwriting is not linked, so it must not appear in the linked list
    // (it belongs only in the dropdown).
    expect(screen.queryAllByText("Underwriting")).toHaveLength(1);
  });

  it("offers a filtered dropdown excluding already-linked capabilities", () => {
    render(<ObjectiveCapabilityLinkEditor objective={OBJECTIVE} />);

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionLabels = Array.from(select.options).map((o) => o.textContent);
    expect(optionLabels).toContain("Underwriting");
    expect(optionLabels).not.toContain("Claims Processing");
  });

  it("calls the link hook with the selected capability id", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useLinkObjectiveCapability.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkObjectiveCapability>);

    const user = userEvent.setup();
    render(<ObjectiveCapabilityLinkEditor objective={OBJECTIVE} />);

    await user.selectOptions(screen.getByRole("combobox"), "cap-2");
    await user.click(screen.getByText("Link"));

    expect(mutate).toHaveBeenCalledWith("cap-2", expect.anything());
  });

  it("calls the unlink hook when Remove is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkObjectiveCapability.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkObjectiveCapability>);

    const user = userEvent.setup();
    render(<ObjectiveCapabilityLinkEditor objective={OBJECTIVE} />);

    await user.click(screen.getByText("Remove"));

    expect(mutate).toHaveBeenCalledWith("cap-1");
  });
});
