import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Alert, Field, Loading } from "./primitives";

describe("shared feedback and form primitives (ADP-blp.46)", () => {
  it("Loading is announced as status and keeps the usual text", () => {
    render(<Loading />);
    expect(screen.getByRole("status").textContent).toBe("Loading…");
  });

  it("Alert announces problems as alerts and the rest as status", () => {
    const { rerender } = render(<Alert tone="crit">Could not save</Alert>);
    expect(screen.getByRole("alert").textContent).toBe("Could not save");
    rerender(<Alert tone="good">Saved</Alert>);
    expect(screen.getByRole("status").className).toContain("good");
  });

  it("Field ties the label, hint and error to its control", () => {
    render(
      <Field label="Name" required hint="Shown in lists" error="Name is required">
        {(control) => <input {...control} />}
      </Field>,
    );
    const input = screen.getByLabelText(/Name/) as HTMLInputElement;
    expect(input.getAttribute("aria-required")).toBe("true");
    expect(input.required).toBe(false); // the form does its own validation
    expect(input.getAttribute("aria-invalid")).toBe("true");
    const described = input.getAttribute("aria-describedby")!.split(" ");
    expect(described.map((id) => document.getElementById(id)?.textContent)).toEqual([
      "Shown in lists",
      "Name is required",
    ]);
    expect(screen.getByRole("alert").textContent).toBe("Name is required");
  });

  it("Field without hint or error adds no extra attributes", () => {
    render(<Field label="Owner">{(control) => <input {...control} />}</Field>);
    const input = screen.getByLabelText("Owner");
    expect(input.getAttribute("aria-describedby")).toBeNull();
    expect(input.getAttribute("aria-invalid")).toBeNull();
  });
});
