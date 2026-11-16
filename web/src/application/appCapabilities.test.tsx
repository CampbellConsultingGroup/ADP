// 937-application-capabilities: catalog tree, warning badge, gaps list, level-filtered pickers,
// reviewer read-only, and the read-only lists shown on other screens.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type React from "react";
import * as acApi from "../api/appCapabilities";
import type { ApplicationCapability, ApplicationCapabilityDetail, AppCapSummary } from "../api/appCapabilities";
import { ApiError } from "../api/client";
import * as auth from "../auth/AuthProvider";
import AppCapabilitiesView, { missingTechGaps } from "./AppCapabilitiesView";
import { businessL3Options, technicalOptions } from "./AppCapDetail";
import { buildAppCapTree } from "./AppCapTree";
import { AppCapSummaryItems, ApplicationRealizes } from "./AppCapSummaryList";
import { AppCapNavContext, canWriteApplications } from "./appCapNav";

vi.mock("../api/appCapabilities", async (orig) => {
  const actual = await orig<typeof import("../api/appCapabilities")>();
  return {
    ...actual,
    useAppCapabilities: vi.fn(),
    useAppCapability: vi.fn(),
    useAppCapsByApplication: vi.fn(),
    useCreateAppCapability: vi.fn(),
    useUpdateAppCapability: vi.fn(),
    useDeleteAppCapability: vi.fn(),
    useAddAppCapLink: vi.fn(),
    useRemoveAppCapLink: vi.fn(),
  };
});
vi.mock("../auth/AuthProvider", () => ({ useAuth: vi.fn() }));
vi.mock("../api/business", () => ({
  useCapabilities: () => ({
    data: {
      items: [
        { id: "b1", name: "Sales & Customer Transactions", level: 1, parent_id: null },
        { id: "b2", name: "In-Store Transaction Management", level: 2, parent_id: "b1" },
        { id: "b3", name: "Accept Payment", level: 3, parent_id: "b2" },
      ],
    },
  }),
}));
vi.mock("../api/client", async (orig) => {
  const actual = await orig<typeof import("../api/client")>();
  return {
    ...actual,
    apiGet: vi.fn(async (path: string) => {
      if (path.includes("technical-capabilities")) {
        return {
          items: [
            { id: "t1", name: "Integration & Data Services", level: 1, parent_id: null },
            { id: "t2", name: "Security", level: 2, parent_id: "t1" },
            { id: "t3", name: "Payment Tokenization (P2PE)", level: 3, parent_id: "t2" },
          ],
        };
      }
      return { items: [{ id: "pos", name: "Store POS" }] };
    }),
  };
});

const api = vi.mocked(acApi);
const useAuth = vi.mocked(auth.useAuth);

function cap(id: string, name: string, level: 1 | 2 | 3, parent: string | null, techCount = 0): ApplicationCapability {
  return {
    id, name, level, parent_id: parent, description: null, created_at: "", updated_at: "",
    business_capability_count: 0, technical_capability_count: techCount, realization_count: 0,
    warnings: level === 3 && techCount === 0 ? ["missing_technical_capability"] : [],
  };
}

const ITEMS = [
  cap("a1", "Transaction Processing", 1, null),
  cap("a2", "Payments", 2, "a1"),
  cap("a3", "Tender Authorization", 3, "a2", 1),
  cap("a4", "Loyalty Points Accrual", 3, "a2", 0),
];

function detail(overrides: Partial<ApplicationCapabilityDetail> = {}): ApplicationCapabilityDetail {
  return {
    ...cap("a4", "Loyalty Points Accrual", 3, "a2", 0),
    path: [{ id: "a1", name: "Transaction Processing", level: 1 }, { id: "a2", name: "Payments", level: 2 }],
    business_capabilities: [], technical_capabilities: [], realized_by: [],
    ...overrides,
  };
}

function mutation(fn = vi.fn().mockResolvedValue({})) {
  return { mutate: vi.fn(), mutateAsync: fn, isPending: false } as never;
}

function wrap(ui: React.ReactElement) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(<QueryClientProvider client={qc}>{ui}</QueryClientProvider>);
}

beforeEach(() => {
  vi.clearAllMocks();
  useAuth.mockReturnValue({ user: { role: "solution_architect" } } as never);
  api.useAppCapabilities.mockReturnValue({ data: { items: ITEMS, total: 4 }, isLoading: false, error: null } as never);
  api.useAppCapability.mockReturnValue({ data: detail(), isLoading: false, error: null } as never);
  for (const hook of [
    api.useCreateAppCapability, api.useUpdateAppCapability, api.useDeleteAppCapability,
    api.useAddAppCapLink, api.useRemoveAppCapLink,
  ]) {
    hook.mockReturnValue(mutation());
  }
});

describe("pure helpers", () => {
  it("builds a sorted tree and lists L3 gaps with their path", () => {
    const tree = buildAppCapTree([...ITEMS].reverse());
    expect(tree[0].children[0].children.map((c) => c.name)).toEqual(["Loyalty Points Accrual", "Tender Authorization"]);
    expect(missingTechGaps(ITEMS)).toEqual([
      { id: "a4", name: "Loyalty Points Accrual", path: "Transaction Processing › Payments" },
    ]);
  });

  it("offers only business L3s and technical L2/L3s", () => {
    expect(businessL3Options([
      { id: "b1", name: "S", level: 1, parent_id: null },
      { id: "b3", name: "Accept Payment", level: 3, parent_id: "b1" },
    ] as never)).toEqual([{ id: "b3", label: "S › Accept Payment" }]);
    expect(technicalOptions([
      { id: "t1", name: "I", level: 1, parent_id: null },
      { id: "t2", name: "Sec", level: 2, parent_id: "t1" },
      { id: "t3", name: "P2PE", level: 3, parent_id: "t2" },
    ]).map((o) => o.id).sort()).toEqual(["t2", "t3"]);
  });

  it("gates writes to WRITE_APPLICATION roles", () => {
    expect(canWriteApplications("technical_architect")).toBe(true);
    expect(canWriteApplications("reviewer")).toBe(false);
    expect(canWriteApplications(null, false)).toBe(true);
    expect(canWriteApplications(null, true)).toBe(false);
  });
});

describe("AppCapabilitiesView", () => {
  it("shows the warning badge only on L3s without a technical capability and no + child on L3", () => {
    wrap(<AppCapabilitiesView />);
    const loyalty = document.querySelector('[data-app-cap-row="a4"]') as HTMLElement;
    const tender = document.querySelector('[data-app-cap-row="a3"]') as HTMLElement;
    expect(within(loyalty).getAllByText(/No technical capability/).length).toBeGreaterThan(0);
    expect(within(tender).queryAllByText(/No technical capability/)).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Add child to Payments" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Add child to Tender Authorization" })).toBeNull();
  });

  it("offers a Redundant tab beside Overlaps, Gaps and Shared (943)", () => {
    wrap(<AppCapabilitiesView />);
    const tabs = screen.getAllByRole("tab").map((t) => t.textContent);
    expect(tabs.slice(-4)).toEqual(["Overlaps", "Gaps", "Shared", "Redundant"]);
  });

  it("lists gaps and opens the selected capability", async () => {
    wrap(<AppCapabilitiesView />);
    await userEvent.click(screen.getByRole("tab", { name: "Missing technical capability (1)" }));
    const gaps = screen.getByLabelText("Missing technical capability");
    await userEvent.click(within(gaps).getByText("Loyalty Points Accrual"));
    expect(api.useAppCapability).toHaveBeenLastCalledWith("a4");
    expect(screen.getByRole("region", { name: "Depends on technical capabilities" })).toBeTruthy();
  });

  it("links a technical capability from a level-filtered picker and shows the server's rule on failure", async () => {
    const add = vi.fn().mockRejectedValue(
      new ApiError(422, "POST failed", { detail: "map to a technical capability at L2 or L3" }),
    );
    api.useAddAppCapLink.mockReturnValue(mutation(add));
    wrap(<AppCapabilitiesView initialId="a4" />);
    const section = screen.getByRole("region", { name: "Depends on technical capabilities" });
    const picker = within(section).getByLabelText("Add depends on technical capabilities");
    await within(section).findByText(/Payment Tokenization/);
    const values = Array.from((picker as HTMLSelectElement).options).map((o) => o.value).sort();
    expect(values).toEqual(["", "t2", "t3"]); // no technical L1
    await userEvent.selectOptions(picker, "t3");
    await userEvent.click(within(section).getByRole("button", { name: "Link" }));
    expect(add).toHaveBeenCalledWith({ id: "a4", kind: "technical", targetId: "t3" });
    expect((await within(section).findByRole("alert")).textContent).toContain("L2 or L3");
  });

  it("explains that L1/L2 are not mapped", () => {
    api.useAppCapability.mockReturnValue({ data: detail({ ...cap("a2", "Payments", 2, "a1"), path: [] }), isLoading: false, error: null } as never);
    wrap(<AppCapabilitiesView initialId="a2" />);
    expect(screen.getByText(/Links are made at Level 3/)).toBeTruthy();
    expect(screen.queryByRole("region", { name: "Supports business capabilities" })).toBeNull();
  });

  it("is read-only for a reviewer", () => {
    useAuth.mockReturnValue({ user: { role: "reviewer" } } as never);
    wrap(<AppCapabilitiesView initialId="a4" />);
    expect(screen.queryByRole("button", { name: "+ Root" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Edit" })).toBeNull();
    expect(screen.queryByRole("button", { name: "Link" })).toBeNull();
    expect(screen.getByText(/raises a governance warning/)).toBeTruthy();
  });
});

describe("read-only lists on other screens", () => {
  const summary: AppCapSummary = {
    id: "a3", name: "Tender Authorization", level: 3,
    path: [{ id: "a1", name: "Transaction Processing", level: 1 }], warnings: [],
    realized_by: [{ id: "pos", name: "Store POS" }],
  };

  it("navigates to the application capability and shows who realizes it", async () => {
    const open = vi.fn();
    render(
      <AppCapNavContext.Provider value={open}>
        <AppCapSummaryItems items={[summary]} showRealizedBy />
      </AppCapNavContext.Provider>,
    );
    expect(screen.getByText(/realized by Store POS/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: /Tender Authorization/ }));
    expect(open).toHaveBeenCalledWith("a3");
  });

  it("lists what an application realizes", () => {
    api.useAppCapsByApplication.mockReturnValue({ data: [summary], isLoading: false } as never);
    render(<ApplicationRealizes appId="pos" />);
    expect(screen.getByRole("region", { name: "Realizes application capabilities" }).textContent).toContain("Tender Authorization");
  });

  it("shows the application's own rationale, geography and hint on its list (943)", () => {
    const classified: AppCapSummary = {
      ...summary,
      realized_by: [
        { id: "pos", name: "Store POS", rationale: "target", geography: { id: "eu", name: "Europe", code: null }, hint: "TIME says Migrate" },
        { id: "ecom", name: "Commerce Cloud", rationale: "redundant", geography: null, hint: null },
      ],
    };
    api.useAppCapsByApplication.mockReturnValue({ data: [classified], isLoading: false } as never);
    render(<ApplicationRealizes appId="pos" />);
    const region = screen.getByRole("region", { name: "Realizes application capabilities" });
    expect(region.textContent).toContain("Target");
    expect(region.textContent).toContain("Europe");
    expect(region.textContent).toContain("TIME says Migrate");
    expect(region.textContent).not.toContain("Redundant");
  });

  it("names each realizing application's rationale on business capability rows (943)", () => {
    const classified: AppCapSummary = {
      ...summary,
      realized_by: [
        { id: "pos", name: "Store POS", rationale: "target", geography: null },
        { id: "ecom", name: "Commerce Cloud", rationale: "tactical", geography: { id: "am", name: "Americas", code: null } },
        { id: "x", name: "Old Till", rationale: null },
      ],
    };
    render(<AppCapSummaryItems items={[classified]} showRealizedBy />);
    expect(screen.getByText(/realized by Store POS \(Target\), Commerce Cloud \(Tactical, Americas\), Old Till/)).toBeTruthy();
  });
});
