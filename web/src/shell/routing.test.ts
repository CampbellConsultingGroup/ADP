import { describe, expect, it } from "vitest";
import { formatRoute, parseRoute, type AppRoute } from "./routing";

describe("hash routing (ADP-blp.53)", () => {
  const cases: [string, AppRoute][] = [
    ["#/overview", { view: "overview", entity: null, designId: null }],
    ["#/business/cap-1", { view: "business", entity: { kind: "business_capability", id: "cap-1" }, designId: null }],
    ["#/applications/APP-7", { view: "applications", entity: { kind: "application", id: "APP-7" }, designId: null }],
    [
      "#/applications/capabilities/ac-3",
      { view: "applications", entity: { kind: "application_capability", id: "ac-3" }, designId: null },
    ],
    ["#/patterns/adoptions/ad-9", { view: "patterns", entity: { kind: "adoption", id: "ad-9" }, designId: null }],
    ["#/agents/ag-2", { view: "agents", entity: { kind: "agent", id: "ag-2" }, designId: null }],
    ["#/intake?design=DSN-001", { view: "intake", entity: null, designId: "DSN-001" }],
    ["#/canvas-v2?design=DSN-POS", { view: "canvas-v2", entity: null, designId: "DSN-POS" }],
  ];

  it.each(cases)("%s round-trips", (hash, route) => {
    expect(parseRoute(hash)).toEqual(route);
    expect(formatRoute(route)).toBe(hash);
  });

  it("ignores an empty or unknown hash", () => {
    expect(parseRoute("")).toBeNull();
    expect(parseRoute("#")).toBeNull();
    expect(parseRoute("#/nowhere")).toBeNull();
    expect(parseRoute("#state=abc&code=xyz")).toBeNull(); // a Keycloak redirect fragment
  });

  it("drops an id on a screen that has no entity route, and encodes ids", () => {
    expect(parseRoute("#/governance/whatever")).toEqual({ view: "governance", entity: null, designId: null });
    expect(formatRoute({ view: "governance", entity: { kind: "agent", id: "x" }, designId: null })).toBe("#/governance");
    const route: AppRoute = { view: "business", entity: { kind: "business_capability", id: "a b/c" }, designId: null };
    expect(parseRoute(formatRoute(route))).toEqual(route);
  });
});
