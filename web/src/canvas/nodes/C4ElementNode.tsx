import React from "react";
import { Handle, Position } from "@xyflow/react";
import type { C4NodeData } from "../../types";

/**
 * Custom React Flow node for C4 elements.
 *
 * ART-XII / QG-17 — NO OVERRIDE ZONE:
 * Styling is derived ONLY from data.style (pre-computed from the locked theme by element kind).
 * This component accepts NO color, fill, stroke, backgroundColor, or customStyle props.
 * TypeScript strict mode enforces this at compile time.
 */
interface C4ElementNodeProps {
  data: C4NodeData;
  selected: boolean;
}

export function C4ElementNode({ data, selected }: C4ElementNodeProps): React.ReactElement {
  const { element, style } = data;

  return (
    <div
      style={{
        background: style.fill,
        border: `${selected ? 3 : 1.5}px solid ${style.stroke}`,
        color: style.color,
        borderRadius: style.shape === "actor" ? "50% 50% 0 0 / 40% 40% 0 0" : 6,
        padding: "10px 16px",
        minWidth: 120,
        minHeight: 48,
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        fontFamily: "sans-serif",
        cursor: "pointer",
        boxSizing: "border-box",
      }}
    >
      <Handle type="target" position={Position.Top} />
      <span style={{ fontWeight: "bold", fontSize: 13 }}>{element.name}</span>
      <span style={{ fontSize: 11, opacity: 0.85 }}>[{element.kind}]</span>
      <Handle type="source" position={Position.Bottom} />
    </div>
  );
}

export default C4ElementNode;
