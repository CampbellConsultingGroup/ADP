/** Component test: Intake form -- Business Problem/Desired Outcome plus a
 * typed (statement + kind) Known Requirements list, all saved together in
 * one submit action. No free-text/AI-extraction step (removed). */

import { describe, it, expect, afterEach, vi } from "vitest";
import { screen, fireEvent, cleanup, waitFor } from "@testing-library/react";

import IntakeTextForm from "../../src/intake/IntakeTextForm";
import { mockFetch, renderWithQuery } from "./registry-test-utils";

function routes(extra: Record<string, unknown> = {}) {
  return {
    "POST /api/v1/designs/D-1/intake": {
      operation_id: "op-1",
      design_id: "D-1",
      mode: "bulk_text",
      status: "completed",
    },
    "POST /api/v1/designs/D-1/requirements": {
      requirement_id: "REQ-001",
      title: "The system must sustain 10,000 concurrent checkouts.",
      description: "The system must sustain 10,000 concurrent checkouts.",
      kind: "functional",
      proposal_id: null,
    },
    "GET /api/v1/business/capabilities": { items: [], total: 0 },
    ...extra,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("IntakeTextForm", () => {
  it("renders the required inputs and disables submit until Business Problem/Desired Outcome are filled", () => {
    mockFetch(routes());
    renderWithQuery(<IntakeTextForm designId="D-1" onSubmitted={() => {}} />);

    expect(screen.getByLabelText(/Business Problem/i)).toBeDefined();
    expect(screen.getByLabelText(/Desired Outcome/i)).toBeDefined();
    expect(screen.getByLabelText(/Known Requirements/i)).toBeDefined();

    const button = screen.getByRole("button", { name: /Submit Intake/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(true); // required fields empty

    fireEvent.change(screen.getByLabelText(/Business Problem/i), {
      target: { value: "Peak checkout latency loses sales." },
    });
    expect(button.disabled).toBe(true); // still missing desired outcome

    fireEvent.change(screen.getByLabelText(/Desired Outcome/i), {
      target: { value: "Sub-second checkout at 10k users." },
    });
    expect(button.disabled).toBe(false); // both required filled; Known Requirements is optional
  });

  it("saves Business Problem/Desired Outcome and every queued Known Requirement together on submit", async () => {
    const calls = mockFetch(routes());
    const onSubmitted = vi.fn();
    renderWithQuery(<IntakeTextForm designId="D-1" onSubmitted={onSubmitted} />);

    fireEvent.change(screen.getByLabelText(/Business Problem/i), {
      target: { value: "Peak checkout latency loses sales." },
    });
    fireEvent.change(screen.getByLabelText(/Desired Outcome/i), {
      target: { value: "Sub-second checkout at 10k users." },
    });
    fireEvent.change(screen.getByLabelText(/Known Requirements/i), {
      target: { value: "The system must sustain 10,000 concurrent checkouts." },
    });
    // Known Requirements' "Add" -- the form has a second "Add" under Business
    // Capabilities Impacted; Known Requirements renders first.
    fireEvent.click(screen.getAllByText("Add")[0]);

    fireEvent.click(screen.getByRole("button", { name: /Submit Intake/i }));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(1, 0));

    const intakeCall = calls.find((c) => c.url === "/api/v1/designs/D-1/intake");
    expect(intakeCall?.body).toMatchObject({
      mode: "bulk_text",
      business_problem: "Peak checkout latency loses sales.",
      desired_outcome: "Sub-second checkout at 10k users.",
      text: "",
    });

    const reqCall = calls.find((c) => c.url === "/api/v1/designs/D-1/requirements");
    expect(reqCall?.body).toMatchObject({
      statement: "The system must sustain 10,000 concurrent checkouts.",
      kind: "functional",
    });
  });

  it("rejects a Known Requirement shorter than 10 characters without adding it, but leaves Submit enabled", () => {
    mockFetch(routes());
    renderWithQuery(<IntakeTextForm designId="D-1" onSubmitted={() => {}} />);

    fireEvent.change(screen.getByLabelText(/Business Problem/i), { target: { value: "Problem." } });
    fireEvent.change(screen.getByLabelText(/Desired Outcome/i), { target: { value: "Outcome." } });
    fireEvent.change(screen.getByLabelText(/Known Requirements/i), { target: { value: "short" } });
    // Known Requirements' "Add" -- the form has a second "Add" under Business
    // Capabilities Impacted; Known Requirements renders first.
    fireEvent.click(screen.getAllByText("Add")[0]);

    expect(screen.getByText(/at least 10 characters/i)).toBeDefined();
    expect(screen.queryByText("short")).toBeNull();

    // Known Requirements is optional -- Business Problem/Desired Outcome alone
    // are enough to submit.
    const button = screen.getByRole("button", { name: /Submit Intake/i }) as HTMLButtonElement;
    expect(button.disabled).toBe(false);
  });
});
