/** Component test: capability gap analysis panel (ADP-zg3.4). */

import { describe, it, expect, afterEach, vi } from "vitest";
import { screen, cleanup, waitFor } from "@testing-library/react";

import CapabilityGapPanel from "../../src/intake/CapabilityGapPanel";
import { mockFetch, renderWithQuery } from "./registry-test-utils";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("CapabilityGapPanel", () => {
  it("renders present matches and missing gaps for both capability types", async () => {
    mockFetch({
      "GET /api/v1/designs/D-1/capability-gaps": {
        design_id: "D-1",
        business_capabilities: {
          present: [
            {
              requirement_id: "REQ-001",
              requirement_title: "Fraud detection",
              capability_id: "CAP-001",
              capability_name: "Fraud Detection",
              relevance: 0.8,
            },
          ],
          missing: [
            { requirement_id: "REQ-002", requirement_title: "Quantum encryption" },
          ],
        },
        technical_capabilities: { present: [], missing: [] },
      },
    });

    renderWithQuery(<CapabilityGapPanel designId="D-1" />);

    await waitFor(() => {
      expect(screen.getByText(/Capability Gap Analysis/i)).toBeDefined();
    });
    expect(screen.getByText(/Fraud detection/)).toBeDefined();
    expect(screen.getByText(/covered by "Fraud Detection"/)).toBeDefined();
    expect(screen.getByText(/Quantum encryption/)).toBeDefined();
    expect(screen.getByText(/no matching capability/i)).toBeDefined();
  });

  it("renders nothing when there are no requirements to analyze", async () => {
    mockFetch({
      "GET /api/v1/designs/D-1/capability-gaps": {
        design_id: "D-1",
        business_capabilities: { present: [], missing: [] },
        technical_capabilities: { present: [], missing: [] },
      },
    });

    const { container } = renderWithQuery(<CapabilityGapPanel designId="D-1" />);

    await waitFor(() => {
      expect(container.textContent).toBe("");
    });
  });
});
