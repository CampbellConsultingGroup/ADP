import { describe, expect, it } from "vitest";
import * as tones from "./tones";

const ALL = Object.entries(tones) as [string, Record<string, string>][];

describe("status tones (ADP-blp.49)", () => {
  it("only uses the five defined tones", () => {
    const allowed = new Set(["good", "warn", "crit", "info", "neutral"]);
    for (const [name, map] of ALL) {
      for (const [status, tone] of Object.entries(map)) {
        expect(allowed.has(tone), `${name}.${status}`).toBe(true);
      }
    }
  });

  it("never shows an ended state as critical", () => {
    const ended = ["decommissioned", "abandoned", "retired", "not_applicable", "draft"];
    for (const [name, map] of ALL) {
      for (const status of ended) {
        if (status in map) expect(map[status], `${name}.${status}`).toBe("neutral");
      }
    }
  });

  it("uses the same tone for the same word everywhere", () => {
    const seen = new Map<string, string>();
    // "proposed" is the one deliberate exception: a proposed objective has not started.
    const exceptions = new Set(["OBJECTIVE_STATUS_TONES.proposed"]);
    for (const [name, map] of ALL) {
      for (const [status, tone] of Object.entries(map)) {
        if (exceptions.has(`${name}.${status}`)) continue;
        const earlier = seen.get(status);
        if (earlier !== undefined) expect(tone, `${name}.${status}`).toBe(earlier);
        seen.set(status, tone);
      }
    }
  });
});
