import { describe, it, expect } from "vitest";
import { getElementStyle } from "../../src/theme/c4-theme";
import type { C4Theme } from "../../src/types";

const mockTheme: C4Theme = {
  version: "1.0.0",
  locked: true,
  styles: {
    person: { fill: "#08427B", stroke: "#073B6F", color: "#ffffff", shape: "actor", font_size: 14, font_weight: "normal" },
    system: { fill: "#1168BD", stroke: "#0E5FA3", color: "#ffffff", shape: "box", font_size: 14, font_weight: "bold" },
    container: { fill: "#438DD5", stroke: "#3C7FC0", color: "#ffffff", shape: "box", font_size: 13, font_weight: "normal" },
    component: { fill: "#85BBE0", stroke: "#78A8CC", color: "#000000", shape: "box", font_size: 12, font_weight: "normal" },
  },
  relationship_style: { stroke: "#707070", stroke_width: 1.5, arrow_end: "open" },
};

describe("getElementStyle", () => {
  it("test_theme_style_by_kind — container returns correct colors", () => {
    const style = getElementStyle("container", mockTheme);
    expect(style.fill).toBe("#438DD5");
    expect(style.stroke).toBe("#3C7FC0");
    expect(style.color).toBe("#ffffff");
  });

  it("returns person style with actor shape", () => {
    const style = getElementStyle("person", mockTheme);
    expect(style.fill).toBe("#08427B");
    expect(style.shape).toBe("actor");
  });

  it("returns default style when theme is null", () => {
    const style = getElementStyle("container", null);
    expect(style.fill).toBe("#888888");
  });

  it("returns default style when theme is undefined", () => {
    const style = getElementStyle("system", undefined);
    expect(style.fill).toBe("#888888");
  });

  it("returns default style when kind is not in theme", () => {
    const emptyTheme: C4Theme = { ...mockTheme, styles: {} };
    const style = getElementStyle("container", emptyTheme);
    expect(style.fill).toBe("#888888");
  });
});
