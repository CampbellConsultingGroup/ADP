// ADP-3ei: Requirements Intake now durably persists the raw source text (linked
// to the design) instead of discarding it — the banner must say so, not the old
// "not stored" claim.
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import IntakeTextForm from "./IntakeTextForm";

vi.mock("../api/intake", () => ({
  useSubmitIntake: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

vi.mock("../api/config", () => ({
  useLLMConfig: () => ({ data: { api_key_configured: true, extraction_model: "claude-sonnet-4-6" } }),
  useAvailableModels: () => ({ data: { models: [] }, isLoading: false }),
}));

describe("IntakeTextForm source text retention banner (ADP-3ei)", () => {
  it("tells the user source text IS stored, not that it is discarded", () => {
    render(<IntakeTextForm designId="D-001" onOperationCreated={vi.fn()} />);

    expect(screen.getByText(/source text is stored with this design/i)).toBeTruthy();
    expect(screen.queryByText(/not stored after extraction/i)).toBeNull();
  });
});
