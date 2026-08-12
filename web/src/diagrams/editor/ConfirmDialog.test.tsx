// ADP-SPEC-052 (User Story 1, Acceptance Scenario 3 / FR-005): verifies the delete-confirmation
// dialog renders ADP's modal styling (contracts/diagram-css-contract.md's Modal.tsx table).
//
// Note (implementation deviation from tasks.md T007's original wording): this dialog is triggered
// from Canvas.tsx's own "Delete Selected" toolbar action (canvas element deletion), not from the
// diagram list's delete action -- confirmed by reading Canvas.tsx directly (it's the only
// <ConfirmDialog> call site in the codebase). Testing it here, against the component directly,
// is more direct than driving Canvas's full selection/keyboard flow through DiagramEditorPage's
// test harness just to reach the same markup.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { ConfirmDialog } from "./ConfirmDialog";

describe("ConfirmDialog: ADP modal styling (ADP-SPEC-052 FR-005)", () => {
  it("renders via Modal's styled dialog structure, not native browser-default chrome", () => {
    render(<ConfirmDialog message="Delete the selected shape?" onConfirm={vi.fn()} onCancel={vi.fn()} />);

    const dialog = screen.getByTestId("confirm-dialog");
    expect(dialog.className).toContain("modal");
    // ConfirmDialog passes title={null} -- no header, per Modal.tsx's own contract.
    expect(dialog.querySelector(".modal__header")).toBeNull();
    expect(dialog.querySelector(".modal__body")).not.toBeNull();
    expect(dialog.querySelector(".modal__footer")).not.toBeNull();

    screen.getByText("Delete the selected shape?");
    expect(screen.getByTestId("confirm-dialog-cancel").className).toContain("btn--secondary");
    expect(screen.getByTestId("confirm-dialog-confirm").className).toContain("btn--danger");
  });
});
