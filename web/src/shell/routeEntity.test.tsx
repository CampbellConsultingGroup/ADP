// ADP-blp.57 / ADP-blp.68: the open entity lives in the URL and the page follows it.
import { beforeEach, describe, expect, it } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { goToEntity, openEntity, useRouteEntity } from "./routing";

function Probe({ initial = null }: { initial?: string | null }) {
  const [id, setId] = useRouteEntity("application", initial);
  return (
    <div>
      <span data-testid="id">{id ?? "none"}</span>
      <button onClick={() => setId("b")}>pick b</button>
      <button onClick={() => setId(null)}>close</button>
    </div>
  );
}

const shown = () => screen.getByTestId("id").textContent;

describe("useRouteEntity", () => {
  beforeEach(() => window.history.replaceState(null, "", "#/applications/a?tab=registry"));

  it("starts from the URL, and a selection becomes a history entry that keeps the page's parameters", async () => {
    const before = window.history.length;
    render(<Probe />);
    expect(shown()).toBe("a");
    await userEvent.click(screen.getByRole("button", { name: "pick b" }));
    expect(shown()).toBe("b");
    expect(window.location.hash).toBe("#/applications/b?tab=registry");
    expect(window.history.length).toBe(before + 1);
    await userEvent.click(screen.getByRole("button", { name: "close" }));
    expect(window.location.hash).toBe("#/applications?tab=registry");
  });

  it("follows the browser's Back and a link followed elsewhere on the page", () => {
    render(<Probe />);
    act(() => {
      window.history.replaceState(null, "", "#/applications/z");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(shown()).toBe("z");
    act(() => openEntity("application", "y"));
    expect(shown()).toBe("y");
  });

  it("shows nothing of its kind when another kind is open on the same screen", () => {
    window.history.replaceState(null, "", "#/applications/capabilities/c1");
    render(<Probe />);
    expect(shown()).toBe("none");
    // Closing "the application" must not close the capability that is open instead.
    act(() => openEntity("application", null));
    expect(window.location.hash).toBe("#/applications/capabilities/c1");
  });

  it("uses the initial value and leaves the URL alone when there is no route (outside the shell)", async () => {
    window.history.replaceState(null, "", "#");
    render(<Probe initial="seed" />);
    expect(shown()).toBe("seed");
    await userEvent.click(screen.getByRole("button", { name: "pick b" }));
    expect(shown()).toBe("b");
    expect(window.location.hash).toBe("");
  });
});

describe("goToEntity / openEntity across screens", () => {
  it("navigates to the entity's own screen", () => {
    window.history.replaceState(null, "", "#/governance?tab=health");
    goToEntity("business_capability", "b1");
    expect(window.location.hash).toBe("#/business/b1");
    openEntity("agent", "ag");
    expect(window.location.hash).toBe("#/agents/ag");
  });
});
