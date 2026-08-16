// ADP-3ei: the minimal frontend trigger for LLM-as-Judge validation — without
// this, the new /validate endpoint would never actually get called, so no
// verdicts would ever be produced to capture.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import ValidateDesignButton from "./ValidateDesignButton";

const startMutate = vi.fn();
const overrideMutate = vi.fn();
let statusData: unknown = undefined;

vi.mock("../api/validate", () => ({
  useStartValidation: () => ({ mutate: startMutate, isPending: false }),
  useValidationStatus: () => ({ data: statusData }),
  useOverrideVerdict: () => ({ mutate: overrideMutate, isPending: false, isError: false }),
}));

describe("ValidateDesignButton (ADP-3ei)", () => {
  beforeEach(() => {
    startMutate.mockReset();
    overrideMutate.mockReset();
    statusData = undefined;
  });

  it("shows a Run Validation action when the menu opens, before any run has started", () => {
    render(<ValidateDesignButton designId="DSN-001" />);
    fireEvent.click(screen.getByText("Validate ▾"));
    expect(screen.getByText("Run Validation")).toBeTruthy();
  });

  it("starts validation when Run Validation is clicked", () => {
    render(<ValidateDesignButton designId="DSN-001" />);
    fireEvent.click(screen.getByText("Validate ▾"));
    fireEvent.click(screen.getByText("Run Validation"));
    expect(startMutate).toHaveBeenCalledTimes(1);
  });

  it("renders findings and an override action for a FAIL verdict", () => {
    statusData = {
      operation_id: "OP-1",
      design_id: "DSN-001",
      status: "completed",
      verdict: {
        verdict_id: "VRD-1",
        status: "fail",
        composite_score: null,
        design_version: 2,
        citations_present: false,
        findings: [
          { finding_id: "F-1", critic_name: "structural", severity: "critical", description: "Orphan element" },
        ],
      },
    };
    render(<ValidateDesignButton designId="DSN-001" />);
    fireEvent.click(screen.getByText("Validate ▾"));

    expect(screen.getByText(/Orphan element/)).toBeTruthy();
    expect(screen.getByText("Override Verdict")).toBeTruthy();
  });

  it("submits the override justification", () => {
    statusData = {
      operation_id: "OP-1",
      design_id: "DSN-001",
      status: "completed",
      verdict: {
        verdict_id: "VRD-1",
        status: "fail",
        composite_score: null,
        design_version: 2,
        citations_present: false,
        findings: [],
      },
    };
    render(<ValidateDesignButton designId="DSN-001" />);
    fireEvent.click(screen.getByText("Validate ▾"));

    const textarea = screen.getByLabelText("Override justification") as HTMLTextAreaElement;
    fireEvent.change(textarea, { target: { value: "Accepted risk" } });
    fireEvent.click(screen.getByText("Override Verdict"));

    expect(overrideMutate).toHaveBeenCalledWith(
      { justification: "Accepted risk" },
      expect.anything(),
    );
  });
});
