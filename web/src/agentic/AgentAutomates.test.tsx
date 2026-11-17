// 944-agent-traceability (ADP-12x, US1): the Automates section on Agent detail. Choosing a
// value saves at once (ADP-w7z); stages and activities are picked in two steps.

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as agenticApi from "../api/agentic";
import * as businessApi from "../api/business";
import AgentAutomates from "./AgentAutomates";

vi.mock("../api/agentic");
vi.mock("../api/business");
const api = vi.mocked(agenticApi);
const biz = vi.mocked(businessApi);

const add = vi.fn();
const remove = vi.fn();

function cap(id: string, name: string, level: number, parent_id: string | null) {
  return { id, name, level, parent_id };
}

beforeEach(() => {
  vi.clearAllMocks();
  api.errorDetail.mockImplementation((err: unknown) => (err instanceof Error ? err.message : String(err)));
  api.useAgentAutomates.mockReturnValue({
    data: {
      capabilities: [{ id: "l3a", name: "Process Payment", level: 3, path: ["Commerce", "Checkout"] }],
      stages: [{ id: "st1", name: "Take Order", value_stream_id: "vs1", value_stream_name: "Order to Cash" }],
      activities: [
        { id: "act1", name: "Inbound Logistics", category: "primary", value_chain_id: "ch1", value_chain_name: "Retail" },
      ],
    },
    isLoading: false,
  } as never);
  api.useAddAutomates.mockReturnValue({ mutate: add, isPending: false } as never);
  api.useRemoveAutomates.mockReturnValue({ mutate: remove, isPending: false } as never);
  biz.useCapabilities.mockReturnValue({
    data: {
      items: [
        cap("l1", "Commerce", 1, null),
        cap("l2", "Checkout", 2, "l1"),
        cap("l3a", "Process Payment", 3, "l2"),
        cap("l3b", "Apply Promotions", 3, "l2"),
      ],
      total: 4,
    },
    isLoading: false,
  } as never);
  biz.useValueStreams.mockReturnValue({
    data: { items: [{ id: "vs1", name: "Order to Cash" }], total: 1 },
  } as never);
  biz.useValueStream.mockImplementation(
    (id: string | null) =>
      ({
        data: id
          ? { id, name: "Order to Cash", stages: [{ id: "st1", name: "Take Order" }, { id: "st2", name: "Ship" }] }
          : undefined,
      }) as never,
  );
  biz.useValueChains.mockReturnValue({
    data: { items: [{ id: "ch1", name: "Retail" }], total: 1 },
  } as never);
  biz.useValueChain.mockImplementation(
    (id: string | null) =>
      ({
        data: id
          ? {
              id,
              name: "Retail",
              primary_activities: [{ id: "act1", name: "Inbound Logistics", category: "primary" }],
              support_activities: [{ id: "act2", name: "Procurement", category: "support" }],
            }
          : undefined,
      }) as never,
  );
});

describe("AgentAutomates", () => {
  it("lists what the agent automates with context", () => {
    render(<AgentAutomates agentId="ag-1" />);
    expect(screen.getByText("Commerce › Checkout ›")).toBeTruthy();
    expect(screen.getByText("Process Payment")).toBeTruthy();
    expect(screen.getByText("Order to Cash ›")).toBeTruthy();
    expect(screen.getByText("Inbound Logistics")).toBeTruthy();
    expect(screen.getByText("Retail ›")).toBeTruthy();
    expect(screen.getByText("(primary)")).toBeTruthy();
  });

  it("offers only unlinked L3 capabilities, labeled by path, and saves on choose", async () => {
    render(<AgentAutomates agentId="ag-1" />);
    const select = screen.getByLabelText("Link a business capability") as HTMLSelectElement;
    const labels = Array.from(select.options).map((o) => o.text);
    expect(labels).toEqual(["Link an L3 capability…", "Commerce › Checkout › Apply Promotions"]);
    await userEvent.selectOptions(select, "l3b");
    expect(add).toHaveBeenCalledWith({ kind: "capability", targetId: "l3b" }, expect.anything());
  });

  it("picks a stage through its value stream and saves on choose", async () => {
    render(<AgentAutomates agentId="ag-1" />);
    await userEvent.selectOptions(screen.getByLabelText("Value stream"), "vs1");
    const stage = screen.getByLabelText("Link a value stream stage") as HTMLSelectElement;
    // st1 is already linked.
    expect(Array.from(stage.options).map((o) => o.value)).toEqual(["", "st2"]);
    await userEvent.selectOptions(stage, "st2");
    expect(add).toHaveBeenCalledWith({ kind: "stage", targetId: "st2" }, expect.anything());
  });

  it("picks an activity through its value chain", async () => {
    render(<AgentAutomates agentId="ag-1" />);
    await userEvent.selectOptions(screen.getByLabelText("Value chain"), "ch1");
    await userEvent.selectOptions(screen.getByLabelText("Link a value chain activity"), "act2");
    expect(add).toHaveBeenCalledWith({ kind: "activity", targetId: "act2" }, expect.anything());
  });

  it("shows the server's reason when a link fails and resets the select", async () => {
    add.mockImplementation((_vars, opts) => opts.onError(new Error("Agents automate business capabilities at L3 only")));
    render(<AgentAutomates agentId="ag-1" />);
    const select = screen.getByLabelText("Link a business capability") as HTMLSelectElement;
    await userEvent.selectOptions(select, "l3b");
    expect(screen.getByText(/L3 only/)).toBeTruthy();
    expect(select.value).toBe("");
  });

  it("removes a link", async () => {
    render(<AgentAutomates agentId="ag-1" />);
    await userEvent.click(screen.getByRole("button", { name: "Remove Process Payment" }));
    expect(remove).toHaveBeenCalledWith({ kind: "capability", targetId: "l3a" });
  });
});
