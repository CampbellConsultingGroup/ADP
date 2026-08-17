// Intake must be reachable with no design selected at all: it's where a
// design starts (capturing the Business Problem), so the first submit
// creates the design lazily rather than requiring one to already exist.
//
// Known Requirements is a typed (statement + kind) list entered directly and
// saved together with Business Problem/Desired Outcome in one submit action
// -- there is no more free-text/AI-extraction step on this screen.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";

import IntakeTextForm from "./IntakeTextForm";

const submitMutateAsync = vi.fn();
const createDesignMutateAsync = vi.fn();
const addRequirementMutateAsync = vi.fn();
const linkCapabilityMutateAsync = vi.fn();

const CAPABILITIES = [
  { id: "CAP-1", name: "Order Management" },
  { id: "CAP-2", name: "Payments" },
];

vi.mock("../api/intake", async () => {
  const actual = await vi.importActual<typeof import("../api/intake")>("../api/intake");
  return {
    ...actual,
    useSubmitIntake: () => ({ mutateAsync: submitMutateAsync, isPending: false, isError: false }),
    useAddRequirement: () => ({ mutateAsync: addRequirementMutateAsync, isPending: false, isError: false }),
  };
});

let existingDesignData: { business_problem?: string | null; desired_outcome?: string | null } | undefined;

vi.mock("../api/designs", () => ({
  useCreateDesign: () => ({ mutateAsync: createDesignMutateAsync, isError: false }),
  useDesign: () => ({ data: existingDesignData }),
}));

vi.mock("../api/business", () => ({
  useCapabilities: () => ({ data: { items: CAPABILITIES, total: CAPABILITIES.length } }),
  useLinkDesignToCapabilities: () => ({ mutateAsync: linkCapabilityMutateAsync, isError: false }),
}));

function fillRequiredFields() {
  fireEvent.change(screen.getByLabelText(/Business Problem/i), { target: { value: "Checkout is slow" } });
  fireEvent.change(screen.getByLabelText(/Desired Outcome/i), { target: { value: "Checkout is fast" } });
}

// Known Requirements' "Add" button — the form has two ("Add" also appears
// under Business Capabilities Impacted); Known Requirements renders first.
function knownRequirementAddButton() {
  return screen.getAllByText("Add")[0];
}

function addKnownRequirement(statement: string, kindLabel = "Functional") {
  fireEvent.change(screen.getByPlaceholderText(/single sign-on/i), { target: { value: statement } });
  fireEvent.change(screen.getByDisplayValue("Functional"), { target: { value: kindLabel === "Functional" ? "functional" : "non_functional" } });
  fireEvent.click(knownRequirementAddButton());
}

beforeEach(() => {
  submitMutateAsync.mockReset().mockResolvedValue({ operation_id: "OP-1" });
  createDesignMutateAsync.mockReset();
  addRequirementMutateAsync.mockReset().mockResolvedValue({ requirement_id: "REQ-001" });
  linkCapabilityMutateAsync.mockReset().mockResolvedValue({ items: [] });
  existingDesignData = undefined;
});

describe("IntakeTextForm prefill from an existing design", () => {
  it("pre-fills Business Problem and Desired Outcome from the design's saved data", () => {
    existingDesignData = { business_problem: "Checkout is slow", desired_outcome: "Checkout is fast" };
    render(<IntakeTextForm designId="DSN-EXISTING" onSubmitted={vi.fn()} />);

    expect((screen.getByLabelText(/Business Problem/i) as HTMLTextAreaElement).value).toBe("Checkout is slow");
    expect((screen.getByLabelText(/Desired Outcome/i) as HTMLTextAreaElement).value).toBe("Checkout is fast");
  });

  it("leaves the fields blank when the design has no saved business problem yet", () => {
    existingDesignData = { business_problem: null, desired_outcome: null };
    render(<IntakeTextForm designId="DSN-EXISTING" onSubmitted={vi.fn()} />);

    expect((screen.getByLabelText(/Business Problem/i) as HTMLTextAreaElement).value).toBe("");
    expect((screen.getByLabelText(/Desired Outcome/i) as HTMLTextAreaElement).value).toBe("");
  });

  it("does not clobber an in-progress edit once prefilled", () => {
    existingDesignData = { business_problem: "Checkout is slow", desired_outcome: "Checkout is fast" };
    render(<IntakeTextForm designId="DSN-EXISTING" onSubmitted={vi.fn()} />);

    fireEvent.change(screen.getByLabelText(/Business Problem/i), { target: { value: "Edited by user" } });
    expect((screen.getByLabelText(/Business Problem/i) as HTMLTextAreaElement).value).toBe("Edited by user");
  });
});

describe("IntakeTextForm deferred design creation (Intake is always reachable)", () => {
  it("creates a design titled from the Business Problem, then submits intake against it, when none exists yet", async () => {
    createDesignMutateAsync.mockResolvedValue({ id: "DSN-NEW" });
    const onDesignCreated = vi.fn();
    const onSubmitted = vi.fn();
    render(
      <IntakeTextForm designId={null} onDesignCreated={onDesignCreated} onSubmitted={onSubmitted} />,
    );

    fillRequiredFields();
    fireEvent.click(screen.getByText("Submit Intake"));

    await waitFor(() => expect(createDesignMutateAsync).toHaveBeenCalledWith({ title: "Checkout is slow" }));
    expect(onDesignCreated).toHaveBeenCalledWith("DSN-NEW");
    await waitFor(() => expect(submitMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ designId: "DSN-NEW", business_problem: "Checkout is slow", text: "" }),
    ));
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(0, 0));
  });

  it("submits directly against the existing design without creating a new one", async () => {
    render(<IntakeTextForm designId="DSN-EXISTING" onSubmitted={vi.fn()} />);

    fillRequiredFields();
    fireEvent.click(screen.getByText("Submit Intake"));

    await waitFor(() => expect(submitMutateAsync).toHaveBeenCalledWith(
      expect.objectContaining({ designId: "DSN-EXISTING" }),
    ));
    expect(createDesignMutateAsync).not.toHaveBeenCalled();
  });
});

describe("IntakeTextForm Known Requirements typed list", () => {
  it("rejects a requirement shorter than 10 characters", () => {
    render(<IntakeTextForm designId="DSN-001" onSubmitted={vi.fn()} />);
    addKnownRequirement("too short");
    expect(screen.getByText(/at least 10 characters/i)).toBeTruthy();
  });

  it("adds a requirement to the list with its chosen kind, and allows removing it", () => {
    render(<IntakeTextForm designId="DSN-001" onSubmitted={vi.fn()} />);
    addKnownRequirement("The system must support SSO");
    expect(screen.getByText("The system must support SSO")).toBeTruthy();
    expect(screen.getByText("functional")).toBeTruthy();

    fireEvent.click(screen.getByTitle("Remove"));
    expect(screen.queryByText("The system must support SSO")).toBeNull();
  });

  it("submits each queued requirement against the resolved design, sequentially, on Submit", async () => {
    const onSubmitted = vi.fn();
    render(<IntakeTextForm designId="DSN-001" onSubmitted={onSubmitted} />);

    fillRequiredFields();
    addKnownRequirement("The system must support SSO");
    fireEvent.change(screen.getByPlaceholderText(/single sign-on/i), { target: { value: "The system must log audit events" } });
    fireEvent.click(knownRequirementAddButton());

    fireEvent.click(screen.getByText("Submit Intake"));

    await waitFor(() => expect(addRequirementMutateAsync).toHaveBeenCalledTimes(2));
    expect(addRequirementMutateAsync).toHaveBeenNthCalledWith(1, {
      designId: "DSN-001", statement: "The system must support SSO", kind: "functional",
    });
    expect(addRequirementMutateAsync).toHaveBeenNthCalledWith(2, {
      designId: "DSN-001", statement: "The system must log audit events", kind: "functional",
    });
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(2, 0));

    // The queued list is cleared after a successful submit.
    expect(screen.queryByText("The system must support SSO")).toBeNull();
  });
});

describe("IntakeTextForm Business Capabilities Impacted", () => {
  function capabilitySelect() {
    return screen.getByLabelText(/Business Capabilities Impacted/i) as HTMLSelectElement;
  }

  it("adds a selected capability to the list, removing it from further options, and allows removing it", () => {
    render(<IntakeTextForm designId="DSN-001" onSubmitted={vi.fn()} />);

    fireEvent.change(capabilitySelect(), { target: { value: "CAP-1" } });
    fireEvent.click(screen.getAllByText("Add")[1]);

    expect(screen.getByText("Order Management")).toBeTruthy();
    // Removed from the dropdown's remaining options once selected.
    expect(screen.queryByText("Order Management", { selector: "option" })).toBeNull();

    fireEvent.click(screen.getByTitle("Remove"));
    // Back to being just a dropdown option, not also a queued chip.
    expect(screen.queryByTitle("Remove")).toBeNull();
  });

  it("links each selected capability to the resolved design on submit, and clears the list", async () => {
    const onSubmitted = vi.fn();
    render(<IntakeTextForm designId="DSN-001" onSubmitted={onSubmitted} />);

    fillRequiredFields();
    fireEvent.change(capabilitySelect(), { target: { value: "CAP-1" } });
    fireEvent.click(screen.getAllByText("Add")[1]);
    fireEvent.change(capabilitySelect(), { target: { value: "CAP-2" } });
    fireEvent.click(screen.getAllByText("Add")[1]);

    fireEvent.click(screen.getByText("Submit Intake"));

    await waitFor(() => expect(linkCapabilityMutateAsync).toHaveBeenCalledTimes(2));
    expect(linkCapabilityMutateAsync).toHaveBeenNthCalledWith(1, { designId: "DSN-001", capabilityId: "CAP-1" });
    expect(linkCapabilityMutateAsync).toHaveBeenNthCalledWith(2, { designId: "DSN-001", capabilityId: "CAP-2" });
    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(0, 2));

    // The queued list is cleared after a successful submit -- no more chips.
    expect(screen.queryByTitle("Remove")).toBeNull();
  });

  it("does not block submit on a 409 (already linked)", async () => {
    linkCapabilityMutateAsync.mockRejectedValue(Object.assign(new Error("conflict"), { status: 409 }));
    const onSubmitted = vi.fn();
    render(<IntakeTextForm designId="DSN-001" onSubmitted={onSubmitted} />);

    fillRequiredFields();
    fireEvent.change(capabilitySelect(), { target: { value: "CAP-1" } });
    fireEvent.click(screen.getAllByText("Add")[1]);
    fireEvent.click(screen.getByText("Submit Intake"));

    await waitFor(() => expect(onSubmitted).toHaveBeenCalledWith(0, 1));
  });
});
