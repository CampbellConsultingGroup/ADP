// ADP-d8u.2: no existing CapabilityLinksEditor.test.tsx to mirror directly
// (confirmed absent) -- follows this codebase's general
// vi.mock(hooks-module) convention instead (web/src/strategy/
// ObjectiveCapabilityLinkEditor.test.tsx).

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveLinksPanel from "./ObjectiveLinksPanel";
import * as strategyApi from "../api/strategy";

vi.mock("../api/strategy");

const mockedStrategyApi = vi.mocked(strategyApi);

const ALL_OBJECTIVES = {
  items: [
    { id: "obj-1", theme_id: "t1", owner: "A", statement: "Reduce claims cycle time", fiscal_year: 2026, period: "Q3", status: "active", updated_at: "" },
    { id: "obj-2", theme_id: "t1", owner: "A", statement: "Expand digital channels", fiscal_year: 2026, period: "Q3", status: "proposed", updated_at: "" },
  ],
  total: 2,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedStrategyApi.useApplicationObjectives.mockReturnValue({
    data: { items: [ALL_OBJECTIVES.items[0]], total: 1 },
  } as unknown as ReturnType<typeof strategyApi.useApplicationObjectives>);
  mockedStrategyApi.useObjectives.mockReturnValue({
    data: ALL_OBJECTIVES,
  } as unknown as ReturnType<typeof strategyApi.useObjectives>);
  mockedStrategyApi.useLinkApplicationToObjective.mockReturnValue({
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useLinkApplicationToObjective>);
  mockedStrategyApi.useUnlinkApplicationFromObjective.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
  } as unknown as ReturnType<typeof strategyApi.useUnlinkApplicationFromObjective>);
});

describe("ObjectiveLinksPanel", () => {
  it("lists currently-linked objectives with a remove action", () => {
    render(<ObjectiveLinksPanel appId="app-1" />);

    expect(screen.getByText("Reduce claims cycle time")).toBeTruthy();
  });

  it("offers a filtered dropdown excluding already-linked objectives", () => {
    render(<ObjectiveLinksPanel appId="app-1" />);

    const select = screen.getByRole("combobox") as HTMLSelectElement;
    const optionLabels = Array.from(select.options).map((o) => o.textContent);
    expect(optionLabels).toContain("Expand digital channels");
    expect(optionLabels).not.toContain("Reduce claims cycle time");
  });

  it("calls the link mutation with the selected objective id", async () => {
    const mutateAsync = vi.fn(async () => ["app-1"]);
    mockedStrategyApi.useLinkApplicationToObjective.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useLinkApplicationToObjective>);

    const user = userEvent.setup();
    render(<ObjectiveLinksPanel appId="app-1" />);

    await user.selectOptions(screen.getByRole("combobox"), "obj-2");
    await user.click(screen.getByText("Link"));

    expect(mutateAsync).toHaveBeenCalledWith("obj-2");
  });

  it("calls the unlink mutation when the remove control is clicked", async () => {
    const mutate = vi.fn();
    mockedStrategyApi.useUnlinkApplicationFromObjective.mockReturnValue({
      mutate,
      isPending: false,
    } as unknown as ReturnType<typeof strategyApi.useUnlinkApplicationFromObjective>);

    const user = userEvent.setup();
    render(<ObjectiveLinksPanel appId="app-1" />);

    await user.click(screen.getByText("✕"));

    expect(mutate).toHaveBeenCalledWith("obj-1");
  });
});
