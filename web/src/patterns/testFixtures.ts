// Shared fixtures for the Patterns screen tests (935). Not a test file itself.

import { vi } from "vitest";
import type { PatternVersionDetail, PatternVersionSummary } from "../api/patterns";

export function summary(overrides: Partial<PatternVersionSummary> = {}): PatternVersionSummary {
  return {
    id: "v-1",
    pattern_key: "ea.integration.domain-event-backbone",
    version: "1.0.0",
    kind: "reference-architecture",
    lifecycle: "draft",
    name: "Domain Event Backbone",
    summary: "Domains integrate through one backbone.",
    tags: ["integration"],
    digest: "a".repeat(64),
    created_at: "2026-11-14T00:00:00Z",
    created_by: "ea",
    lifecycle_changed_at: "2026-11-14T00:00:00Z",
    ...overrides,
  };
}

export function detail(overrides: Partial<PatternVersionDetail> = {}): PatternVersionDetail {
  return {
    ...summary(),
    definition: {
      pattern: "ea.integration.domain-event-backbone",
      version: "1.0.0",
      kind: "reference-architecture",
      name: "Domain Event Backbone",
      summary: "Domains integrate through one backbone.",
      owner_role: "enterprise",
      tags: ["integration"],
      motivation: {
        context: "Many domains.", problem: "Point-to-point sprawl.", forces: [], benefits: ["Decoupling"],
        liabilities: [], principles: ["PRIN-003"], controls: [],
      },
      roles: {
        backbone: {
          element_type: "application", cardinality: { min: 1, max: 1, per: null }, selector: null,
          label: "Backbone", stereotype: "platform", description: null,
        },
      },
      relationships: [],
      constraints: [],
      transition: null,
      relations: [],
      known_implementations: [],
      views: ["structure"],
    },
    relations: [],
    issues: [],
    allowed_transitions: ["proposed"],
    history: [],
    knowledge_item_id: null,
    ...overrides,
  };
}

export function mutation(mutateAsync = vi.fn().mockResolvedValue({})) {
  return { mutateAsync, isPending: false } as never;
}

