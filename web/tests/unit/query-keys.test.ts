import { describe, expect, it } from "vitest";
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { QK } from "../../src/api/queryKeys";

/**
 * Every query key starts with a name from src/api/queryKeys.ts (ADP-blp.34).
 *
 * A key typed as a string literal where it is used is how the same endpoint came to be cached
 * under several names, and how a mutation invalidated `["application"]` when the list lived under
 * `["applications"]`.
 */
const SRC = join(__dirname, "../../src");
const SKIP = [/[\\/]api[\\/]generated[\\/]/, /[\\/]diagrams[\\/](core|editor)[\\/]/, /\.test\./];

function walk(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return walk(path);
    return /\.tsx?$/.test(name) && !SKIP.some((re) => re.test(path)) ? [path] : [];
  });
}

describe("query keys", () => {
  it("never start with a string literal", () => {
    const offenders: string[] = [];
    for (const file of walk(SRC)) {
      const text = readFileSync(file, "utf8");
      for (const m of text.matchAll(/queryKey:\s*\[\s*["'`]([^"'`]*)/g)) {
        offenders.push(`${relative(SRC, file)}: "${m[1]}"`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("uses each name once", () => {
    const values = Object.values(QK);
    expect(new Set(values).size).toBe(values.length);
  });
});
