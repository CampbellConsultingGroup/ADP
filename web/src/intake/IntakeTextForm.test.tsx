// ADP-3ei: Requirements Intake now durably persists the raw source text (linked
// to the design) instead of discarding it — the banner must say so, not the old
// "not stored" claim.
//
// Intake must be reachable with no design selected at all: it's where a
// design starts (capturing the Business Problem), so the first submit
// creates the design lazily rather than requiring one to already exist.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import IntakeTextForm from "./IntakeTextForm";

const submitMutate = vi.fn();
const createDesignMutateAsync = vi.fn();

vi.mock("../api/intake", () => ({
  useSubmitIntake: () => ({ mutate: submitMutate, isPending: false, isError: false }),
}));

vi.mock("../api/designs", () => ({
  useCreateDesign: () => ({ mutateAsync: createDesignMutateAsync, isError: false }),
}));

vi.mock("../api/config", () => ({
  useLLMConfig: () => ({ data: { api_key_configured: true, extraction_model: "claude-sonnet-4-6" } }),
  useAvailableModels: () => ({ data: { models: [] }, isLoading: false }),
}));

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/Business Problem/i), { target: { value: "Checkout is slow" } });
  fireEvent.change(screen.getByLabelText(/Desired Outcome/i), { target: { value: "Checkout is fast" } });
}

describe("IntakeTextForm source text retention banner (ADP-3ei)", () => {
  it("tells the user source text IS stored, not that it is discarded", () => {
    render(<IntakeTextForm designId="D-001" onOperationCreated={vi.fn()} />);

    expect(screen.getByText(/source text is stored with this design/i)).toBeTruthy();
    expect(screen.queryByText(/not stored after extraction/i)).toBeNull();
  });
});

describe("IntakeTextForm deferred design creation (Intake is always reachable)", () => {
  beforeEach(() => {
    submitMutate.mockReset();
    createDesignMutateAsync.mockReset();
  });

  it("creates a design titled from the Business Problem, then submits intake against it, when none exists yet", async () => {
    createDesignMutateAsync.mockResolvedValue({ id: "DSN-NEW" });
    const onDesignCreated = vi.fn();
    render(
      <IntakeTextForm designId={null} onDesignCreated={onDesignCreated} onOperationCreated={vi.fn()} />,
    );

    fillRequiredFields();
    fireEvent.click(screen.getByText("Submit Intake"));

    await waitFor(() => expect(createDesignMutateAsync).toHaveBeenCalledWith({ title: "Checkout is slow" }));
    expect(onDesignCreated).toHaveBeenCalledWith("DSN-NEW");
    expect(submitMutate).toHaveBeenCalledWith(
      expect.objectContaining({ designId: "DSN-NEW", business_problem: "Checkout is slow" }),
      expect.anything(),
    );
  });

  it("submits directly against the existing design without creating a new one", () => {
    render(<IntakeTextForm designId="DSN-EXISTING" onOperationCreated={vi.fn()} />);

    fillRequiredFields();
    fireEvent.click(screen.getByText("Submit Intake"));

    expect(createDesignMutateAsync).not.toHaveBeenCalled();
    expect(submitMutate).toHaveBeenCalledWith(
      expect.objectContaining({ designId: "DSN-EXISTING" }),
      expect.anything(),
    );
  });
});
