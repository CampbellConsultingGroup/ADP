import React from "react";
import { BaseEdge, EdgeLabelRenderer, getStraightPath } from "@xyflow/react";
import type { C4Theme } from "../../types";

interface C4RelationshipEdgeProps {
  id: string;
  sourceX: number;
  sourceY: number;
  targetX: number;
  targetY: number;
  data?: { label?: string; theme?: C4Theme };
}

export function C4RelationshipEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  data,
}: C4RelationshipEdgeProps): React.ReactElement {
  const [edgePath, labelX, labelY] = getStraightPath({ sourceX, sourceY, targetX, targetY });
  const relStyle = data?.theme?.relationship_style;
  const stroke = relStyle?.stroke ?? "#707070";
  const strokeWidth = relStyle?.stroke_width ?? 1.5;

  return (
    <>
      <BaseEdge
        id={id}
        path={edgePath}
        style={{ stroke, strokeWidth }}
        markerEnd="url(#arrowhead)"
      />
      {data?.label && (
        <EdgeLabelRenderer>
          <div
            style={{
              position: "absolute",
              transform: `translate(-50%, -50%) translate(${labelX}px,${labelY}px)`,
              fontSize: 11,
              color: "#333",
              background: "rgba(255,255,255,0.8)",
              padding: "2px 4px",
              borderRadius: 3,
              pointerEvents: "all",
            }}
          >
            {data.label}
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  );
}

export default C4RelationshipEdge;
