// ADP-d8u.1 (T015): mirrors web/src/chat/ChatPanel.test.tsx's
// vi.mock(hooks-module) convention for the useThemes() dropdown source.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveForm from "./ObjectiveForm";
import * as strategyApi from "../api/strategy";

vi.mock("../api/strategy");

const mockedApi = vi.mocked(strategyApi);

beforeEach(() => {
  vi.clearAllMocks();
  mockedApi.useThemes.mockReturnValue({
    data: {
      items: [{ id: "t1", name: "Growth", created_at: "2026-01-01T00:00:00Z" }],
      total: 1,
    },
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useThemes>);
});

describe("ObjectiveForm", () => {
  it("rejects submission with a blank owner", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText("Statement *"), "Reduce claims cycle time");
    await user.click(screen.getByText("Save"));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/owner is required/i)).toBeTruthy();
  });

  it("rejects submission with a blank statement", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText("Owner *"), "Claims Platform Team");
    await user.click(screen.getByText("Save"));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/statement is required/i)).toBeTruthy();
  });

  it("submits a fully-populated metric group correctly when provided", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText("Owner *"), "Claims Platform Team");
    await user.type(screen.getByLabelText("Statement *"), "Reduce claims cycle time");
    await user.type(screen.getByLabelText("Metric name"), "Claims cycle time");
    await user.type(screen.getByLabelText("Target value"), "40");
    await user.type(screen.getByLabelText("Target unit"), "%");
    await user.selectOptions(screen.getByLabelText("Direction"), "decrease");
    await user.type(screen.getByLabelText("Fiscal year *"), "2026");

    await user.click(screen.getByText("Save"));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        theme_id: "t1",
        owner: "Claims Platform Team",
        statement: "Reduce claims cycle time",
        metric_name: "Claims cycle time",
        target_value: 40,
        target_unit: "%",
        direction: "decrease",
        fiscal_year: 2026,
      }),
    );
  });

  it("rejects submission with only some metric fields filled in (bug found live, 2026-08-14)", async () => {
    // Previously: selecting only Direction (leaving metric name/target value/
    // target unit blank) silently sent a partial metric group the backend
    // rejects with a 422, with no client-side guidance -- looked like "Save
    // doesn't work" since nothing else in the UI explained why.
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText("Owner *"), "Claims Platform Team");
    await user.type(screen.getByLabelText("Statement *"), "Reduce claims cycle time");
    await user.selectOptions(screen.getByLabelText("Direction"), "decrease");
    await user.type(screen.getByLabelText("Fiscal year *"), "2026");

    await user.click(screen.getByText("Save"));

    expect(onSubmit).not.toHaveBeenCalled();
    expect(screen.getByText(/must all be filled in together, or all left blank/i)).toBeTruthy();
  });

  it("submits with no metric group at all when none of the fields are filled", async () => {
    const onSubmit = vi.fn();
    const user = userEvent.setup();
    render(<ObjectiveForm onSubmit={onSubmit} onCancel={vi.fn()} />);

    await user.type(screen.getByLabelText("Owner *"), "Retention Team");
    await user.type(screen.getByLabelText("Statement *"), "Grow renewal rate");
    await user.type(screen.getByLabelText("Fiscal year *"), "2027");

    await user.click(screen.getByText("Save"));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        metric_name: undefined,
        target_value: undefined,
        target_unit: undefined,
        direction: undefined,
      }),
    );
  });
});
