// 935-pattern-registry FR-022: registry-owned knowledge items are marked and read-only here.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as knowledgeApi from "../api/knowledge";
import type { KnowledgeItemSummary } from "../api/knowledge";
import KnowledgeItemRow from "./KnowledgeItemRow";

vi.mock("../api/knowledge", async (orig) => {
  const actual = await orig<typeof import("../api/knowledge")>();
  return { ...actual, useDeleteKnowledgeItem: vi.fn() };
});
const api = vi.mocked(knowledgeApi);

function item(overrides: Partial<KnowledgeItemSummary> = {}): KnowledgeItemSummary {
  return {
    id: "PRIN-003",
    version: "1.0.0",
    kind: "principle",
    title: "API First Design",
    source_ref: "https://example.com/api-first",
    metadata: {},
    ...overrides,
  } as KnowledgeItemSummary;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.useDeleteKnowledgeItem.mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
});

describe("KnowledgeItemRow", () => {
  it("offers Edit and Delete for an ordinary item", () => {
    render(<KnowledgeItemRow item={item()} onEdit={() => {}} />);
    expect(screen.getByRole("button", { name: "Edit" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Delete" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "https://example.com/api-first" })).toBeTruthy();
  });

  it("marks a pattern-registry projection, links to Patterns and hides Edit/Delete", async () => {
    const onOpenPatterns = vi.fn();
    render(
      <KnowledgeItemRow
        item={item({
          id: "adp-pattern:ea.integration.domain-event-backbone",
          kind: "reference_architecture",
          title: "Domain Event Backbone",
          source_ref: "adp-pattern:ea.integration.domain-event-backbone",
          metadata: { managed_by: "pattern-registry", pattern_key: "ea.integration.domain-event-backbone" },
        })}
        onEdit={() => {}}
        onOpenPatterns={onOpenPatterns}
      />,
    );
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Delete" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: /Managed by Patterns/ }));
    expect(onOpenPatterns).toHaveBeenCalledTimes(1);
  });

  it("never renders a non-http source_ref as a link", () => {
    render(<KnowledgeItemRow item={item({ source_ref: "javascript:alert(1)" })} onEdit={() => {}} />);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText("javascript:alert(1)")).toBeTruthy();
  });
});
