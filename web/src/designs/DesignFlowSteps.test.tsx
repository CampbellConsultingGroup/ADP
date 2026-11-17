import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import DesignFlowSteps, { currentStep } from "./DesignFlowSteps";

describe("DesignFlowSteps (ADP-blp.59)", () => {
  it("knows which step each screen is", () => {
    expect(currentStep("intake", "intake")).toBe("describe");
    expect(currentStep("intake", "recommend")).toBe("recommend");
    expect(currentStep("intake", "settings")).toBe("describe");
    expect(currentStep("canvas-v2", "intake")).toBe("design");
    expect(currentStep("designs", "intake")).toBe("validate");
    expect(currentStep("business", "intake")).toBeNull();
  });

  it("marks the current step and links the others to their screens", () => {
    window.history.replaceState(null, "", "#/canvas-v2?design=DSN-1");
    render(<DesignFlowSteps view="canvas-v2" designId="DSN-1" />);
    expect(screen.getByText("Design").closest(".s")?.getAttribute("aria-current")).toBe("step");
    expect(screen.getByRole("link", { name: /Describe/ }).getAttribute("href")).toBe("#/intake?design=DSN-1");
    expect(screen.getByRole("link", { name: /Recommend/ }).getAttribute("href")).toBe(
      "#/intake?design=DSN-1&tab=recommend",
    );
    expect(screen.getByRole("link", { name: /Validate/ }).getAttribute("href")).toBe("#/designs");
    expect(screen.queryByRole("link", { name: /Design Shape/ })).toBeNull(); // the current step is not a link
  });

  it("leaves steps that need a design inactive until one exists", () => {
    window.history.replaceState(null, "", "#/intake");
    render(<DesignFlowSteps view="intake" designId={null} />);
    expect(screen.getByText("Describe").closest(".s")?.getAttribute("aria-current")).toBe("step");
    expect(screen.queryAllByRole("link")).toHaveLength(0);
    expect(screen.getByText("Recommend").closest(".s")?.getAttribute("title")).toBe(
      "Create or open a design first",
    );
  });

  it("is not shown on screens outside the flow", () => {
    const { container } = render(<DesignFlowSteps view="business" designId="DSN-1" />);
    expect(container.firstChild).toBeNull();
  });
});
