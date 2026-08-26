/**
 * ADP-qsw: mechanical guard against the "black screen" class of bug (ADP-cm9) --
 * a module reinventing fetch() without attaching the Keycloak auth header, which
 * 401s silently in any real (auth-enabled) deployment but looks completely fine
 * under this project's own test/CI posture (VITE_AUTH_ENABLED=false everywhere),
 * so nothing else would ever catch it before it reaches a user.
 *
 * Mirrors tests/unit/agents/test_toolkit_boundary.py's / test_tools_boundary.py's
 * mechanical-enforcement approach on the backend (walk the real source, don't
 * trust a convention) -- adapted to a proportionate text scan rather than a full
 * TS AST walk, per this bead's own "a scan-based unit test is proportionate and
 * fast" recommendation. client.ts's own apiGet/apiMutation are the sanctioned
 * fetch() call sites; every OTHER file that calls fetch() directly (needed for
 * a non-JSON response -- a Blob export, an SSE stream -- that apiGet/apiMutation
 * can't handle) must reference getAuthHeader() somewhere in that same file, or
 * this test fails and names the offending file.
 */

import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const SRC_ROOT = join(__dirname, "..");

// The canonical implementation -- the only file allowed to call fetch()
// without itself referencing getAuthHeader() as a "check" (it's the
// definition site: apiGet/apiMutation call getAuthHeader() internally, and
// every other file's own safety is that it also calls getAuthHeader()).
const EXEMPT_FILES = new Set(["api/client.ts"]);

// A bare fetch( call, word-boundary anchored so it does not match a
// same-named wrapper like apiFetch( (application.ts's own helper) -- those
// are exactly the sanctioned indirection this guard wants to allow.
const RAW_FETCH_RE = /\bfetch\(/;
const AUTH_HEADER_RE = /getAuthHeader/;

function collectSourceFiles(dir: string): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir)) {
    const full = join(dir, entry);
    const stat = statSync(full);
    if (stat.isDirectory()) {
      out.push(...collectSourceFiles(full));
      continue;
    }
    if (!/\.(ts|tsx)$/.test(entry)) continue;
    if (/\.test\.(ts|tsx)$/.test(entry)) continue; // test doubles are not production code paths
    out.push(full);
  }
  return out;
}

describe("fetch() auth boundary (ADP-qsw)", () => {
  it("every file that calls fetch() directly also references getAuthHeader()", () => {
    const offenders: string[] = [];

    for (const file of collectSourceFiles(SRC_ROOT)) {
      const relPath = file.slice(SRC_ROOT.length + 1).replace(/\\/g, "/");
      if (EXEMPT_FILES.has(relPath)) continue;

      const content = readFileSync(file, "utf-8");
      if (!RAW_FETCH_RE.test(content)) continue;
      if (!AUTH_HEADER_RE.test(content)) offenders.push(relPath);
    }

    expect(
      offenders,
      `File(s) call fetch() directly without referencing getAuthHeader() anywhere in the same ` +
        `file -- this is the exact class of bug that caused the ADP-cm9 "black screen" incident ` +
        `(a request silently missing its Bearer token, 401ing only once auth is actually enabled). ` +
        `Route through apiGet/apiMutation (web/src/api/client.ts) instead, or if a raw fetch() is ` +
        `genuinely required (a Blob/SSE response apiGet/apiMutation can't handle), attach ` +
        `getAuthHeader() explicitly, mirroring web/src/api/application.ts's own apiFetch() helper. ` +
        `Offending file(s): ${offenders.join(", ") || "(none)"}`,
    ).toEqual([]);
  });
});
