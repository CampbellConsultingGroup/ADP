// ADP-SPEC-054 T019/T023/T025/T026/T029/T030: integration coverage for C4DesignView.tsx across
// all four user stories. Mocks web/src/api/designs.ts's hooks directly (this session's established
// vi.mock(hooks-module) convention, e.g. ThemeList.test.tsx) rather than wrapping in a
// QueryClientProvider.
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { C4DesignView } from "./C4DesignView";
import * as api from "../api/designs";
import * as strategyApi from "../api/strategy";
import type { ArchitectureDescription } from "../types";

vi.mock("../api/designs");
vi.mock("../api/strategy");
vi.mock("../api/client", () => ({
  getAuthHeader: vi.fn(async () => ({})),
}));

const mockedApi = vi.mocked(api);
const mockedStrategyApi = vi.mocked(strategyApi);

const DESIGN: ArchitectureDescription = {
  schema_version: "1.0.0",
  id: "DSN-001",
  title: "Payments Platform",
  elements: [
    { id: "ELM-001", name: "Customer", kind: "person" },
    { id: "ELM-002", name: "Payments Service", kind: "system" },
    { id: "ELM-003", name: "Web App", kind: "container" },
    { id: "ELM-004", name: "Checkout", kind: "component" },
  ],
  relationships: [
    { id: "REL-001", source: "ELM-001", target: "ELM-002", label: "Uses" },
  ],
  requirements: [],
};

let createElementMutateAsync: ReturnType<typeof vi.fn>;
let saveLayoutMutate: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  createElementMutateAsync = vi.fn(async (body: { kind: string; name: string }) => ({
    id: "ELM-999",
    name: body.name,
    kind: body.kind,
  }));
  saveLayoutMutate = vi.fn();

  mockedApi.useDesign.mockReturnValue({
    data: DESIGN,
    isLoading: false,
    error: null,
  } as unknown as ReturnType<typeof api.useDesign>);
  mockedApi.useLayout.mockReturnValue({
    data: { design_id: "DSN-001", level: "context", positions: { "ELM-001": { x: 111, y: 222 } } },
  } as unknown as ReturnType<typeof api.useLayout>);
  mockedApi.useSaveLayout.mockReturnValue({
    mutate: saveLayoutMutate,
  } as unknown as ReturnType<typeof api.useSaveLayout>);
  mockedApi.useCreateElement.mockReturnValue({
    mutateAsync: createElementMutateAsync,
  } as unknown as ReturnType<typeof api.useCreateElement>);
  mockedApi.useUpdateElement.mockReturnValue({
    mutateAsync: vi.fn(async () => DESIGN.elements[0]),
  } as unknown as ReturnType<typeof api.useUpdateElement>);
  mockedApi.useDeleteElement.mockReturnValue({
    mutateAsync: vi.fn(async () => undefined),
  } as unknown as ReturnType<typeof api.useDeleteElement>);
  mockedApi.useCreateRelationship.mockReturnValue({
    mutateAsync: vi.fn(async (body: { source: string; target: string }) => ({ id: "REL-999", ...body })),
  } as unknown as ReturnType<typeof api.useCreateRelationship>);
  mockedApi.useDeleteRelationship.mockReturnValue({
    mutateAsync: vi.fn(async () => undefined),
  } as unknown as ReturnType<typeof api.useDeleteRelationship>);
  mockedApi.useUpdateElementTags.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    isError: false,
  } as unknown as ReturnType<typeof api.useUpdateElementTags>);
  mockedStrategyApi.useDesignObjectives.mockReturnValue({
    data: { items: [], total: 0 },
    isLoading: false,
  } as unknown as ReturnType<typeof strategyApi.useDesignObjectives>);

  global.fetch = vi.fn(async () => ({
    ok: true,
    blob: async () => new Blob(["{}"], { type: "application/json" }),
  })) as unknown as typeof fetch;
});

describe("C4DesignView: level filtering (User Story 2, FR-006)", () => {
  it("shows only person+system elements at Context level by default", () => {
    render(<C4DesignView designId="DSN-001" />);
    expect(screen.getByTestId("node-ELM-001")).toBeTruthy();
    expect(screen.getByTestId("node-ELM-002")).toBeTruthy();
    expect(screen.queryByTestId("node-ELM-003")).toBeNull();
    expect(screen.queryByTestId("node-ELM-004")).toBeNull();
  });

  it("switching to Container level shows only system+container elements", async () => {
    const user = userEvent.setup();
    render(<C4DesignView designId="DSN-001" />);
    await user.click(screen.getByText("Container"));
    expect(screen.queryByTestId("node-ELM-001")).toBeNull();
    expect(screen.getByTestId("node-ELM-002")).toBeTruthy();
    expect(screen.getByTestId("node-ELM-003")).toBeTruthy();
  });

  it("switching to Component level shows only container+component elements", async () => {
    const user = userEvent.setup();
    render(<C4DesignView designId="DSN-001" />);
    await user.click(screen.getByText("Component"));
    expect(screen.getByTestId("node-ELM-003")).toBeTruthy();
    expect(screen.getByTestId("node-ELM-004")).toBeTruthy();
  });
});

describe("C4DesignView: element picker lists every element regardless of level (User Story 3, FR-008)", () => {
  it("shows all 4 elements in the picker even though only 2 are visible on the Context canvas", () => {
    render(<C4DesignView designId="DSN-001" />);
    expect(screen.getByTestId("element-row-ELM-001").textContent).toContain("Customer");
    expect(screen.getByTestId("element-row-ELM-002").textContent).toContain("Payments Service");
    expect(screen.getByTestId("element-row-ELM-003").textContent).toContain("Web App");
    expect(screen.getByTestId("element-row-ELM-004").textContent).toContain("Checkout");
  });

  it("selecting an element in the picker renders InspectionPanel with its technology section", async () => {
    const user = userEvent.setup();
    render(<C4DesignView designId="DSN-001" />);
    await user.click(screen.getByTestId("element-row-ELM-002"));
    // InspectionPanel renders the element's kind and a Technology section.
    expect(screen.getByText("[system]")).toBeTruthy();
    screen.getByText("Technology");
  });
});

describe("C4DesignView: adding a shape commits immediately (User Story 1, FR-002, SC-001)", () => {
  it("clicking Add Rectangle calls createElement with the shape convention's mapped kind", async () => {
    const user = userEvent.setup();
    render(<C4DesignView designId="DSN-001" />);
    await user.click(screen.getByTestId("add-shape-rectangle"));
    await waitFor(() => expect(createElementMutateAsync).toHaveBeenCalledTimes(1));
    expect(createElementMutateAsync.mock.calls[0][0]).toMatchObject({ kind: "system" });
  });
});

describe("C4DesignView: layout continuity (User Story 4, FR-013)", () => {
  it("seeds a node's position from the existing useLayout hook's returned positions", () => {
    render(<C4DesignView designId="DSN-001" />);
    // The DSL panel (useDslSync's serialized view of the current model) is the simplest place to
    // observe the model's raw position data -- confirm the layout-seeded coordinate (111, 222) for
    // ELM-001 made it into the derived model, not an auto-generated one.
    const dsl = screen.getByTestId("dsl-panel") as HTMLTextAreaElement;
    expect(dsl.value).toContain("111");
    expect(dsl.value).toContain("222");
  });

  it("debounces a save-layout call through the existing, unmodified useSaveLayout hook after a model change", async () => {
    const user = userEvent.setup();
    render(<C4DesignView designId="DSN-001" />);
    await user.click(screen.getByTestId("add-shape-rectangle"));
    await waitFor(() => expect(saveLayoutMutate).toHaveBeenCalled(), { timeout: 2000 });
    expect(saveLayoutMutate.mock.calls[0][0]).toMatchObject({ design_id: "DSN-001", level: "context" });
  });
});

describe("C4DesignView: export reuses existing endpoints verbatim (User Story 3, FR-009/FR-010, research.md Decision 9)", () => {
  it("Export Render posts to the existing locked-theme render endpoint", async () => {
    const user = userEvent.setup();
    render(<C4DesignView designId="DSN-001" />);
    await user.click(screen.getByText("Export Render"));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      "/api/v1/designs/DSN-001/render",
      expect.objectContaining({ method: "POST" }),
    ));
  });

  it("Export CALM fetches the existing CALM export endpoint", async () => {
    const user = userEvent.setup();
    render(<C4DesignView designId="DSN-001" />);
    await user.click(screen.getByText("Export CALM"));
    await waitFor(() => expect(global.fetch).toHaveBeenCalledWith(
      "/api/v1/designs/DSN-001/export/calm",
      expect.anything(),
    ));
  });
});

describe("C4DesignView: Traceability panel (ADP-d8u.2)", () => {
  it("shows an empty state when no objectives are linked", () => {
    render(<C4DesignView designId="DSN-001" />);
    expect(screen.getByText("Traceability")).toBeTruthy();
    expect(screen.getByText("No objectives linked to this design yet.")).toBeTruthy();
  });

  it("lists every objective linked to this design", () => {
    mockedStrategyApi.useDesignObjectives.mockReturnValue({
      data: {
        items: [
          {
            id: "obj-1", theme_id: "t1", owner: "Owner", statement: "Reduce claims cycle time",
            fiscal_year: 2026, period: "Q3", status: "active", updated_at: "",
          },
        ],
        total: 1,
      },
      isLoading: false,
    } as unknown as ReturnType<typeof strategyApi.useDesignObjectives>);

    render(<C4DesignView designId="DSN-001" />);

    expect(screen.getByText("Reduce claims cycle time")).toBeTruthy();
    expect(screen.queryByText("No objectives linked to this design yet.")).toBeNull();
  });
});
