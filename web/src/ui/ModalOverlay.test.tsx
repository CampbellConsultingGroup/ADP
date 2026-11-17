import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ModalOverlay } from "./ModalOverlay";
import { clickableRow } from "./clickableRow";

describe("ModalOverlay (ADP-blp.40)", () => {
  it("is announced as a modal dialog and takes focus", () => {
    render(
      <ModalOverlay label="Confirm restore" onClose={vi.fn()}>
        <button>Cancel</button>
      </ModalOverlay>,
    );
    const dialog = screen.getByRole("dialog", { name: "Confirm restore" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");
    expect(document.activeElement).toBe(dialog);
  });

  it("closes on Escape, and ignores Escape when there is no onClose", () => {
    const onClose = vi.fn();
    const { rerender } = render(
      <ModalOverlay label="x" onClose={onClose}>
        <button>Cancel</button>
      </ModalOverlay>,
    );
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
    rerender(
      <ModalOverlay label="x">
        <button>Cancel</button>
      </ModalOverlay>,
    );
    fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it("keeps Tab inside the dialog and restores focus when it closes", () => {
    render(<button>opener</button>);
    const opener = screen.getByText("opener");
    opener.focus();
    const { unmount } = render(
      <ModalOverlay label="x" onClose={vi.fn()}>
        <button>First</button>
        <button>Last</button>
      </ModalOverlay>,
    );
    const first = screen.getByText("First");
    const last = screen.getByText("Last");
    last.focus();
    fireEvent.keyDown(last, { key: "Tab" });
    expect(document.activeElement).toBe(first);
    fireEvent.keyDown(first, { key: "Tab", shiftKey: true });
    expect(document.activeElement).toBe(last);
    unmount();
    expect(document.activeElement).toBe(opener);
  });
});

describe("clickableRow (ADP-blp.40)", () => {
  it("activates on click, Enter and Space, but not for keys inside a nested control", () => {
    const onActivate = vi.fn();
    render(
      <div {...clickableRow(onActivate)}>
        Row <button>inner</button>
      </div>,
    );
    const row = screen.getByRole("button", { name: /Row/ });
    expect(row.getAttribute("tabindex")).toBe("0");
    fireEvent.click(row);
    fireEvent.keyDown(row, { key: "Enter" });
    fireEvent.keyDown(row, { key: " " });
    fireEvent.keyDown(row, { key: "a" });
    expect(onActivate).toHaveBeenCalledTimes(3);
    fireEvent.keyDown(screen.getByText("inner"), { key: "Enter" });
    expect(onActivate).toHaveBeenCalledTimes(3);
  });
});

import { Tabs } from "./Tabs";

describe("Tabs (ADP-blp.45)", () => {
  const tabs = [
    { id: "a", label: "Alpha" },
    { id: "b", label: "Beta" },
    { id: "c", label: "Gamma" },
  ] as const;

  it("is a tablist with one selected tab in the Tab order", () => {
    render(<Tabs label="Sections" tabs={tabs} active="b" onChange={vi.fn()} />);
    expect(screen.getByRole("tablist", { name: "Sections" })).toBeTruthy();
    const selected = screen.getByRole("tab", { selected: true });
    expect(selected.textContent).toBe("Beta");
    expect(selected.getAttribute("tabindex")).toBe("0");
    expect(screen.getByRole("tab", { name: "Alpha" }).getAttribute("tabindex")).toBe("-1");
  });

  it("changes tab on click and with the arrow, Home and End keys", () => {
    const onChange = vi.fn();
    render(<Tabs label="Sections" tabs={tabs} active="b" onChange={onChange} />);
    fireEvent.click(screen.getByRole("tab", { name: "Gamma" }));
    const beta = screen.getByRole("tab", { name: "Beta" });
    fireEvent.keyDown(beta, { key: "ArrowRight" });
    fireEvent.keyDown(beta, { key: "ArrowLeft" });
    fireEvent.keyDown(beta, { key: "Home" });
    fireEvent.keyDown(beta, { key: "End" });
    fireEvent.keyDown(beta, { key: "x" });
    expect(onChange.mock.calls.map((c) => c[0])).toEqual(["c", "c", "a", "a", "c"]);
  });
});
