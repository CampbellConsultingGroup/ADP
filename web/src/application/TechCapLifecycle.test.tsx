// 938-capability-model-analysis US2: lifecycle controls and the past-end-of-life flag on technical
// capability rows. A partial mock keeps the real label constants (an automock would empty them).

import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import * as applicationApi from "../api/application";
import type { TechnicalCapability } from "../api/application";
import * as authApi from "../auth/AuthProvider";
import TechCapTree from "./TechCapTree";

vi.mock("../api/application", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../api/application")>()),
  useTechCaps: vi.fn(),
  useCreateTechCap: vi.fn(),
  useUpdateTechCap: vi.fn(),
  useDeleteTechCap: vi.fn(),
}));
vi.mock("../auth/AuthProvider", async (importOriginal) => ({
  ...(await importOriginal<typeof import("../auth/AuthProvider")>()),
  useAuth: vi.fn(),
}));

const api = vi.mocked(applicationApi);
const auth = vi.mocked(authApi);

function cap(over: Partial<TechnicalCapability>): TechnicalCapability {
  return {
    id: "tc", name: "Offline Sync", description: null, parent_id: null, level: 1, created_at: "",
    strategic_relevance: null, lifecycle_status: "current", end_of_life_date: null, ...over,
  };
}

let mutate: ReturnType<typeof vi.fn>;

function setup(items: TechnicalCapability[], role: string) {
  api.useTechCaps.mockReturnValue({ data: { items, total: items.length }, isLoading: false, error: null } as never);
  api.useCreateTechCap.mockReturnValue({ mutate: vi.fn(), mutateAsync: vi.fn(), isPending: false } as never);
  api.useUpdateTechCap.mockReturnValue({ mutate, isPending: false } as never);
  api.useDeleteTechCap.mockReturnValue({ mutate: vi.fn(), isPending: false } as never);
  auth.useAuth.mockReturnValue({ user: { role } } as never);
}

beforeEach(() => {
  vi.clearAllMocks();
  mutate = vi.fn();
});

describe("technical capability lifecycle on the tree", () => {
  it("lets a writer change the status and set or clear the end-of-life date", async () => {
    setup([cap({ end_of_life_date: "2027-06-30" })], "technical_architect");
    const user = userEvent.setup();
    render(<TechCapTree />);
    await user.selectOptions(screen.getByLabelText("Lifecycle of Offline Sync"), "retiring");
    expect(mutate).toHaveBeenCalledWith({ id: "tc", body: { lifecycle_status: "retiring" } });
    await user.clear(screen.getByLabelText("End-of-life date of Offline Sync"));
    expect(mutate).toHaveBeenLastCalledWith({ id: "tc", body: { end_of_life_date: null } });
  });

  it("shows a reader the lifecycle without controls", () => {
    setup([cap({ lifecycle_status: "retiring", end_of_life_date: "2027-06-30" })], "reviewer");
    render(<TechCapTree />);
    expect(screen.queryByLabelText("Lifecycle of Offline Sync")).toBeNull();
    expect(screen.getByLabelText("Lifecycle").textContent).toBe("Retiring · EOL 2027-06-30");
  });

  it("flags a capability whose end-of-life date has passed, unless it is already retired", () => {
    setup(
      [cap({ id: "a", name: "Old Sync", end_of_life_date: "2020-01-01" }), cap({ id: "b", name: "Gone", lifecycle_status: "retired", end_of_life_date: "2020-01-01" })],
      "reviewer",
    );
    render(<TechCapTree />);
    expect(screen.getAllByText("⚠ past end of life")).toHaveLength(1);
  });

  it("highlights and scrolls to a focused capability", () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    setup([cap({ id: "a", name: "Alpha" }), cap({ id: "b", name: "Bravo" })], "reviewer");
    render(<TechCapTree focusId="b" />);
    expect(scroll).toHaveBeenCalled();
    const row = document.querySelector('[data-tech-cap-row="b"] > div') as HTMLElement;
    expect(row.style.background).not.toBe("");
  });
});
