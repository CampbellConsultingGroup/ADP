// ADP-4sf: regression coverage for the viewport-overflow fix. A recommendation option with
// many proposed elements used to render a dialog taller than the viewport with no scroll
// container anywhere (neither the overlay nor the dialog box had overflow set), pushing
// "Confirm Accept"/"Cancel" off-screen with no way to reach them -- reported live by the user
// as "able to type in a reason but no way to save and move on."
//
// jsdom has no real layout engine (no actual pixel measurement, no computed overflow/clipping),
// so this can't assert "the button is visually off-screen" directly. Instead it locks in the
// structural fix that *causes* the button to stay reachable regardless of content length: the
// footer (Cancel/Confirm) is a flex-shrink-0 sibling of the scrollable content pane, never a
// descendant of it, and the dialog frame itself is height-bounded (maxHeight: 100%) with
// overflow only on that one middle pane. If a future refactor moved the footer back inside the
// scrolling region, or dropped the maxHeight/overflowY styling, this test fails.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import AcceptDialog from "./AcceptDialog";
import type { ProposedElement, SolutionOption } from "../api/recommend";

function option(overrides: Partial<SolutionOption> = {}): SolutionOption {
  return {
    option_id: "OPT-1",
    rank: 1,
    title: "Event-Driven Order Processing",
    rationale: "...",
    advisory: false,
    satisfies: [],
    trade_offs: [],
    proposed_elements: [],
    grounded_on: [],
    ranking_score: 0.9,
    status: "pending",
    knowledge_source: "knowledge_base",
    ...overrides,
  };
}

function manyProposedElements(count: number): ProposedElement[] {
  return Array.from({ length: count }, (_, i) => ({
    name: `Element ${i}`,
    kind: "component",
    description: `Description for element ${i}`,
    satisfies: [],
  }));
}

// Locates the one scrollable pane (overflowY: auto) inside the dialog -- the middle content
// section, not the header or footer, per the fix's own comment in AcceptDialog.tsx.
function scrollablePane(container: HTMLElement): HTMLElement {
  const pane = container.querySelector<HTMLElement>('[style*="overflow-y: auto"]');
  if (!pane) throw new Error("expected a scrollable content pane (style overflow-y: auto)");
  return pane;
}

describe("AcceptDialog viewport overflow fix (ADP-4sf)", () => {
  it("bounds the dialog frame's height and scrolls only the middle content pane", () => {
    const { container } = render(
      <AcceptDialog option={option()} designId="DSN-1" onConfirm={vi.fn()} onCancel={vi.fn()} isPending={false} />,
    );

    // The dialog box itself (not the fixed full-screen overlay) is a bounded flex column.
    const dialogBox = container.querySelector<HTMLElement>('[style*="max-height: 100%"]');
    expect(dialogBox).not.toBeNull();
    expect(dialogBox!.style.display).toBe("flex");
    expect(dialogBox!.style.flexDirection).toBe("column");

    const pane = scrollablePane(container);
    expect(pane.style.minHeight).toBe("0");
  });

  it("keeps Confirm Accept / Cancel outside the scrollable pane, even with a long proposed_elements list", () => {
    const { container } = render(
      <AcceptDialog
        option={option({ proposed_elements: manyProposedElements(20) })}
        designId="DSN-1"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        isPending={false}
      />,
    );

    const pane = scrollablePane(container);

    // All 20 elements really did render (the content that used to blow out the viewport) --
    // a plain substring check on the pane's own text, not a getByText query: each "Element N"
    // is a bare text node between sibling <strong>/<span> elements (not its own element), and
    // the repeated "Element N" pattern across 20 rows makes exact:false substring queries
    // ambiguous (multiple ancestor levels all "contain" the same substring).
    expect(pane.textContent).toContain("This will add 20 elements to the design:");
    expect(pane.textContent).toContain("Element 0");
    expect(pane.textContent).toContain("Element 19");

    const confirmButton = screen.getByRole("button", { name: "Confirm Accept" });
    const cancelButton = screen.getByRole("button", { name: "Cancel" });

    // The bug: these used to be reachable only by scrolling a pane that didn't exist. The fix:
    // they're siblings of the scrollable pane, not descendants of it -- scrolling the content
    // never moves them off-screen because they were never inside the scrolling region at all.
    expect(pane.contains(confirmButton)).toBe(false);
    expect(pane.contains(cancelButton)).toBe(false);
  });

  it("Confirm Accept still submits the correct payload with a long proposed_elements list", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(
      <AcceptDialog
        option={option({ option_id: "OPT-42", proposed_elements: manyProposedElements(20) })}
        designId="DSN-1"
        onConfirm={onConfirm}
        onCancel={vi.fn()}
        isPending={false}
      />,
    );

    await user.type(screen.getByPlaceholderText(/Why are you accepting/), "Matches our target architecture.");
    await user.click(screen.getByRole("button", { name: "Confirm Accept" }));

    expect(onConfirm).toHaveBeenCalledWith({
      confirmation_id: "CONFIRM-OPT-42",
      advisory_acknowledged: false,
      acceptance_reason: "Matches our target architecture.",
    });
  });

  it("an advisory option requires the acknowledgement checkbox before Confirm Accept is enabled", async () => {
    const user = userEvent.setup();
    render(
      <AcceptDialog
        option={option({ advisory: true })}
        designId="DSN-1"
        onConfirm={vi.fn()}
        onCancel={vi.fn()}
        isPending={false}
      />,
    );

    const confirmButton = screen.getByRole("button", { name: "Confirm Accept" }) as HTMLButtonElement;
    expect(confirmButton.disabled).toBe(true);

    await user.click(screen.getByRole("checkbox"));
    expect(confirmButton.disabled).toBe(false);
  });
});
