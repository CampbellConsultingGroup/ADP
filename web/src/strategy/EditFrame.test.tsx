// ADP-q3j / ADP-a8s: the shared Strategy edit frame.
import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EditFrame, { DISCARD_PROMPT } from "./EditFrame";

function setup(props: Partial<React.ComponentProps<typeof EditFrame>> = {}) {
  const onClose = vi.fn();
  const onSubmit = vi.fn((e: React.FormEvent) => e.preventDefault());
  render(
    <EditFrame
      title="Edit initiative"
      subject="Claims Automation"
      backLabel="Back to initiatives"
      dirty={false}
      saving={false}
      onSubmit={onSubmit}
      onClose={onClose}
      after={<p>Linked things</p>}
      {...props}
    >
      <label>
        Name
        <input defaultValue="x" />
      </label>
    </EditFrame>,
  );
  return { onClose, onSubmit, user: userEvent.setup() };
}

afterEach(() => vi.restoreAllMocks());

describe("EditFrame", () => {
  it("names the item in a focused heading and labels the form with it", () => {
    setup();
    const heading = screen.getByRole("heading", { name: /Edit initiative: Claims Automation/ });
    expect(document.activeElement).toBe(heading);
    expect(screen.getByRole("form", { name: /Edit initiative/ })).toBeTruthy();
    expect(screen.getByText("Linked things")).toBeTruthy();
  });

  it("has a styled primary Save and a Cancel", async () => {
    const { onSubmit, user } = setup();
    const save = screen.getByRole("button", { name: "Save" });
    expect(save.className).toContain("ui-btn-primary");
    await user.click(save);
    expect(onSubmit).toHaveBeenCalled();
  });

  it("closes from Back, Cancel and Escape without asking when nothing changed", async () => {
    const confirmSpy = vi.spyOn(window, "confirm");
    const { onClose, user } = setup();
    await user.click(screen.getByRole("button", { name: /Back to initiatives/ }));
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    await user.click(screen.getByRole("textbox"));
    await user.keyboard("{Escape}");
    expect(onClose).toHaveBeenCalledTimes(3);
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("asks before discarding unsaved changes, and stays open when declined", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const { onClose, user } = setup({ dirty: true });
    expect(screen.getByText("Unsaved changes")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: /Back to initiatives/ }));
    expect(confirmSpy).toHaveBeenCalledWith(DISCARD_PROMPT);
    expect(onClose).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("shows Saving… and disables Save while saving or when saveDisabled", () => {
    setup({ saving: true });
    expect((screen.getByRole("button", { name: "Saving…" }) as HTMLButtonElement).disabled).toBe(true);
  });
});
