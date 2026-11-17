import { beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import ApplicationSummary from "./ApplicationSummary";
import * as applicationApi from "../api/application";
import * as complianceApi from "../api/compliance";
import { ApiError } from "../api/client";
import type { Application } from "../api/application";

vi.mock("../api/application", async (orig) => ({
  ...(await orig<typeof import("../api/application")>()),
  useApplicationRisk: vi.fn(),
  useApplicationCost: vi.fn(),
}));
vi.mock("../api/compliance", async (orig) => ({
  ...(await orig<typeof import("../api/compliance")>()),
  useApplicationComplianceMappings: vi.fn(),
}));

const api = vi.mocked(applicationApi);
const comp = vi.mocked(complianceApi);

const APP = {
  id: "a1", name: "Billing", health_score: 2, business_value: 4, time_classification: "Migrate",
  r_strategy: "Replatform", lifecycle_status: "sunset",
} as unknown as Application;

function result(data: unknown, error: unknown = null) {
  return { data, error, isLoading: false } as never;
}

function card(labelText: string): HTMLElement {
  return screen.getByText(labelText).closest(".ui-scorecard") as HTMLElement;
}

beforeEach(() => {
  api.useApplicationRisk.mockReturnValue(
    result({ security_posture: "weak", vulnerability_status: "open_high" }),
  );
  api.useApplicationCost.mockReturnValue(result({ tco: "350000" }));
  comp.useApplicationComplianceMappings.mockReturnValue(
    result({ items: [{ compliance_status: "compliant" }, { compliance_status: "non_compliant" }] }),
  );
});

describe("ApplicationSummary (ADP-blp.59)", () => {
  it("shows every score on one screen", () => {
    render(<ApplicationSummary app={APP} onOpen={vi.fn()} />);
    expect(card("Health").textContent).toContain("2 / 5");
    expect(card("Business value").textContent).toContain("4 / 5");
    expect(card("Disposition").textContent).toContain("Migrate");
    expect(card("Disposition").textContent).toContain("Replatform");
    expect(card("Lifecycle").textContent).toContain("Sunset");
    expect(card("Risk").textContent).toContain("Weak");
    expect(card("Risk").textContent).toContain("open high");
    expect(card("Cost").textContent).toContain("350,000");
    // The worst mapped control decides the headline.
    expect(card("Compliance").textContent).toContain("Non compliant");
    expect(card("Compliance").textContent).toContain("2 controls mapped");
  });

  it("opens the tab that holds the detail", () => {
    const onOpen = vi.fn();
    render(<ApplicationSummary app={APP} onOpen={onOpen} />);
    fireEvent.click(card("Risk"));
    fireEvent.click(card("Cost"));
    fireEvent.click(card("Compliance"));
    expect(onOpen.mock.calls.map((c) => c[0])).toEqual(["risk", "cost", "compliance-mappings"]);
    // Scores held on the application itself are not links.
    expect(card("Health").tagName).toBe("DIV");
  });

  it("says a score is restricted rather than showing an error", () => {
    api.useApplicationRisk.mockReturnValue(result(undefined, new ApiError(403, "forbidden")));
    api.useApplicationCost.mockReturnValue(result(undefined, new ApiError(500, "boom")));
    render(<ApplicationSummary app={APP} onOpen={vi.fn()} />);
    expect(card("Risk").textContent).toContain("Restricted");
    expect(card("Risk").textContent).toContain("Not available to your role");
    expect(card("Cost").textContent).toContain("Could not be loaded");
  });

  it("handles an application with nothing recorded yet", () => {
    api.useApplicationRisk.mockReturnValue(result({ security_posture: null, vulnerability_status: null }));
    api.useApplicationCost.mockReturnValue(result({ tco: "0" }));
    comp.useApplicationComplianceMappings.mockReturnValue(result({ items: [] }));
    const blank = { ...APP, health_score: null, business_value: null, time_classification: null, r_strategy: null };
    render(<ApplicationSummary app={blank as Application} onOpen={vi.fn()} />);
    expect(card("Health").textContent).toContain("Not assessed");
    expect(card("Disposition").textContent).toContain("Not classified");
    expect(card("Risk").textContent).toContain("Not assessed");
    expect(card("Cost").textContent).toContain("Not recorded");
    expect(card("Compliance").textContent).toContain("No controls mapped yet");
  });
});
