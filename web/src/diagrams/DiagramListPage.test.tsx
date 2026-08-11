import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiagramListPage } from "./DiagramListPage";
import * as api from "./api";
import type { DiagramSummary } from "./api";

vi.mock("./api");

const mockedApi = vi.mocked(api);

const ITEMS: DiagramSummary[] = [
  { id: "d-1", title: "Claims Flow", diagram_type: "flowchart", updated_at: "2026-08-06T00:00:00Z" },
  { id: "d-2", title: "Order Sequence", diagram_type: "sequence", updated_at: "2026-08-06T01:00:00Z" },
  { id: "d-3", title: "Data Model", diagram_type: "erd", updated_at: "2026-08-06T02:00:00Z" },
];

beforeEach(() => {
  vi.clearAllMocks();
});

describe("DiagramListPage: browse (User Story 3)", () => {
  it("renders items across every diagram type", async () => {
    mockedApi.listDiagrams.mockResolvedValue({ items: ITEMS, total: 3 });

    render(<DiagramListPage onOpen={vi.fn()} />);

    // getByText/findByText already throw if the element isn't found -- that
    // IS the assertion; no jest-dom matcher needed (not a project dependency).
    await screen.findByText("Claims Flow");
    screen.getByText("Order Sequence");
    screen.getByText("Data Model");
    screen.getByText("flowchart");
    screen.getByText("sequence");
    screen.getByText("erd");
  });

  it("calls onOpen with the diagram id when a title is clicked", async () => {
    mockedApi.listDiagrams.mockResolvedValue({ items: ITEMS, total: 3 });
    const onOpen = vi.fn();
    const user = userEvent.setup();

    render(<DiagramListPage onOpen={onOpen} />);
    await user.click(await screen.findByText("Claims Flow"));

    expect(onOpen).toHaveBeenCalledWith("d-1");
  });

  it("removes a deleted item from the list", async () => {
    mockedApi.listDiagrams
      .mockResolvedValueOnce({ items: ITEMS, total: 3 })
      .mockResolvedValueOnce({ items: ITEMS.slice(1), total: 2 });
    mockedApi.deleteDiagram.mockResolvedValue(undefined);
    const user = userEvent.setup();

    render(<DiagramListPage onOpen={vi.fn()} />);
    await screen.findByText("Claims Flow");

    await user.click(screen.getByLabelText("Delete Claims Flow"));

    await waitFor(() => expect(mockedApi.deleteDiagram).toHaveBeenCalledWith("d-1"));
    await waitFor(() => expect(screen.queryByText("Claims Flow")).toBeNull());
  });

  it("shows an empty state with no diagrams", async () => {
    mockedApi.listDiagrams.mockResolvedValue({ items: [], total: 0 });

    render(<DiagramListPage onOpen={vi.fn()} />);

    await screen.findByText("No diagrams yet.");
  });
});
