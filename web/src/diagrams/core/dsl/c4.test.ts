/**
 * ADP-SPEC-053 T003: parse/serialize round-trip coverage for the `c4` DSL family
 * (web/src/diagrams/core/dsl/c4.ts) — mirroring families.test.ts's existing per-family pattern
 * (flowchart/erd/architecture/sequence/uml each already have coverage there; `c4` currently has
 * none anywhere in the repo, research.md Decision 2). `c4.ts` itself is vendored and unchanged by
 * this feature — this file verifies existing, correct behavior, not new production code.
 */
import { describe, expect, it } from 'vitest';
import { parseC4, serializeC4 } from './c4';
import { isParseSuccess } from './types';
import type { DiagramModel } from '../model/diagram-model';

function normalize(model: DiagramModel) {
  return {
    diagramTypeId: model.diagramTypeId,
    nodes: [...model.nodes].sort((a, b) => a.id.localeCompare(b.id)),
    edges: [...model.edges].sort((a, b) => a.id.localeCompare(b.id)),
    containers: [...model.containers].sort((a, b) => a.id.localeCompare(b.id)),
  };
}

describe('c4 (Context level): parse(serialize(model)) round-trip', () => {
  it('round-trips Person/System/SystemQueue with a plain and a bidirectional relationship', () => {
    const model: DiagramModel = {
      diagramTypeId: 'c4-context',
      nodes: [
        { id: 'user', label: 'Customer', shape: 'person', role: 'person', position: { x: 0, y: 0 } },
        { id: 'sys', label: 'Payments Service', shape: 'rectangle', role: 'system', position: { x: 200, y: 0 } },
        { id: 'queue', label: 'Payments Queue', shape: 'stadium', role: 'system', position: { x: 400, y: 0 } },
      ],
      edges: [
        { id: 'e1', sourceId: 'user', targetId: 'sys', label: 'Uses' },
        { id: 'e2', sourceId: 'sys', targetId: 'queue', label: 'Publishes to', arrow: 'both' },
      ],
      containers: [],
    };
    const dsl = serializeC4(model);
    const result = parseC4(dsl);
    expect(isParseSuccess(result)).toBe(true);
    if (isParseSuccess(result)) {
      expect(normalize(result.model)).toEqual(normalize(model));
    }
  });
});

describe('c4 (Container level): parse(serialize(model)) round-trip', () => {
  it('round-trips a ContainerDb element inside nested boundaries', () => {
    const model: DiagramModel = {
      diagramTypeId: 'c4-container',
      nodes: [
        { id: 'web', label: 'Web App', shape: 'rounded-rectangle', role: 'container', position: { x: 0, y: 0 }, containerId: 'sys' },
        { id: 'db', label: 'Database', shape: 'cylinder', role: 'container', position: { x: 200, y: 0 }, containerId: 'sys' },
      ],
      edges: [{ id: 'e1', sourceId: 'web', targetId: 'db', label: 'Reads/writes' }],
      containers: [
        { id: 'enterprise', label: 'Acme Corp', position: { x: 0, y: 0 } },
        { id: 'sys', label: 'Payments System', position: { x: 10, y: 10 }, parentContainerId: 'enterprise' },
      ],
    };
    const dsl = serializeC4(model);
    const result = parseC4(dsl);
    expect(isParseSuccess(result)).toBe(true);
    if (isParseSuccess(result)) {
      expect(normalize(result.model)).toEqual(normalize(model));
      const db = result.model.nodes.find((n) => n.id === 'db');
      expect(db?.shape).toBe('cylinder');
    }
  });
});

describe('c4: parses valid C4Context DSL text into a structured model', () => {
  it('parses a person, a system, and a relationship between them', () => {
    const dsl = 'C4Context\nPerson(user, "Customer")\nSystem(sys, "Payments Service")\nRel(user, sys, "Uses")\n';
    const result = parseC4(dsl);
    expect(isParseSuccess(result)).toBe(true);
    if (isParseSuccess(result)) {
      expect(result.model.nodes).toHaveLength(2);
      expect(result.model.edges).toHaveLength(1);
      expect(result.model.diagramTypeId).toBe('c4-context');
    }
  });
});

describe('parseC4: structured error reporting (FR-007)', () => {
  it('never throws on malformed input', () => {
    expect(() => parseC4('not a c4 diagram at all {{{')).not.toThrow();
    expect(() => parseC4('')).not.toThrow();
  });

  it('reports a structured error with line and content for an unrecognized construct', () => {
    const result = parseC4('C4Context\nPerson(user, "Customer")\nPersn(oops, "Typo")\n');
    expect(isParseSuccess(result)).toBe(false);
    if (!isParseSuccess(result)) {
      expect(result.errors.length).toBeGreaterThan(0);
      expect(result.errors[0]).toMatchObject({
        line: 3,
        content: expect.stringContaining('Persn'),
      });
      expect(result.errors[0].message).toBeTruthy();
    }
  });
});
