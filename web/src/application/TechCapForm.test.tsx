// 938-capability-model-analysis US2: the create form carries the lifecycle.

import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import TechCapForm from "./TechCapForm";

describe("TechCapForm lifecycle", () => {
  it("defaults to Current with no end-of-life date", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<TechCapForm onSave={onSave} onCancel={() => {}} />);
    await user.type(screen.getByPlaceholderText("Capability name *"), "API Services");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ name: "API Services", lifecycle_status: "current", end_of_life_date: null }),
    );
  });

  it("offers the five statuses and sends the chosen status and date", async () => {
    const onSave = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    render(<TechCapForm onSave={onSave} onCancel={() => {}} />);
    const select = screen.getByRole("combobox", { name: /Lifecycle/ });
    expect(Array.from((select as HTMLSelectElement).options).map((o) => o.textContent)).toEqual([
      "Emerging", "Current", "Contained", "Retiring", "Retired",
    ]);
    await user.type(screen.getByPlaceholderText("Capability name *"), "Offline Sync");
    await user.selectOptions(select, "retiring");
    await user.type(screen.getByLabelText(/End of life/), "2027-06-30");
    await user.click(screen.getByRole("button", { name: "Save" }));
    expect(onSave).toHaveBeenCalledWith(
      expect.objectContaining({ lifecycle_status: "retiring", end_of_life_date: "2027-06-30" }),
    );
  });
});
