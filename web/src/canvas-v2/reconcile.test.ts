// ADP-SPEC-054 T018: diff-and-fire coverage for reconcile.ts.
import { describe, expect, it, vi } from "vitest";
import { applyIdReplacements, reconcile, type ReconcileMutations } from "./reconcile";
import type { DiagramModel } from "../diagrams/core/model/diagram-model";

function emptyModel(diagramTypeId = "c4-context"): DiagramModel {
  return { diagramTypeId, nodes: [], edges: [], containers: [] };
}

function mockMutations(): ReconcileMutations {
  return {
    createElement: vi.fn(async () => ({ id: "ELM-999" })),
    updateElement: vi.fn(async () => {}),
    deleteElement: vi.fn(async () => {}),
    createRelationship: vi.fn(async () => ({ id: "REL-999" })),
    deleteRelationship: vi.fn(async () => {}),
  };
}

describe("reconcile: no-op when nothing changed", () => {
  it("calls nothing when previous and next are identical", async () => {
    const model: DiagramModel = {
      ...emptyModel(),
      nodes: [{ id: "ELM-001", label: "Customer", shape: "circle", role: "person", position: { x: 0, y: 0 } }],
    };
    const mutations = mockMutations();
    await reconcile(model, model, mutations);
    expect(mutations.createElement).not.toHaveBeenCalled();
    expect(mutations.updateElement).not.toHaveBeenCalled();
    expect(mutations.deleteElement).not.toHaveBeenCalled();
    expect(mutations.createRelationship).not.toHaveBeenCalled();
    expect(mutations.deleteRelationship).not.toHaveBeenCalled();
  });
});

describe("reconcile: added node", () => {
  it("calls createElement exactly once and returns the id replacement", async () => {
    const previous = emptyModel();
    const next: DiagramModel = {
      ...emptyModel(),
      nodes: [{ id: "tmp-1", label: "New System", shape: "rectangle", position: { x: 0, y: 0 } }],
    };
    const mutations = mockMutations();
    const replacements = await reconcile(previous, next, mutations);
    expect(mutations.createElement).toHaveBeenCalledTimes(1);
    expect(mutations.createElement).toHaveBeenCalledWith({ kind: "system", name: "New System" });
    expect(replacements).toEqual([{ kind: "node", tempId: "tmp-1", realId: "ELM-999" }]);
  });
});

describe("reconcile: removed node", () => {
  it("calls deleteElement exactly once", async () => {
    const previous: DiagramModel = {
      ...emptyModel(),
      nodes: [{ id: "ELM-001", label: "Customer", shape: "circle", role: "person", position: { x: 0, y: 0 } }],
    };
    const next = emptyModel();
    const mutations = mockMutations();
    await reconcile(previous, next, mutations);
    expect(mutations.deleteElement).toHaveBeenCalledTimes(1);
    expect(mutations.deleteElement).toHaveBeenCalledWith("ELM-001");
  });
});

describe("reconcile: renamed node", () => {
  it("calls updateElement exactly once with the new name, no create/delete", async () => {
    const node = { id: "ELM-001", label: "Customer", shape: "circle" as const, role: "person", position: { x: 0, y: 0 } };
    const previous: DiagramModel = { ...emptyModel(), nodes: [node] };
    const next: DiagramModel = { ...emptyModel(), nodes: [{ ...node, label: "VIP Customer" }] };
    const mutations = mockMutations();
    await reconcile(previous, next, mutations);
    expect(mutations.updateElement).toHaveBeenCalledTimes(1);
    expect(mutations.updateElement).toHaveBeenCalledWith("ELM-001", { name: "VIP Customer" });
    expect(mutations.createElement).not.toHaveBeenCalled();
    expect(mutations.deleteElement).not.toHaveBeenCalled();
  });
});

describe("reconcile: added/removed edges", () => {
  it("calls createRelationship for a new edge and returns its id replacement", async () => {
    const previous = emptyModel();
    const next: DiagramModel = {
      ...emptyModel(),
      edges: [{ id: "tmp-e1", sourceId: "ELM-001", targetId: "ELM-002", label: "Uses" }],
    };
    const mutations = mockMutations();
    const replacements = await reconcile(previous, next, mutations);
    expect(mutations.createRelationship).toHaveBeenCalledWith({ source: "ELM-001", target: "ELM-002", label: "Uses" });
    expect(replacements).toEqual([{ kind: "edge", tempId: "tmp-e1", realId: "REL-999" }]);
  });

  it("calls deleteRelationship for a removed edge whose endpoints are untouched", async () => {
    const previous: DiagramModel = {
      ...emptyModel(),
      edges: [{ id: "REL-001", sourceId: "ELM-001", targetId: "ELM-002" }],
    };
    const next = emptyModel();
    const mutations = mockMutations();
    await reconcile(previous, next, mutations);
    expect(mutations.deleteRelationship).toHaveBeenCalledTimes(1);
    expect(mutations.deleteRelationship).toHaveBeenCalledWith("REL-001");
  });

  it("does NOT call deleteRelationship for an edge whose endpoint element was also removed (server cascades it)", async () => {
    const previous: DiagramModel = {
      ...emptyModel(),
      nodes: [{ id: "ELM-001", label: "Customer", shape: "circle", position: { x: 0, y: 0 } }],
      edges: [{ id: "REL-001", sourceId: "ELM-001", targetId: "ELM-002" }],
    };
    const next = emptyModel();
    const mutations = mockMutations();
    await reconcile(previous, next, mutations);
    expect(mutations.deleteElement).toHaveBeenCalledWith("ELM-001");
    expect(mutations.deleteRelationship).not.toHaveBeenCalled();
  });
});

describe("applyIdReplacements", () => {
  it("replaces a node's temp id and updates any edge endpoints referencing it", () => {
    const model: DiagramModel = {
      ...emptyModel(),
      nodes: [{ id: "tmp-1", label: "New", shape: "rectangle", position: { x: 0, y: 0 } }],
      edges: [{ id: "tmp-e1", sourceId: "tmp-1", targetId: "ELM-002" }],
    };
    const updated = applyIdReplacements(model, [
      { kind: "node", tempId: "tmp-1", realId: "ELM-999" },
      { kind: "edge", tempId: "tmp-e1", realId: "REL-999" },
    ]);
    expect(updated.nodes[0].id).toBe("ELM-999");
    expect(updated.edges[0].id).toBe("REL-999");
    expect(updated.edges[0].sourceId).toBe("ELM-999");
  });

  it("returns the same model reference when there are no replacements", () => {
    const model = emptyModel();
    expect(applyIdReplacements(model, [])).toBe(model);
  });
});
