// 051-strategy-landing-card: OverviewPage's fifth "Strategy" domain card.
// Mocks every hooks module OverviewPage calls (vi.mock(hooks-module),
// mirroring web/src/chat/ChatPanel.test.tsx's convention) rather than
// standing up a QueryClientProvider + real fetch mocking, since this page
// calls eight hooks across five modules unconditionally on every render.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OverviewPage from "./OverviewPage";
import * as applicationApi from "../api/application";
import * as businessApi from "../api/business";
import * as knowledgeApi from "../api/knowledge";
import * as portfolioApi from "../api/portfolio";
import * as strategyApi from "../api/strategy";
import * as complianceApi from "../api/compliance";

vi.mock("../api/application");
vi.mock("../api/business");
vi.mock("../api/knowledge");
vi.mock("../api/portfolio");
vi.mock("../api/strategy");
vi.mock("../api/compliance");

const mockedApplicationApi = vi.mocked(applicationApi);
const mockedBusinessApi = vi.mocked(businessApi);
const mockedKnowledgeApi = vi.mocked(knowledgeApi);
const mockedPortfolioApi = vi.mocked(portfolioApi);
const mockedStrategyApi = vi.mocked(strategyApi);
const mockedComplianceApi = vi.mocked(complianceApi);

function listResult<T>(items: T[], total?: number) {
  return {
    data: { items, total: total ?? items.length },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof businessApi.useCapabilities>;
}

const DEFAULT_SUMMARY = {
  total_objectives: 12,
  total_themes: 4,
  linked_count: 9,
  unlinked_count: 3,
  current_period_count: 5,
  upcoming_count: 4,
  past_due_count: 3,
  // 918-strategy-rollups
  proposed_count: 3,
  active_count: 5,
  at_risk_count: 2,
  achieved_count: 1,
  abandoned_count: 1,
  initiative_count: 6,
};

beforeEach(() => {
  vi.clearAllMocks();
  mockedApplicationApi.useApplications.mockReturnValue(
    listResult([]) as unknown as ReturnType<typeof applicationApi.useApplications>,
  );
  mockedApplicationApi.useTechCaps.mockReturnValue(
    listResult([]) as unknown as ReturnType<typeof applicationApi.useTechCaps>,
  );
  mockedApplicationApi.useIntegrations.mockReturnValue(
    listResult([]) as unknown as ReturnType<typeof applicationApi.useIntegrations>,
  );
  mockedBusinessApi.useCapabilities.mockReturnValue(listResult([]));
  mockedBusinessApi.useValueStreams.mockReturnValue(
    listResult([]) as unknown as ReturnType<typeof businessApi.useValueStreams>,
  );
  mockedBusinessApi.useDomains.mockReturnValue(
    listResult([]) as unknown as ReturnType<typeof businessApi.useDomains>,
  );
  mockedKnowledgeApi.useKnowledgeItems.mockReturnValue(
    listResult([]) as unknown as ReturnType<typeof knowledgeApi.useKnowledgeItems>,
  );
  mockedPortfolioApi.usePortfolioSummary.mockReturnValue({
    data: { total_designs: 0, by_status: {}, overdue_review_count: 0 },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof portfolioApi.usePortfolioSummary>);
  mockedStrategyApi.useStrategySummary.mockReturnValue({
    data: DEFAULT_SUMMARY,
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof strategyApi.useStrategySummary>);
  // 924-compliance-rollup-reporting: OverviewPage now calls useComplianceSummary()
  // unconditionally too -- default it here so every pre-existing test above is unaffected.
  mockedComplianceApi.useComplianceSummary.mockReturnValue({
    data: { framework_count: 3, coverage_percent: 60, at_risk_count: 2 },
    isLoading: false,
    isError: false,
  } as unknown as ReturnType<typeof complianceApi.useComplianceSummary>);
});

describe("OverviewPage: Strategy domain card (051-strategy-landing-card)", () => {
  it("renders a Strategy card with the mocked objective/theme counts", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    expect(screen.getByText("Strategy")).toBeTruthy();
    expect(screen.getByText("12")).toBeTruthy(); // total_objectives
    expect(screen.getByText("4")).toBeTruthy(); // total_themes
  });

  it("navigates to the strategy view when its deep-link tile is clicked", async () => {
    const onNavigate = vi.fn();
    const user = userEvent.setup();
    render(<OverviewPage onNavigate={onNavigate} />);

    await user.click(screen.getByTitle("Open Objectives"));

    expect(onNavigate).toHaveBeenCalledWith("strategy");
  });

  it("never renders a progress-percentage element on the Strategy card (FR-003)", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    // Scoped to the Strategy card itself (924-compliance-rollup-reporting's own Compliance card
    // legitimately renders a "%" coverage figure elsewhere on the page now).
    const strategyCard = screen.getByText("Strategy").closest(".ovw-dcard") as HTMLElement;
    expect(within(strategyCard).queryByText(/%/)).toBeNull();
    expect(within(strategyCard).queryByText(/progress/i)).toBeNull();
  });
});

describe("OverviewPage: Strategy card linkage-health bar (US2)", () => {
  it("renders the linked/unlinked split from the summary data", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    expect(screen.getByText(/9 linked/i)).toBeTruthy();
    expect(screen.getByText(/3 unlinked/i)).toBeTruthy();
  });

  it("flags the unlinked segment as a warning when unlinked_count > 0", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    const unlinkedLabel = screen.getByText(/3 unlinked/i);
    expect(unlinkedLabel.closest(".alert")).not.toBeNull();
  });

  it("shows no warning treatment when unlinked_count is 0", () => {
    mockedStrategyApi.useStrategySummary.mockReturnValue({
      data: { ...DEFAULT_SUMMARY, linked_count: 12, unlinked_count: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useStrategySummary>);

    render(<OverviewPage onNavigate={vi.fn()} />);

    const unlinkedLabel = screen.getByText(/0 unlinked/i);
    expect(unlinkedLabel.closest(".alert")).toBeNull();
  });
});

describe("OverviewPage: Strategy card fiscal-period breakdown (US3)", () => {
  it("renders the current/upcoming/past-due split from the summary data", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    expect(screen.getByText(/5 current/i)).toBeTruthy();
    expect(screen.getByText(/4 upcoming/i)).toBeTruthy();
    expect(screen.getByText(/3 past due/i)).toBeTruthy();
  });

  it("flags the past-due bucket as a warning when past_due_count > 0", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    const pastDueLabel = screen.getByText(/3 past due/i);
    expect(pastDueLabel.closest(".alert")).not.toBeNull();
  });

  it("shows no warning treatment when past_due_count is 0", () => {
    mockedStrategyApi.useStrategySummary.mockReturnValue({
      data: { ...DEFAULT_SUMMARY, current_period_count: 8, upcoming_count: 4, past_due_count: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useStrategySummary>);

    render(<OverviewPage onNavigate={vi.fn()} />);

    const pastDueLabel = screen.getByText(/0 past due/i);
    expect(pastDueLabel.closest(".alert")).toBeNull();
  });
});

describe("OverviewPage: Strategy card status breakdown + initiative count (918-strategy-rollups)", () => {
  // The Governance & Standards tile elsewhere on this page also renders
  // "N at risk" text (application-level risk, an unrelated concept that
  // happens to share the same phrasing) -- scope queries to the Strategy
  // card's own container to avoid colliding with it.
  function strategyCard() {
    return screen.getByText("Strategy").closest(".ovw-dcard") as HTMLElement;
  }

  it("renders the initiative count as a metric tile", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    expect(within(strategyCard()).getByText("6")).toBeTruthy(); // initiative_count
    expect(within(strategyCard()).getByText("Initiatives")).toBeTruthy();
  });

  it("renders the at-risk/on-track split from the summary data", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    expect(within(strategyCard()).getByText(/2 at risk/i)).toBeTruthy();
    expect(within(strategyCard()).getByText(/6 on track/i)).toBeTruthy(); // active_count + achieved_count
  });

  it("flags the at-risk segment as a warning when at_risk_count > 0", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    const atRiskLabel = within(strategyCard()).getByText(/2 at risk/i);
    expect(atRiskLabel.closest(".alert")).not.toBeNull();
  });

  it("shows no warning treatment when at_risk_count is 0", () => {
    mockedStrategyApi.useStrategySummary.mockReturnValue({
      data: { ...DEFAULT_SUMMARY, at_risk_count: 0, active_count: 7 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof strategyApi.useStrategySummary>);

    render(<OverviewPage onNavigate={vi.fn()} />);

    const atRiskLabel = within(strategyCard()).getByText(/0 at risk/i);
    expect(atRiskLabel.closest(".alert")).toBeNull();
  });
});

describe("OverviewPage: Compliance domain card (924-compliance-rollup-reporting US2)", () => {
  function complianceCard() {
    return screen.getByText("Compliance").closest(".ovw-dcard") as HTMLElement;
  }

  it("renders a Compliance card with the mocked framework count, coverage %, and at-risk count", () => {
    render(<OverviewPage onNavigate={vi.fn()} />);

    const card = complianceCard();
    expect(within(card).getByText("3")).toBeTruthy(); // framework_count
    expect(within(card).getByText("60%")).toBeTruthy(); // coverage_percent
    expect(within(card).getByText("2")).toBeTruthy(); // at_risk_count
    expect(within(card).getByText("Frameworks", { selector: ".m-l" })).toBeTruthy();
    expect(within(card).getByText("Coverage")).toBeTruthy();
    expect(within(card).getByText("At risk")).toBeTruthy();
  });

  it("shows '—' for coverage, never a misleading 0%, when coverage_percent is null (FR-009)", () => {
    mockedComplianceApi.useComplianceSummary.mockReturnValue({
      data: { framework_count: 0, coverage_percent: null, at_risk_count: 0 },
      isLoading: false,
      isError: false,
    } as unknown as ReturnType<typeof complianceApi.useComplianceSummary>);

    render(<OverviewPage onNavigate={vi.fn()} />);

    const card = complianceCard();
    expect(within(card).getByText("—")).toBeTruthy();
    expect(within(card).queryByText("0%")).toBeNull();
  });

  it("navigates to the compliance view (not governance) when its deep-link tile is clicked", async () => {
    const onNavigate = vi.fn();
    const user = userEvent.setup();
    render(<OverviewPage onNavigate={onNavigate} />);

    await user.click(screen.getByTitle("Open Frameworks"));

    expect(onNavigate).toHaveBeenCalledWith("compliance");
    expect(onNavigate).not.toHaveBeenCalledWith("governance");
  });
});
