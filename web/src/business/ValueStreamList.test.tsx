// 918-strategy-rollups: mirrors this session's established vi.mock(hooks-module)
// convention (e.g. ThemeList.test.tsx).

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ValueStreamList from "./ValueStreamList";
import * as businessApi from "../api/business";
import type { ValueStream } from "../api/business";

vi.mock("../api/business");

const mockedBusinessApi = vi.mocked(businessApi);

function vs(partial: Partial<ValueStream> & { id: string; name: string }): ValueStream {
  return {
    description: null,
    stakeholder: null,
    position: 0,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...partial,
  };
}

const STREAMS: ValueStream[] = [
  vs({ id: "linked", name: "Linked VS" }),
  vs({ id: "orphan", name: "Orphan VS", position: 1 }),
];

beforeEach(() => {
  vi.clearAllMocks();
  mockedBusinessApi.useValueStreams.mockReturnValue({
    data: { items: STREAMS, total: 2 },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof businessApi.useValueStreams>);
  mockedBusinessApi.useOrphanReport.mockReturnValue({
    data: { orphan_capabilities: [], orphan_value_streams: [STREAMS[1]] },
  } as unknown as ReturnType<typeof businessApi.useOrphanReport>);
});

describe("ValueStreamList: orphan badge and filter (918-strategy-rollups)", () => {
  it("shows a 'no strategic linkage' badge only on the orphaned value stream", () => {
    render(<ValueStreamList onSelect={vi.fn()} />);

    expect(screen.getAllByText("no strategic linkage")).toHaveLength(1);
  });

  it("toggling 'Show orphans only' narrows the list to just orphaned value streams", async () => {
    const user = userEvent.setup();
    render(<ValueStreamList onSelect={vi.fn()} />);

    expect(screen.getByText("Linked VS")).toBeTruthy();
    expect(screen.getByText("Orphan VS")).toBeTruthy();

    await user.click(screen.getByText("Show orphans only"));

    expect(screen.queryByText("Linked VS")).toBeNull();
    expect(screen.getByText("Orphan VS")).toBeTruthy();
  });

  it("shows an empty state when the orphan filter matches nothing", async () => {
    mockedBusinessApi.useOrphanReport.mockReturnValue({
      data: { orphan_capabilities: [], orphan_value_streams: [] },
    } as unknown as ReturnType<typeof businessApi.useOrphanReport>);

    const user = userEvent.setup();
    render(<ValueStreamList onSelect={vi.fn()} />);

    await user.click(screen.getByText("Show orphans only"));

    expect(screen.getByText("No value streams with missing strategic linkage.")).toBeTruthy();
  });
});
