/** Shared TypeScript types for the ADP workspace — mirrors ADP-SPEC-001 canonical model. */

export type ElementKind = "person" | "system" | "container" | "component";
export type C4Level = "context" | "container" | "component";

/** Structured technology metadata for a design element (ADP-SPEC-029). */
export interface TechnologyMetadata {
  technology?: string | null;
  vendor?: string | null;
  platform?: string | null;
  version?: string | null;
  owner_team?: string | null;
}

export interface Element {
  id: string;
  name: string;
  kind: ElementKind;
  description?: string;
  satisfies?: string[];
  provenance?: string;
  tags?: string[];
  technology_metadata?: TechnologyMetadata | null;  // ADP-SPEC-029
}

export interface Relationship {
  id: string;
  source: string;
  target: string;
  label?: string;
  technology?: string;
}

export interface Requirement {
  id: string;
  title: string;
  description?: string;
}

export interface ArchitectureDescription {
  id: string;
  schema_version: string;
  title: string;
  elements: Element[];
  relationships: Relationship[];
  requirements?: Requirement[];
  version?: number;
}

export interface DiagramLayout {
  design_id: string;
  level: C4Level;
  positions: Record<string, { x: number; y: number }>;
}

export interface C4ElementStyle {
  fill: string;
  stroke: string;
  color: string;
  shape: "box" | "actor";
}

export interface ElementStyleEntry {
  fill: string;
  stroke: string;
  color: string;
  shape: string;
  font_size: number;
  font_weight: string;
}

export interface RelationshipStyle {
  stroke: string;
  stroke_width: number;
  arrow_end: string;
}

export interface C4Theme {
  version: string;
  locked: boolean;
  styles: Record<string, ElementStyleEntry>;
  relationship_style: RelationshipStyle;
}

export interface C4NodeData extends Record<string, unknown> {
  element: Element;
  style: C4ElementStyle;
  selected: boolean;
}

export interface PlaceElementInput {
  design_id: string;
  name: string;
  kind: ElementKind;
  description?: string;
  satisfies?: string[];
  position: { x: number; y: number };
}

export interface DrawRelationshipInput {
  design_id: string;
  source: string;
  target: string;
  label?: string;
  technology?: string;
}

export interface SaveLayoutInput {
  design_id: string;
  level: C4Level;
  positions: Record<string, { x: number; y: number }>;
}
