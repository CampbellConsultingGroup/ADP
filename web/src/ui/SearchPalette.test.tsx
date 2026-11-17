import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { SearchLauncher } from "./SearchPalette";

const HITS = [
  { entity_type: "business_capability", entity_id: "c1", text: "Accept Payment", score: 0.9 },
  { entity_type: "application", entity_id: "a1", text: "Adyen Payments\nGateway", score: 0.8 },
];

function setup(onOpenResult = vi.fn()) {
  const fetchMock = vi.fn().mockImplementation(() =>
    Promise.resolve(new Response(JSON.stringify({ query: "pay", hits: HITS }), { status: 200 })),
  );
  vi.stubGlobal("fetch", fetchMock);
  render(
    <QueryClientProvider client={new QueryClient()}>
      <SearchLauncher onOpenResult={onOpenResult} />
    </QueryClientProvider>,
  );
  return { fetchMock, onOpenResult };
}

afterEach(() => vi.unstubAllGlobals());

describe("global search (ADP-blp.56)", () => {
  it("opens from the button and from Ctrl+K, and closes on Escape", () => {
    setup();
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    expect(screen.getByRole("dialog", { name: "Search" })).toBeTruthy();
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(screen.queryByRole("dialog")).toBeNull();
    fireEvent.keyDown(window, { key: "k", ctrlKey: true });
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("searches after two characters and opens the chosen result with the keyboard", async () => {
    const { fetchMock, onOpenResult } = setup();
    fireEvent.click(screen.getByRole("button", { name: "Search" }));
    const input = screen.getByRole("combobox");
    fireEvent.change(input, { target: { value: "p" } });
    expect(screen.getByRole("status").textContent).toContain("at least two characters");
    fireEvent.change(input, { target: { value: "pay" } });
    await waitFor(() => expect(screen.getAllByRole("option")).toHaveLength(2));
    expect(fetchMock.mock.calls[0][0]).toContain("/api/v1/search?q=pay");
    expect(screen.getByText("Business capability")).toBeTruthy();
    expect(screen.getByText("Adyen Payments")).toBeTruthy(); // first line only

    fireEvent.keyDown(input, { key: "ArrowDown" });
    fireEvent.keyDown(input, { key: "Enter" });
    expect(onOpenResult).toHaveBeenCalledWith(HITS[1]);
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});
