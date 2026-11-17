import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";

/**
 * Every `var(--name)` used in the app must be defined somewhere (ADP-blp.43).
 *
 * An undefined custom property does not fail loudly: the declaration is dropped and the element
 * falls back to an inherited or default value. `--text-secondary`, `--text`, `--error` and
 * `--danger` were used in about 65 places without ever being defined.
 */
const SRC = join(__dirname, "../../src");

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return walk(path);
    return /\.(css|tsx|ts)$/.test(name) && !/\.test\./.test(name) ? [path] : [];
  });
}

describe("CSS custom properties", () => {
  it("are all defined (in a stylesheet, or set inline by a component)", () => {
    const defined = new Set<string>();
    const used = new Map<string, string>();
    for (const file of walk(SRC)) {
      const text = readFileSync(file, "utf8");
      // `--name: value` in CSS, or `["--name" as string]: value` set inline in TSX.
      for (const m of text.matchAll(/(--[a-zA-Z0-9-]+)\s*:/g)) defined.add(m[1]);
      for (const m of text.matchAll(/["'](--[a-zA-Z0-9-]+)["']/g)) defined.add(m[1]);
      for (const m of text.matchAll(/var\(\s*(--[a-zA-Z0-9-]+)/g)) {
        if (!used.has(m[1])) used.set(m[1], file.slice(SRC.length + 1));
      }
    }
    const undefinedVars = [...used].filter(([name]) => !defined.has(name));
    expect(undefinedVars).toEqual([]);
  });
});
