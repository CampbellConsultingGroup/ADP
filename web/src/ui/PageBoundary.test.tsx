import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider, useSuspenseQuery } from "@tanstack/react-query";
import { PageBoundary } from "./PageBoundary";

function Page({ fetcher }: { fetcher: () => Promise<string> }) {
  const { data } = useSuspenseQuery({ queryKey: ["page"], queryFn: fetcher, retry: false });
  return <div>page: {data}</div>;
}

function renderInShell(fetcher: () => Promise<string>) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>
      <nav>navigation</nav>
      <PageBoundary>
        <Page fetcher={fetcher} />
      </PageBoundary>
    </QueryClientProvider>,
  );
}

describe("PageBoundary (ADP-blp.30)", () => {
  it("shows a loading state while a suspense query is pending", async () => {
    renderInShell(() => Promise.resolve("ready"));
    expect(screen.getByRole("status").textContent).toContain("Loading");
    expect(await screen.findByText("page: ready")).toBeTruthy();
  });

  it("keeps the shell when the page fails, and retries without a reload", async () => {
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => {});
    const fetcher = vi
      .fn<() => Promise<string>>()
      .mockRejectedValueOnce(new Error("GET /api/v1/applications failed: 500"))
      .mockResolvedValue("ready");
    renderInShell(fetcher);

    expect((await screen.findByRole("alert")).textContent).toContain("This page couldn't load");
    expect(screen.getByText("GET /api/v1/applications failed: 500")).toBeTruthy();
    // The navigation outside the boundary is still there.
    expect(screen.getByText("navigation")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("page: ready")).toBeTruthy();
    expect(fetcher).toHaveBeenCalledTimes(2);
    consoleError.mockRestore();
  });
});
