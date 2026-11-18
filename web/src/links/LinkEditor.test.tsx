// ADP-blp.65: the shared link editor disables its controls for a role that cannot link.
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as permissions from "../auth/permissions";
import LinkEditor from "./LinkEditor";

vi.mock("../auth/permissions");
const useCan = vi.mocked(permissions.useCan);

function editor(action?: string) {
  const mutation = { mutate: vi.fn(), isPending: false };
  return (
    <LinkEditor
      noun="capability"
      plural="capabilities"
      options={[{ id: "a", label: "Alpha" }, { id: "b", label: "Beta" }]}
      linkedIds={["a"]}
      link={mutation}
      unlink={mutation}
      action={action}
    />
  );
}

describe("LinkEditor permission", () => {
  beforeEach(() => useCan.mockReturnValue({ allowed: false, reason: "Your role (Reviewer) cannot do this." }));

  it("disables the picker and Remove, with the reason, when the action is not allowed", () => {
    render(editor("write_business_arch"));
    expect(useCan).toHaveBeenCalledWith("write_business_arch");
    const picker = screen.getByLabelText("Link a capability") as HTMLSelectElement;
    const remove = screen.getByRole("button", { name: "Remove" }) as HTMLButtonElement;
    expect(picker.disabled).toBe(true);
    expect(remove.disabled).toBe(true);
    expect(remove.title).toMatch(/Reviewer/);
    // What is linked stays readable.
    expect(screen.getByText("Alpha")).toBeTruthy();
  });

  it("stays editable when the caller names no action", () => {
    render(editor());
    expect((screen.getByLabelText("Link a capability") as HTMLSelectElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: "Remove" }) as HTMLButtonElement).disabled).toBe(false);
  });
});
