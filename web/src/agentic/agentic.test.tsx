// 933-agent-registry (ADP-hii): component tests for the agent registry UI. Mirrors
// RiskPanel.test.tsx's vi.mock(hooks-module) convention; plain Testing Library queries only (no
// jest-dom matchers are configured in this project).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as agenticApi from "../api/agentic";
import type { Agent, AgentDetail as AgentDetailType, SolutionAgent } from "../api/agentic";
import AgentForm from "./AgentForm";
import AgentDetail from "./AgentDetail";
import AgentsPage from "./AgentsPage";
import SolutionAgentsPanel from "./SolutionAgentsPanel";
import { costLabel } from "./autonomy";

vi.mock("../api/agentic");
const api = vi.mocked(agenticApi);

function agent(overrides: Partial<Agent> = {}): Agent {
  return {
    id: "ag-1",
    name: "Claims Triage",
    description: null,
    owner: "Claims Platform",
    lifecycle_status: "active",
    model_provider: "Anthropic",
    model_id: "claude-sonnet-5-5",
    model_version: null,
    framework: "Claude Agent SDK",
    prompt_ref: "triage@v7",
    autonomy_level: 2,
    human_approval: "on_irreversible",
    data_classification_max: "confidential",
    a2a_card_url: null,
    est_cost_per_run: "0.0420",
    runs_per_month: 1000,
    cost_visible: true,
    external_registry_ref: null,
    solution_count: 0,
    created_at: "2026-11-13T00:00:00Z",
    updated_at: "2026-11-13T00:00:00Z",
    ...overrides,
  };
}

function mutation(mutateAsync = vi.fn().mockResolvedValue({})) {
  return { mutateAsync, isPending: false } as never;
}

beforeEach(() => {
  vi.clearAllMocks();
  api.errorDetail.mockImplementation((err: unknown) => (err instanceof Error ? err.message : String(err)));
  for (const hook of [
    "useCreateAgent",
    "useUpdateAgent",
    "useDeleteAgent",
    "useAddSolutionAgent",
    "useUpdateSolutionAgentRole",
    "useReorderSolutionAgents",
    "useRemoveSolutionAgent",
  ] as const) {
    api[hook].mockReturnValue(mutation());
  }
});

// ── AgentForm ─────────────────────────────────────────────────────────────────

describe("AgentForm", () => {
  it("shows the meaning of the selected autonomy level and submits typed values", async () => {
    const onSubmit = vi.fn();
    render(<AgentForm onSubmit={onSubmit} onCancel={vi.fn()} />);
    await userEvent.type(screen.getByLabelText(/^Name/), "  Policy Lookup ");
    await userEvent.selectOptions(screen.getByLabelText("Autonomy level"), "3");
    expect(screen.getByText(/reviewed after the fact/)).toBeTruthy();
    await userEvent.type(screen.getByLabelText(/Prompt version reference/), "policy@v2");
    await userEvent.type(screen.getByLabelText(/Est. runs per month/), "500");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
    const body = onSubmit.mock.calls[0][0];
    expect(body).toMatchObject({
      name: "Policy Lookup",
      autonomy_level: 3,
      prompt_ref: "policy@v2",
      runs_per_month: 500,
      human_approval: "on_write",
    });
    expect("est_cost_per_run" in body).toBe(false); // never set, so not sent
  });

  it("blocks a non-http Agent Card URL and a blank name", async () => {
    const onSubmit = vi.fn();
    render(<AgentForm onSubmit={onSubmit} onCancel={vi.fn()} />);
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("alert").textContent).toMatch(/Name is required/);
    await userEvent.type(screen.getByLabelText(/^Name/), "X");
    await userEvent.type(screen.getByLabelText(/Agent Card URL/), "javascript:alert(1)");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(screen.getByRole("alert").textContent).toMatch(/http/);
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("hides cost inputs and never sends cost when cost is not visible", async () => {
    const onSubmit = vi.fn();
    render(
      <AgentForm
        initial={agent({ cost_visible: false, est_cost_per_run: null, runs_per_month: null })}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.queryByLabelText(/Est. cost per run/)).toBeNull();
    expect(screen.getByText(/restricted for your role/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Save" }));
    const body = onSubmit.mock.calls[0][0];
    expect("est_cost_per_run" in body).toBe(false);
    expect("runs_per_month" in body).toBe(false);
  });
});

describe("costLabel", () => {
  it("distinguishes restricted from not estimated", () => {
    expect(costLabel(null, false)).toBe("Restricted");
    expect(costLabel(null, true)).toBe("Not estimated");
    expect(costLabel("0.5", true, "$")).toBe("$0.5");
  });
});

// ── SolutionAgentsPanel ───────────────────────────────────────────────────────

describe("SolutionAgentsPanel", () => {
  const members: SolutionAgent[] = [
    { agent: agent({ id: "a", name: "Orchestrator" }), role: "orchestrator", position: 0 },
    { agent: agent({ id: "b", name: "Worker" }), role: "worker", position: 1 },
  ];

  beforeEach(() => {
    api.useSolutionAgents.mockReturnValue({ data: { items: members, total: 2 }, isLoading: false } as never);
    api.useAgents.mockReturnValue({
      data: { items: [members[0].agent, members[1].agent, agent({ id: "c", name: "Spare" })], total: 3 },
    } as never);
  });

  it("lists members in order and only offers non-members to add", async () => {
    render(<SolutionAgentsPanel appId="app-1" />);
    const rows = screen.getAllByRole("row").slice(1);
    expect(rows.map((r) => within(r).getAllByRole("cell")[1].textContent)).toEqual(["Orchestrator", "Worker"]);
    const picker = screen.getByLabelText("Agent to add") as HTMLSelectElement;
    expect(Array.from(picker.options).map((o) => o.textContent)).toEqual(["Add an existing agent…", "Spare"]);
  });

  it("adds, reorders, re-roles and removes through the hooks", async () => {
    const add = vi.fn().mockResolvedValue({});
    const reorder = vi.fn().mockResolvedValue({});
    const role = vi.fn().mockResolvedValue({});
    const remove = vi.fn().mockResolvedValue({});
    api.useAddSolutionAgent.mockReturnValue(mutation(add));
    api.useReorderSolutionAgents.mockReturnValue(mutation(reorder));
    api.useUpdateSolutionAgentRole.mockReturnValue(mutation(role));
    api.useRemoveSolutionAgent.mockReturnValue(mutation(remove));
    render(<SolutionAgentsPanel appId="app-1" />);

    await userEvent.selectOptions(screen.getByLabelText("Agent to add"), "c");
    await userEvent.selectOptions(screen.getByLabelText("Role for new member"), "reviewer");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect(add).toHaveBeenCalledWith({ agent_id: "c", role: "reviewer" });

    await userEvent.click(screen.getByLabelText("Move Worker up"));
    expect(reorder).toHaveBeenCalledWith(["b", "a"]);

    await userEvent.selectOptions(screen.getByLabelText("Role for Worker"), "router");
    expect(role).toHaveBeenCalledWith({ agentId: "b", role: "router" });

    await userEvent.click(screen.getByLabelText("Remove Orchestrator"));
    expect(remove).toHaveBeenCalledWith("a");
  });

  it("shows the server's reason when adding fails", async () => {
    api.useAddSolutionAgent.mockReturnValue(mutation(vi.fn().mockRejectedValue(new Error("already part of solution"))));
    render(<SolutionAgentsPanel appId="app-1" />);
    await userEvent.selectOptions(screen.getByLabelText("Agent to add"), "c");
    await userEvent.click(screen.getByRole("button", { name: "Add" }));
    expect((await screen.findByRole("alert")).textContent).toMatch(/already part of solution/);
  });
});

// ── AgentsPage / AgentDetail ──────────────────────────────────────────────────

describe("AgentsPage", () => {
  it("lists agents with solution counts and an Unassigned badge, and passes filters", async () => {
    api.useAgents.mockReturnValue({
      data: {
        items: [agent({ id: "a", name: "Shared", solution_count: 2 }), agent({ id: "b", name: "Lonely", model_provider: "OpenAI" })],
        total: 2,
      },
      isLoading: false,
    } as never);
    render(<AgentsPage />);
    expect(screen.getByText("Shared")).toBeTruthy();
    expect(screen.getByText("Unassigned")).toBeTruthy();
    expect(screen.getByText("2")).toBeTruthy();

    await userEvent.selectOptions(screen.getByLabelText("Minimum autonomy"), "3");
    expect(api.useAgents.mock.calls.some(([f]) => (f as { autonomy_min?: number } | undefined)?.autonomy_min === 3)).toBe(true);
    const providers = screen.getByLabelText("Model provider") as HTMLSelectElement;
    expect(Array.from(providers.options).map((o) => o.value)).toEqual(["", "Anthropic", "OpenAI"]);
  });
});

describe("AgentDetail", () => {
  function mockDetail(overrides: Partial<AgentDetailType>) {
    api.useAgent.mockReturnValue({
      data: { ...agent(), solutions: [], ...overrides },
      isLoading: false,
    } as never);
  }

  it("lists every solution with its role and opens one", async () => {
    const onOpen = vi.fn();
    mockDetail({
      solution_count: 2,
      solutions: [
        { app_id: "x", app_name: "Claims", role: "worker", position: 0 },
        { app_id: "y", app_name: "Fraud", role: "reviewer", position: 1 },
      ],
    });
    render(<AgentDetail agentId="ag-1" onBack={vi.fn()} onOpenSolution={onOpen} />);
    expect(screen.getByText(/Solutions \(2\)/)).toBeTruthy();
    expect(screen.getByText(/— Reviewer/)).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Fraud" }));
    expect(onOpen).toHaveBeenCalledWith("y");
  });

  it("shows Restricted cost and renders only http(s) Agent Card links", () => {
    mockDetail({ cost_visible: false, est_cost_per_run: null, runs_per_month: null, a2a_card_url: "javascript:alert(1)" });
    render(<AgentDetail agentId="ag-1" onBack={vi.fn()} />);
    expect(screen.getAllByText("Restricted")).toHaveLength(2);
    expect(screen.queryByRole("link")).toBeNull();
    expect(screen.getByText(/Unassigned/)).toBeTruthy();
  });

  it("discloses the solution count before deleting", async () => {
    const del = vi.fn().mockResolvedValue(undefined);
    api.useDeleteAgent.mockReturnValue(mutation(del));
    mockDetail({ solution_count: 3 });
    const confirm = vi.spyOn(window, "confirm").mockReturnValue(true);
    const onBack = vi.fn();
    render(<AgentDetail agentId="ag-1" onBack={onBack} />);
    await userEvent.click(screen.getByRole("button", { name: "Delete" }));
    expect(confirm.mock.calls[0][0]).toMatch(/removed from 3 solutions/);
    expect(del).toHaveBeenCalledWith("ag-1");
    expect(onBack).toHaveBeenCalled();
  });
});
