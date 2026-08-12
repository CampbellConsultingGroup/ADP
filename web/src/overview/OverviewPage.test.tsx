// 051-strategy-landing-card: OverviewPage's fifth "Strategy" domain card.
// Mocks every hooks module OverviewPage calls (vi.mock(hooks-module),
// mirroring web/src/chat/ChatPanel.test.tsx's convention) rather than
// standing up a QueryClientProvider + real fetch mocking, since this page
// calls eight hooks across five modules unconditionally on every render.

import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import OverviewPage from "./OverviewPage";
import * as applicationApi from "../api/application";
import * as businessApi from "../api/business";
import * as knowledgeApi from "../api/knowledge";
import * as portfolioApi from "../api/portfolio";
import * as strategyApi from "../api/strategy";

vi.mock("../api/application");
vi.mock("../api/business");
vi.mock("../api/knowledge");
vi.mock("../api/portfolio");
vi.mock("../api/strategy");

const mockedApplicationApi = vi.mocked(applicationApi);
const mockedBusinessApi = vi.mocked(businessApi);
const mockedKnowledgeApi = vi.mocked(knowledgeApi);
const mockedPortfolioApi = vi.mocked(portfolioApi);
const mockedStrategyApi = vi.mocked(strategyApi);

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

    expect(screen.queryByText(/%/)).toBeNull();
    expect(screen.queryByText(/progress/i)).toBeNull();
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
