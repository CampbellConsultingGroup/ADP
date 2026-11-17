import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { resetPermissionsCache, useCan } from "./permissions";

function Probe({ action }: { action: string }) {
  const can = useCan(action);
  return <button disabled={!can.allowed} title={can.reason}>go</button>;
}

function respond(body: unknown, status = 200) {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify(body), { status })));
}

afterEach(() => {
  vi.unstubAllGlobals();
  resetPermissionsCache();
});

describe("useCan (ADP-blp.62)", () => {
  it("disables a control the role may not use, with the reason", async () => {
    respond({ role: "reviewer", actions: ["use_chat_assistant"] });
    render(<Probe action="write_business_arch" />);
    await waitFor(() => expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(true));
    expect(screen.getByRole("button").getAttribute("title")).toContain("Your role (reviewer) cannot do this");
  });

  it("leaves a granted action enabled", async () => {
    respond({ role: "solution_architect", actions: ["write_business_arch"] });
    render(<Probe action="write_business_arch" />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(false);
  });

  it("allows everything when permissions cannot be loaded (the server still enforces)", async () => {
    respond({ detail: "boom" }, 500);
    render(<Probe action="write_business_arch" />);
    await waitFor(() => expect(fetch).toHaveBeenCalled());
    expect((screen.getByRole("button") as HTMLButtonElement).disabled).toBe(false);
  });
});
