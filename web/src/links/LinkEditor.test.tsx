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

describe("LinkEditor with extra fields and a narrowing choice (ADP-blp.36)", () => {
  beforeEach(() => useCan.mockReturnValue({ allowed: true }));

  function withFields(validate: () => string | null, mutate = vi.fn()) {
    render(
      <LinkEditor
        title="Business Capabilities"
        noun="capability"
        plural="capabilities"
        options={[{ id: "a", label: "Alpha" }, { id: "b", label: "Beta" }]}
        linkedIds={[]}
        link={{ mutate, isPending: false }}
        unlink={{ mutate: vi.fn(), isPending: false }}
        addFields={<input aria-label="Fit score" defaultValue="3" />}
        validate={validate}
      />,
    );
    return mutate;
  }

  it("waits for the Link button when the link has fields of its own", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const mutate = withFields(() => null);
    expect(screen.getByRole("heading", { name: "Business Capabilities" })).toBeTruthy();
    const linkButton = screen.getByRole("button", { name: "Link" }) as HTMLButtonElement;
    expect(linkButton.disabled).toBe(true);

    await userEvent.selectOptions(screen.getByLabelText("Link a capability"), "b");
    expect(mutate).not.toHaveBeenCalled(); // choosing alone does not save
    await userEvent.click(linkButton);
    expect(mutate.mock.calls[0][0]).toBe("b");
  });

  it("shows the caller's validation message instead of linking", async () => {
    const { default: userEvent } = await import("@testing-library/user-event");
    const mutate = withFields(() => "Fit score must be 1–5");
    await userEvent.selectOptions(screen.getByLabelText("Link a capability"), "a");
    await userEvent.click(screen.getByRole("button", { name: "Link" }));
    expect(screen.getByText("Fit score must be 1–5")).toBeTruthy();
    expect(mutate).not.toHaveBeenCalled();
  });

  it("hides the picker until the narrowing choice is made, and shows the hint", () => {
    render(
      <LinkEditor
        noun="stage"
        plural="stages"
        pickerLabel="Stage"
        hidePicker
        pickerPrefix={<select aria-label="Value stream" />}
        hint="This value stream has no stages yet."
        options={[]}
        linkedIds={[]}
        link={{ mutate: vi.fn(), isPending: false }}
        unlink={{ mutate: vi.fn(), isPending: false }}
      />,
    );
    expect(screen.getByLabelText("Value stream")).toBeTruthy();
    expect(screen.queryByLabelText("Stage")).toBeNull();
    expect(screen.getByText("This value stream has no stages yet.")).toBeTruthy();
  });
});
