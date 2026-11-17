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

import { act, renderHook } from "@testing-library/react";
import { readHashParam, useHashParam, writeHashParam } from "./routing";

describe("page state in the URL (ADP-blp.68)", () => {
  const TABS = ["domains", "capabilities", "heatmap"] as const;

  it("reads the tab from the URL and falls back for a missing or unknown value", () => {
    window.history.replaceState(null, "", "#/business?tab=capabilities");
    expect(renderHook(() => useHashParam("tab", TABS, "domains")).result.current[0]).toBe("capabilities");
    window.history.replaceState(null, "", "#/business?tab=nonsense");
    expect(renderHook(() => useHashParam("tab", TABS, "domains")).result.current[0]).toBe("domains");
    window.history.replaceState(null, "", "#/business");
    expect(renderHook(() => useHashParam("tab", TABS, "domains")).result.current[0]).toBe("domains");
  });

  it("writes the choice into the URL without a new history entry, and omits the default", () => {
    window.history.replaceState(null, "", "#/business?design=DSN-1");
    const before = window.history.length;
    const { result } = renderHook(() => useHashParam("tab", TABS, "domains"));
    act(() => result.current[1]("heatmap"));
    expect(result.current[0]).toBe("heatmap");
    expect(window.location.hash).toBe("#/business?design=DSN-1&tab=heatmap");
    expect(parseRoute(window.location.hash)).toEqual({ view: "business", entity: null, designId: "DSN-1" });
    act(() => result.current[1]("domains"));
    expect(window.location.hash).toBe("#/business?design=DSN-1");
    expect(window.history.length).toBe(before);
  });

  it("follows Back/Forward and leaves a URL with no route alone", () => {
    window.history.replaceState(null, "", "#/business?tab=heatmap");
    const { result } = renderHook(() => useHashParam("tab", TABS, "domains"));
    act(() => {
      window.history.replaceState(null, "", "#/business?tab=capabilities");
      window.dispatchEvent(new PopStateEvent("popstate"));
    });
    expect(result.current[0]).toBe("capabilities");

    window.history.replaceState(null, "", window.location.pathname);
    writeHashParam("tab", "heatmap");
    expect(window.location.hash).toBe("");
    expect(readHashParam("tab")).toBeNull();
  });
});
