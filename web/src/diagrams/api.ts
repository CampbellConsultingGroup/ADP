// ADP-SPEC-046: typed client for /api/v1/diagrams.
//
// Uses the shared apiGet/apiMutation helpers (web/src/api/client.ts), NOT a
// raw fetch() -- a raw fetch bypassing getAuthHeader() is exactly the class
// of bug that caused the "black screen" incident documented in this
// project's own history (application.ts/Workspace.tsx, ADP-cm9).

import { apiGet, apiMutation } from "../api/client";

export type DiagramType = "flowchart" | "sequence" | "erd" | "uml" | "architecture";

export interface Diagram {
  id: string;
  title: string;
  diagram_type: DiagramType;
  dsl_source: string;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface DiagramSummary {
  id: string;
  title: string;
  diagram_type: DiagramType;
  updated_at: string;
}

export interface DiagramListResponse {
  items: DiagramSummary[];
  total: number;
}

export interface DiagramCreateBody {
  title: string;
  diagram_type: DiagramType;
  dsl_source?: string;
}

export interface DiagramUpdateBody {
  title?: string;
  dsl_source?: string;
}

const BASE = "/api/v1/diagrams";

export function listDiagrams(): Promise<DiagramListResponse> {
  return apiGet<DiagramListResponse>(BASE);
}

export function getDiagram(id: string): Promise<Diagram> {
  return apiGet<Diagram>(`${BASE}/${id}`);
}

export function createDiagram(body: DiagramCreateBody): Promise<Diagram> {
  return apiMutation<Diagram, DiagramCreateBody>("POST", BASE, body);
}

export function updateDiagram(id: string, body: DiagramUpdateBody): Promise<Diagram> {
  return apiMutation<Diagram, DiagramUpdateBody>("PUT", `${BASE}/${id}`, body);
}

export function deleteDiagram(id: string): Promise<void> {
  return apiMutation<void>("DELETE", `${BASE}/${id}`);
}

export function exportDiagramPng(id: string, svg: string): Promise<Blob> {
  // apiMutation always parses JSON -- PNG bytes need a dedicated call using
  // the same auth header, not apiMutation's response handling.
  return (async () => {
    const { getAuthHeader } = await import("../api/client");
    const authHeader = await getAuthHeader();
    const res = await fetch(`${BASE}/${id}/export`, {
      method: "POST",
      headers: { ...authHeader, "Content-Type": "application/json" },
      body: JSON.stringify({ svg }),
    });
    if (!res.ok) {
      throw new Error(`Export failed: ${res.status}`);
    }
    return res.blob();
  })();
}
