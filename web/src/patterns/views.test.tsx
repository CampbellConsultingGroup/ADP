// 935-pattern-registry US4: read-only flowchart rendering of pattern views.

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as patternsApi from "../api/patterns";
import FlowchartView, { flowchartToSvg } from "./FlowchartView";
import PatternViews from "./PatternViews";

vi.mock("../api/patterns", async (orig) => {
  const actual = await orig<typeof import("../api/patterns")>();
  return { ...actual, usePatternView: vi.fn() };
});
const api = vi.mocked(patternsApi);

const GOLDEN = readFileSync(
  resolve(process.cwd(), "..", "tests", "unit", "patterns", "goldens",
    "structure__ea.integration.domain-event-backbone_1.0.0.mmd"),
  "utf-8",
);

beforeEach(() => {
  vi.clearAllMocks();
  api.usePatternView.mockReturnValue({
    data: { view: "structure", flowchart: GOLDEN, digest: "d", generated_at: "", truncated: [] },
    isLoading: false,
    error: null,
  } as never);
});

describe("flowchartToSvg", () => {
  it("renders a golden to SVG with the escaped labels", () => {
    const out = flowchartToSvg(GOLDEN);
    expect("svg" in out).toBe(true);
    if ("svg" in out) {
      expect(out.svg.startsWith("<svg")).toBe(true);
      expect(out.svg).toContain("Domain App");
    }
  });

  it("escapes markup in labels rather than emitting it", () => {
    const out = flowchartToSvg("flowchart LR\n    a[x &lt; <b>bold</b>]\n");
    expect("svg" in out).toBe(true);
    if ("svg" in out) expect(out.svg).not.toContain("<b>");
  });

  it("reports unparsable text", () => {
    const out = flowchartToSvg("flowchart LR\n    a -.-x b\n");
    expect("error" in out).toBe(true);
  });
});

describe("FlowchartView", () => {
  it("mounts the drawing as an image and shows copyable source", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    Object.assign(navigator, { clipboard: { writeText } });
    render(<FlowchartView flowchart={GOLDEN} title="Pattern structure" truncated={["catalog limited to 40 patterns"]} />);
    const img = screen.getByRole("img", { name: "Pattern structure" }) as HTMLImageElement;
    expect(img.src.startsWith("data:image/svg+xml")).toBe(true);
    expect(screen.getByText("catalog limited to 40 patterns")).toBeTruthy();
    expect(screen.getByLabelText("Flowchart source").textContent).toBe(GOLDEN);
    await userEvent.click(screen.getByText("Flowchart source"));
    await userEvent.click(screen.getByRole("button", { name: "Copy" }));
    expect(writeText).toHaveBeenCalledWith(GOLDEN);
  });

  it("shows an error instead of a broken drawing", () => {
    render(<FlowchartView flowchart={"not a flowchart"} title="x" />);
    expect(screen.getByRole("alert").textContent).toContain("could not be drawn");
  });
});

describe("PatternViews", () => {
  it("switches view and catalog depth", async () => {
    render(<PatternViews patternKey="ea.a.b" version="1.0.0" />);
    expect(api.usePatternView).toHaveBeenLastCalledWith("ea.a.b", "1.0.0", "structure", 1);
    await userEvent.selectOptions(screen.getByLabelText("View"), "catalog");
    await userEvent.selectOptions(screen.getByLabelText("Depth"), "2");
    expect(api.usePatternView).toHaveBeenLastCalledWith("ea.a.b", "1.0.0", "catalog", 2);
    expect(screen.queryByLabelText("Depth")).toBeTruthy();
    await userEvent.selectOptions(screen.getByLabelText("View"), "traceability");
    expect(screen.queryByLabelText("Depth")).toBeNull();
  });
});
