// ADP-d8u.5 (T018)

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ObjectiveProgressForm from "./ObjectiveProgressForm";
import * as strategyApi from "../api/strategy";
import type { ObjectiveProgressEntry } from "../api/strategy";

vi.mock("../api/strategy");

const mockedStrategyApi = vi.mocked(strategyApi);

const EXISTING: ObjectiveProgressEntry = {
  objective_id: "obj-1",
  as_of_date: "2026-08-01",
  actual_value: 40,
  note: null,
  recorded_by: "jane",
  created_at: "2026-08-01T00:00:00Z",
};

let createMutate: ReturnType<typeof vi.fn>;
let updateMutate: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  createMutate = vi.fn();
  updateMutate = vi.fn();
  mockedStrategyApi.useCreateProgress.mockReturnValue({
    mutate: createMutate,
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useCreateProgress>);
  mockedStrategyApi.useUpdateProgress.mockReturnValue({
    mutate: updateMutate,
    isPending: false,
    error: null,
  } as unknown as ReturnType<typeof strategyApi.useUpdateProgress>);
});

describe("ObjectiveProgressForm: recording a new entry", () => {
  it("calls useCreateProgress's mutate for a date with no existing entry", async () => {
    const user = userEvent.setup();
    render(<ObjectiveProgressForm objectiveId="obj-1" existingEntries={[]} />);

    const dateInput = screen.getByLabelText("Date") as HTMLInputElement;
    await user.clear(dateInput);
    await user.type(dateInput, "2026-09-01");
    await user.type(screen.getByLabelText("Actual value"), "75");
    await user.click(screen.getByText("Record Progress"));

    expect(createMutate).toHaveBeenCalledWith(
      { as_of_date: "2026-09-01", actual_value: 75, note: null },
      expect.anything(),
    );
    expect(updateMutate).not.toHaveBeenCalled();
  });
});

describe("ObjectiveProgressForm: correcting an existing entry (FR-002a)", () => {
  it("switches to correction mode and calls useUpdateProgress's mutate for a date that already has an entry", async () => {
    const user = userEvent.setup();
    render(<ObjectiveProgressForm objectiveId="obj-1" existingEntries={[EXISTING]} />);

    const dateInput = screen.getByLabelText("Date") as HTMLInputElement;
    await user.clear(dateInput);
    await user.type(dateInput, "2026-08-01");

    expect(screen.getByText(/already exists/)).toBeTruthy();
    expect(screen.getByText("Save Correction")).toBeTruthy();

    await user.type(screen.getByLabelText("Actual value"), "60");
    await user.click(screen.getByText("Save Correction"));

    expect(updateMutate).toHaveBeenCalledWith(
      { asOfDate: "2026-08-01", body: { actual_value: 60, note: null } },
      expect.anything(),
    );
    expect(createMutate).not.toHaveBeenCalled();
  });
});
