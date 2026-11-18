// ADP-blp.63: unsaved edits are known app-wide, and leaving asks first.
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { Tabs } from "./Tabs";
import { hasUnsavedChanges, leaveIfSafe, resetUnsavedChanges, useUnsavedChanges } from "./unsaved";

function Form() {
  const [dirty, setDirty] = useState(false);
  useUnsavedChanges(dirty);
  return <button onClick={() => setDirty((d) => !d)}>toggle dirty</button>;
}

afterEach(() => {
  resetUnsavedChanges();
  vi.restoreAllMocks();
});

describe("unsaved changes", () => {
  it("tracks a form while it is dirty and forgets it when it unmounts", async () => {
    const { unmount } = render(<Form />);
    expect(hasUnsavedChanges()).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "toggle dirty" }));
    expect(hasUnsavedChanges()).toBe(true);
    unmount();
    expect(hasUnsavedChanges()).toBe(false);
  });

  it("leaves at once when nothing is unsaved", () => {
    const leave = vi.fn();
    leaveIfSafe(leave);
    expect(leave).toHaveBeenCalledTimes(1);
  });

  it("asks before a tab change discards edits, and stays when the answer is no", async () => {
    // No ConfirmHost is mounted, so the prompt falls back to window.confirm.
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    const onChange = vi.fn();
    render(
      <>
        <Form />
        <Tabs label="Sections" active="a" onChange={onChange} tabs={[{ id: "a", label: "A" }, { id: "b", label: "B" }]} />
      </>,
    );
    await userEvent.click(screen.getByRole("button", { name: "toggle dirty" }));
    await userEvent.click(screen.getByRole("tab", { name: "B" }));
    expect(confirm).toHaveBeenCalledWith("Discard your unsaved changes?");
    expect(onChange).not.toHaveBeenCalled();

    confirm.mockReturnValue(true);
    await userEvent.click(screen.getByRole("tab", { name: "B" }));
    await vi.waitFor(() => expect(onChange).toHaveBeenCalledWith("b"));
  });

  it("warns on closing or reloading the page only while something is unsaved", async () => {
    render(<Form />);
    const fire = () => {
      const event = new Event("beforeunload", { cancelable: true });
      window.dispatchEvent(event);
      return event.defaultPrevented;
    };
    expect(fire()).toBe(false);
    await userEvent.click(screen.getByRole("button", { name: "toggle dirty" }));
    expect(fire()).toBe(true);
  });
});
