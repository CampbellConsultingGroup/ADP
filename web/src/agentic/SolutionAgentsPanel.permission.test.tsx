// ADP-blp.65: a role that cannot write applications sees the solution's agents read-only.
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import * as agenticApi from "../api/agentic";
import * as complianceApi from "../api/compliance";
import * as permissions from "../auth/permissions";
import SolutionAgentsPanel from "./SolutionAgentsPanel";

vi.mock("../api/agentic");
vi.mock("../api/compliance");
vi.mock("../auth/permissions");
const api = vi.mocked(agenticApi);

const member = {
  agent: {
    id: "a", name: "Orchestrator", autonomy_level: 1, human_approval: "always",
    model_provider: null, model_id: null,
    agentic_risk: { band: "low", factors: [], missing: [], not_considered: [] },
  },
  role: "orchestrator", position: 0,
};

describe("SolutionAgentsPanel for a read-only role", () => {
  it("disables role, order, remove and add, and gives the reason", () => {
    vi.mocked(permissions.useCan).mockReturnValue({ allowed: false, reason: "Your role (Reviewer) cannot do this." });
    const idle = { mutateAsync: vi.fn(), isPending: false } as never;
    api.useSolutionAgents.mockReturnValue({ data: { items: [member], total: 1 }, isLoading: false } as never);
    api.useAgents.mockReturnValue({ data: { items: [member.agent], total: 1 } } as never);
    api.useAddSolutionAgent.mockReturnValue(idle);
    api.useUpdateSolutionAgentRole.mockReturnValue(idle);
    api.useReorderSolutionAgents.mockReturnValue(idle);
    api.useRemoveSolutionAgent.mockReturnValue(idle);
    vi.mocked(complianceApi.useAgentComplianceStatuses).mockReturnValue({ data: undefined } as never);

    render(<SolutionAgentsPanel appId="app" />);
    expect(permissions.useCan).toHaveBeenCalledWith("write_application");
    expect((screen.getByLabelText("Role for Orchestrator") as HTMLSelectElement).disabled).toBe(true);
    const remove = screen.getByRole("button", { name: "Remove Orchestrator" }) as HTMLButtonElement;
    expect(remove.disabled).toBe(true);
    expect(remove.title).toMatch(/Reviewer/);
    expect((screen.getByLabelText("Agent to add") as HTMLSelectElement).disabled).toBe(true);
    // The agents themselves are still listed.
    expect(screen.getAllByText("Orchestrator").length).toBeGreaterThan(0);
  });
});
