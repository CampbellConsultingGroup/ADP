import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  ReactFlow,
  addEdge,
  useNodesState,
  useEdgesState,
  type Connection,
  type Node,
  type Edge,
  type OnConnect,
  type OnNodeDrag,
  type NodeMouseHandler,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { ArchitectureDescription, C4Level, C4NodeData, C4Theme, DiagramLayout } from "../types";
import { C4NodeTypes } from "./nodes/NodeTypes";
import { C4EdgeTypes } from "./edges/EdgeTypes";
import { filterElementsForLevel, filterRelationshipsForLevel } from "./c4-filter";
import { getElementStyle } from "../theme/c4-theme";
import { useDrawRelationship, usePlaceElement, useSaveLayout } from "../api/designs";
import { useWorkspaceStore } from "../store/workspace-store";

interface C4CanvasProps {
  design: ArchitectureDescription;
  layout: DiagramLayout | undefined;
  theme: C4Theme | undefined;
  activeLevel: C4Level;
}

const ADD_ELEMENT_KINDS = ["person", "system", "container", "component"] as const;
type AddKind = (typeof ADD_ELEMENT_KINDS)[number];

let _saveDebounceTimer: ReturnType<typeof setTimeout> | null = null;

export default function C4Canvas({
  design,
  layout,
  theme,
  activeLevel,
}: C4CanvasProps): React.ReactElement {
  const [showAddMenu, setShowAddMenu] = useState(false);
  const [addName, setAddName] = useState("");
  const [addKind, setAddKind] = useState<AddKind>("container");
  const [saving, setSaving] = useState(false);
  const layoutRef = useRef(layout);
  layoutRef.current = layout;

  const { selectElement, clearSelection } = useWorkspaceStore();
  const placeElement = usePlaceElement();
  const drawRelationship = useDrawRelationship();
  const saveLayout = useSaveLayout();

  // Derive visible elements + edges from the canonical model
  const visibleElements = useMemo(
    () => filterElementsForLevel(design.elements, activeLevel),
    [design.elements, activeLevel],
  );

  const visibleIds = useMemo(
    () => new Set(visibleElements.map((e) => e.id)),
    [visibleElements],
  );

  const visibleRelationships = useMemo(
    () => filterRelationshipsForLevel(design.relationships, visibleIds),
    [design.relationships, visibleIds],
  );

  const initialNodes = useMemo<Node<C4NodeData>[]>(() => {
    return visibleElements.map((el) => {
      const pos = layout?.positions[el.id] ?? { x: Math.random() * 400, y: Math.random() * 300 };
      return {
        id: el.id,
        type: "c4Element",
        position: pos,
        data: {
          element: el,
          style: getElementStyle(el.kind, theme ?? null),
          selected: false,
        },
      };
    });
  }, [visibleElements, layout, theme]);

  const initialEdges = useMemo<Edge[]>(() =>
    visibleRelationships.map((r) => ({
      id: r.id,
      source: r.source,
      target: r.target,
      type: "c4Relationship",
      data: { label: r.label, theme },
    })),
    [visibleRelationships, theme],
  );

  const [nodes, setNodes, onNodesChange] = useNodesState<Node<C4NodeData>>(initialNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>(initialEdges);

  // Keep nodes in sync when design/level/layout changes
  useEffect(() => {
    setNodes(initialNodes);
  }, [initialNodes, setNodes]);

  useEffect(() => {
    setEdges(initialEdges);
  }, [initialEdges, setEdges]);

  const onConnect: OnConnect = useCallback(
    (connection: Connection) => {
      if (!connection.source || !connection.target) return;
      void drawRelationship.mutateAsync({
        design_id: design.id,
        source: connection.source,
        target: connection.target,
      });
      setEdges((eds) => addEdge(connection, eds));
    },
    [drawRelationship, design.id, setEdges],
  );

  const onNodeDragStop: OnNodeDrag = useCallback(
    (_event, node) => {
      const positions = {
        ...(layoutRef.current?.positions ?? {}),
        [node.id]: { x: node.position.x, y: node.position.y },
      };
      if (_saveDebounceTimer) clearTimeout(_saveDebounceTimer);
      setSaving(true);
      _saveDebounceTimer = setTimeout(() => {
        saveLayout.mutate(
          { design_id: design.id, level: activeLevel, positions },
          { onSettled: () => setSaving(false) },
        );
      }, 500);
    },
    [saveLayout, design.id, activeLevel],
  );

  const handleNodeClick: NodeMouseHandler = useCallback(
    (_event, node) => {
      selectElement(node.id);
    },
    [selectElement],
  );

  const handlePaneClick = useCallback(() => {
    clearSelection();
  }, [clearSelection]);

  const handleAddElement = useCallback(() => {
    if (!addName.trim()) return;
    placeElement.mutate({
      design_id: design.id,
      name: addName.trim(),
      kind: addKind,
      position: { x: 100 + Math.random() * 200, y: 100 + Math.random() * 200 },
    });
    setAddName("");
    setShowAddMenu(false);
  }, [placeElement, design.id, addName, addKind]);

  return (
    <div style={{ width: "100%", height: "100%", position: "relative" }}>
      {saving && (
        <div style={{ position: "absolute", top: 8, right: 8, fontSize: 12, color: "var(--ink-3)", zIndex: 10 }}>
          Saving...
        </div>
      )}

      <div style={{ position: "absolute", top: 8, left: 8, zIndex: 10 }}>
        <button
          onClick={() => setShowAddMenu((v) => !v)}
          style={{ padding: "6px 14px", cursor: "pointer", background: "var(--accent)", color: "#fff", border: "none", borderRadius: 4 }}
        >
          + Add Element
        </button>
        {showAddMenu && (
          <div style={{ background: "var(--surface)", border: "1px solid var(--border)", borderRadius: 4, padding: 12, marginTop: 4, display: "flex", flexDirection: "column", gap: 8 }}>
            <select value={addKind} onChange={(e) => setAddKind(e.target.value as AddKind)}>
              {ADD_ELEMENT_KINDS.map((k) => (
                <option key={k} value={k}>{k}</option>
              ))}
            </select>
            <input
              value={addName}
              onChange={(e) => setAddName(e.target.value)}
              placeholder="Element name"
              style={{ padding: "4px 8px", border: "1px solid var(--border)", borderRadius: 4 }}
              onKeyDown={(e) => { if (e.key === "Enter") handleAddElement(); }}
            />
            <button onClick={handleAddElement} style={{ background: "var(--accent)", color: "#fff", border: "none", borderRadius: 4, padding: "4px 8px", cursor: "pointer" }}>
              Add
            </button>
          </div>
        )}
      </div>

      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeDragStop={onNodeDragStop}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        nodeTypes={C4NodeTypes}
        edgeTypes={C4EdgeTypes}
        fitView
      />
    </div>
  );
}
