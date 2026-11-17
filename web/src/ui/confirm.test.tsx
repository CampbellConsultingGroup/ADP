import { afterEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { ConfirmHost, confirmAction } from "./confirm";

afterEach(() => vi.restoreAllMocks());

describe("confirmAction (ADP-blp.47)", () => {
  it("falls back to the browser's confirm when no host is mounted", async () => {
    const native = vi.spyOn(window, "confirm").mockReturnValue(true);
    expect(await confirmAction('Delete "X"?')).toBe(true);
    expect(native).toHaveBeenCalledWith('Delete "X"?');
  });

  it("shows a themed dialog and resolves with the user's answer", async () => {
    const native = vi.spyOn(window, "confirm");
    render(<ConfirmHost />);

    let answer: Promise<boolean>;
    act(() => {
      answer = confirmAction('Delete theme "Growth"?');
    });
    const dialog = screen.getByRole("dialog", { name: "Confirm" });
    expect(dialog.textContent).toContain('Delete theme "Growth"?');
    // The button is named after the action and styled as destructive.
    const confirm = screen.getByRole("button", { name: "Delete" });
    expect(confirm.className).toContain("ui-btn-danger");
    fireEvent.click(confirm);
    expect(await answer!).toBe(true);
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(native).not.toHaveBeenCalled();
  });

  it("Cancel and Escape both answer no", async () => {
    render(<ConfirmHost />);
    let first: Promise<boolean>;
    act(() => {
      first = confirmAction('Remove "EMEA"? Org units lose that link.');
    });
    expect(screen.getByRole("button", { name: "Remove" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(await first!).toBe(false);

    let second: Promise<boolean>;
    act(() => {
      second = confirmAction("You have unsaved changes.", { confirmLabel: "Discard" });
    });
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(await second!).toBe(false);
  });
});
