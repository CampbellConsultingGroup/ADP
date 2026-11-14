// 935-pattern-registry US2: LifecycleDialog + History component tests.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as patternsApi from "../api/patterns";
import { ApiError } from "../api/client";
import * as auth from "../auth/AuthProvider";
import History from "./History";
import LifecycleDialog from "./LifecycleDialog";
import { detail, mutation } from "./testFixtures";

vi.mock("../api/patterns", async (orig) => {
  const actual = await orig<typeof import("../api/patterns")>();
  return { ...actual, useTransition: vi.fn() };
});
vi.mock("../auth/AuthProvider", () => ({ useAuth: vi.fn() }));

const api = vi.mocked(patternsApi);
const useAuth = vi.mocked(auth.useAuth);

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({ user: { role: "enterprise_architect" } } as never);
  api.useTransition.mockReturnValue(mutation());
});

describe("LifecycleDialog", () => {
  it("offers only the allowed transitions", () => {
    render(<LifecycleDialog detail={detail({ lifecycle: "proposed", allowed_transitions: ["draft", "current"] })} />);
    expect(screen.getByRole("button", { name: "Return to draft" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Promote to current" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Deprecate" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Propose" })).toBeNull();
  });

  it("needs a reason and the confirmation before submitting, then sends a confirmation id", async () => {
    const mutateAsync = vi.fn().mockResolvedValue(detail());
    api.useTransition.mockReturnValue(mutation(mutateAsync));
    render(<LifecycleDialog detail={detail()} />);
    await userEvent.click(screen.getByRole("button", { name: "Propose" }));
    const dialog = screen.getByRole("dialog");
    const submit = within(dialog).getByRole("button", { name: "Propose" }) as HTMLButtonElement;
    expect(submit.disabled).toBe(true);
    await userEvent.type(within(dialog).getByLabelText("Reason"), "Ready for ARB");
    expect(submit.disabled).toBe(true);
    await userEvent.click(within(dialog).getByRole("checkbox"));
    expect(submit.disabled).toBe(false);
    await userEvent.click(submit);
    expect(mutateAsync).toHaveBeenCalledTimes(1);
    const req = mutateAsync.mock.calls[0][0];
    expect(req.to).toBe("proposed");
    expect(req.reason).toBe("Ready for ARB");
    expect(typeof req.confirmation_id).toBe("string");
    expect(req.confirmation_id.length).toBeGreaterThan(0);
    expect(screen.queryByRole("dialog")).toBeNull();
  });

  it("shows the issues of a blocked promotion", async () => {
    const issues = [{ path: "motivation.principles[0]", code: "R1.unresolved_principle", message: "principle 'X' does not exist", severity: "error" }];
    const err = new ApiError(422, "POST failed: 422", { detail: { message: "promotion blocked by 1 issue(s)", issues } });
    api.useTransition.mockReturnValue(mutation(vi.fn().mockRejectedValue(err)));
    render(<LifecycleDialog detail={detail({ lifecycle: "proposed", allowed_transitions: ["draft", "current"] })} />);
    await userEvent.click(screen.getByRole("button", { name: "Promote to current" }));
    const dialog = screen.getByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Reason"), "Go");
    await userEvent.click(within(dialog).getByRole("checkbox"));
    await userEvent.click(within(dialog).getByRole("button", { name: "Promote to current" }));
    const region = await screen.findByRole("region", { name: "Promotion blocked" });
    expect(within(region).getByText("R1.unresolved_principle")).toBeTruthy();
    expect(screen.getByRole("dialog")).toBeTruthy();
  });

  it("is hidden for roles that cannot govern patterns", () => {
    useAuth.mockReturnValue({ user: { role: "solution_architect" } } as never);
    const { container } = render(<LifecycleDialog detail={detail()} />);
    expect(container.textContent).toBe("");
  });

  it("renders nothing for a terminal version", () => {
    const { container } = render(<LifecycleDialog detail={detail({ lifecycle: "decommissioned", allowed_transitions: [] })} />);
    expect(container.textContent).toBe("");
  });
});

describe("History", () => {
  it("lists events and marks automatic demotions", () => {
    render(
      <History
        events={[
          { id: "e1", from_state: "proposed", to_state: "current", reason: "ARB ok", confirmation_id: "c-1", actor: "ea", at: "2026-11-14T10:00:00Z", caused_by_event_id: null },
          { id: "e2", from_state: "current", to_state: "deprecated", reason: "Superseded by 1.1.0: x", confirmation_id: "c-2", actor: "ea", at: "2026-11-14T11:00:00Z", caused_by_event_id: "e9" },
        ]}
      />,
    );
    const table = screen.getByRole("table", { name: "Lifecycle history" });
    expect(within(table).getByText("ARB ok")).toBeTruthy();
    expect(within(table).getByText(/Current → Deprecated \(automatic, superseded\)/)).toBeTruthy();
  });
});
