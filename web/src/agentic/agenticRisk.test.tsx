// 944-agent-traceability (ADP-12x, US3): the risk badge and factor list.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiskBadge, RiskFactors } from "./agenticRisk";

describe("RiskBadge", () => {
  it.each([
    ["high", "High risk"],
    ["medium", "Medium risk"],
    ["low", "Low risk"],
  ] as const)("labels %s", (band, label) => {
    render(<RiskBadge band={band} />);
    expect(screen.getByText(label)).toBeTruthy();
  });

  it("shows No agents for a solution without counted agents", () => {
    render(<RiskBadge band={null} />);
    expect(screen.getByText("No agents")).toBeTruthy();
  });
});

describe("RiskFactors", () => {
  it("lists the factors, a missing classification and what isn't considered", () => {
    render(
      <RiskFactors
        risk={{
          band: "high",
          factors: [
            { code: "autonomy", label: "autonomy 4" },
            { code: "no_human_approval", label: "no human approval" },
          ],
          missing: ["data_classification"],
          not_considered: ["tool_side_effects"],
        }}
      />,
    );
    const text = screen.getByText(/autonomy 4/).textContent ?? "";
    expect(text).toContain("autonomy 4, no human approval");
    expect(text).toContain("data classification not recorded");
    expect(text).toContain("Tool side effects are not yet considered.");
  });

  it("says when nothing elevates the band", () => {
    render(<RiskFactors risk={{ band: "low", factors: [], missing: [], not_considered: ["tool_side_effects"] }} />);
    expect(screen.getByText(/no elevating factors/)).toBeTruthy();
  });
});
