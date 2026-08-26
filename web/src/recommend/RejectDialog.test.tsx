// ADP-4sf: regression coverage for the viewport-overflow fix, applied to RejectDialog
// defensively alongside AcceptDialog's own fix (same underlying bug class, even though
// RejectDialog's content is a single textarea rather than a variable-length list) -- see
// AcceptDialog.test.tsx's own comment for the full rationale and the jsdom-layout-engine
// caveat this test works around the same way.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RejectDialog from "./RejectDialog";
import type { SolutionOption } from "../api/recommend";

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

function scrollablePane(container: HTMLElement): HTMLElement {
  const pane = container.querySelector<HTMLElement>('[style*="overflow-y: auto"]');
  if (!pane) throw new Error("expected a scrollable content pane (style overflow-y: auto)");
  return pane;
}

describe("RejectDialog viewport overflow fix (ADP-4sf)", () => {
  it("bounds the dialog frame's height and scrolls only the middle content pane", () => {
    const { container } = render(
      <RejectDialog option={option()} onConfirm={vi.fn()} onCancel={vi.fn()} isPending={false} />,
    );

    const dialogBox = container.querySelector<HTMLElement>('[style*="max-height: 100%"]');
    expect(dialogBox).not.toBeNull();
    expect(dialogBox!.style.display).toBe("flex");
    expect(dialogBox!.style.flexDirection).toBe("column");

    const pane = scrollablePane(container);
    expect(pane.style.minHeight).toBe("0");
  });

  it("keeps Confirm Reject / Cancel outside the scrollable pane", () => {
    const { container } = render(
      <RejectDialog option={option()} onConfirm={vi.fn()} onCancel={vi.fn()} isPending={false} />,
    );

    const pane = scrollablePane(container);
    const confirmButton = screen.getByRole("button", { name: "Confirm Reject" });
    const cancelButton = screen.getByRole("button", { name: "Cancel" });

    expect(pane.contains(confirmButton)).toBe(false);
    expect(pane.contains(cancelButton)).toBe(false);
  });

  it("Confirm Reject is disabled until a reason is entered, then submits the trimmed reason", async () => {
    const user = userEvent.setup();
    const onConfirm = vi.fn();
    render(<RejectDialog option={option()} onConfirm={onConfirm} onCancel={vi.fn()} isPending={false} />);

    const confirmButton = screen.getByRole("button", { name: "Confirm Reject" }) as HTMLButtonElement;
    expect(confirmButton.disabled).toBe(true);

    await user.type(screen.getByPlaceholderText(/Explain why this option/), "  Doesn't reuse the existing gateway.  ");
    expect(confirmButton.disabled).toBe(false);

    await user.click(confirmButton);
    expect(onConfirm).toHaveBeenCalledWith("Doesn't reuse the existing gateway.");
  });
});
