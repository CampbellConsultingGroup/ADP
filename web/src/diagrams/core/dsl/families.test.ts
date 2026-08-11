/**
 * ADP-SPEC-046 T003: parse/serialize roundtrip smoke coverage for all 5 registered DSL families,
 * plus the SVG renderer's escapeXml safety and the parser's structured-error reporting.
 *
 * Translated from /home/jmuir/projects/canvas/packages/diagram-core's own existing contract-test
 * suite (tests/contract/round-trip.test.ts, dsl-architecture.test.ts, erd-attributes.test.ts,
 * sequence-notes-and-blocks.test.ts, uml-class-syntax.test.ts, render-svg.test.ts,
 * parse-errors.test.ts) -- a representative confidence-check subset, not a full re-port of that
 * upstream project's own 55-file suite (which remains that project's own maintenance
 * responsibility; this file exists to confirm the *vendored copy* behaves as advertised,
 * per research.md Decision 1).
 */
import { describe, expect, it } from 'vitest';
import { parseFlowchart } from './flowchart-parser';
import { serializeFlowchart } from './flowchart-serializer';
import { parseSequence } from './sequence';
import { parseErd, serializeErd } from './erd';
import { parseUml } from './uml';
import { parseArchitecture, serializeArchitecture } from './architecture';
import { isParseSuccess } from './types';
import type { DiagramModel } from '../model/diagram-model';
import { renderToSvg } from '../render/svg-renderer';

function normalize(model: DiagramModel) {
  return {
    diagramTypeId: model.diagramTypeId,
    nodes: [...model.nodes].sort((a, b) => a.id.localeCompare(b.id)),
    edges: [...model.edges].sort((a, b) => a.id.localeCompare(b.id)),
    containers: [...model.containers].sort((a, b) => a.id.localeCompare(b.id)),
  };
}

describe('flowchart: parse(serialize(model)) round-trip', () => {
  it('round-trips a simple three-node, two-edge diagram', () => {
    const model: DiagramModel = {
      diagramTypeId: 'flowchart',
      nodes: [
        { id: 'A', label: 'Start', shape: 'rectangle', position: { x: 40, y: 40 } },
        { id: 'B', label: 'Decision', shape: 'diamond', position: { x: 240, y: 40 } },
        { id: 'C', label: 'End', shape: 'rounded-rectangle', position: { x: 440, y: 40 } },
      ],
      edges: [
        { id: 'e1', sourceId: 'A', targetId: 'B' },
        { id: 'e2', sourceId: 'B', targetId: 'C', label: 'yes' },
      ],
      containers: [],
    };
    const dsl = serializeFlowchart(model);
    const result = parseFlowchart(dsl);
    expect(isParseSuccess(result)).toBe(true);
    if (isParseSuccess(result)) {
      expect(normalize(result.model)).toEqual(normalize(model));
    }
  });
});

describe('erd: parse(serialize(model)) round-trip', () => {
  it('round-trips attribute type/name/keys through export and re-import', () => {
    const model: DiagramModel = {
      diagramTypeId: 'erd',
      nodes: [
        {
          id: 'CUSTOMER',
          label: 'CUSTOMER',
          shape: 'rectangle',
          role: 'entity',
          position: { x: 0, y: 0 },
          attributes: [
            { type: 'string', name: 'id', keys: ['PK'] },
            { type: 'string', name: 'name', keys: [] },
          ],
        },
      ],
      edges: [],
      containers: [],
    };
    const dsl = serializeErd(model);
    const reparsed = parseErd(dsl);
    expect(isParseSuccess(reparsed)).toBe(true);
    if (isParseSuccess(reparsed)) {
      expect(reparsed.model.nodes[0].attributes).toEqual(model.nodes[0].attributes);
    }
  });
});

describe('architecture (cloud-infrastructure): parse(serialize(model)) round-trip', () => {
  it('round-trips an icon service inside a group', () => {
    const model: DiagramModel = {
      diagramTypeId: 'cloud-infrastructure',
      nodes: [
        {
          id: 'fn1',
          label: 'Order Processor',
          shape: 'icon',
          position: { x: 0, y: 0 },
          containerId: 'vpc1',
          icon: { libraryId: 'aws-icons', libraryVersion: '2024.1', iconId: 'lambda' },
        },
      ],
      edges: [],
      containers: [{ id: 'vpc1', label: 'VPC', position: { x: 0, y: 0 }, size: { width: 300, height: 200 } }],
    };
    const dsl = serializeArchitecture(model);
    const result = parseArchitecture(dsl);
    expect(isParseSuccess(result)).toBe(true);
    if (isParseSuccess(result)) {
      expect(normalize(result.model)).toEqual(normalize(model));
    }
  });
});

describe('sequence: parses valid DSL text into a structured model', () => {
  it('parses participants and a message between them', () => {
    const dsl = 'sequenceDiagram\nparticipant Alice\nparticipant Bob\nAlice->>Bob: Hello\n';
    const result = parseSequence(dsl);
    expect(isParseSuccess(result)).toBe(true);
  });

  it('parses "Note right of X" into a note-right container attached to X', () => {
    const dsl = 'sequenceDiagram\nparticipant Alice\nNote right of Alice: some text\n';
    const result = parseSequence(dsl);
    expect(isParseSuccess(result)).toBe(true);
    if (isParseSuccess(result)) {
      const note = result.model.containers.find((c) => c.role === 'note-right');
      expect(note).toBeDefined();
      expect(note?.attachedNodeIds).toEqual(['Alice']);
    }
  });
});

describe('uml: parses valid DSL text into a structured model', () => {
  it('parses a class with typed, visibility-marked attributes', () => {
    const dsl = ['classDiagram', 'class Foo {', '  +String pub', '  -String priv', '}', ''].join('\n');
    const result = parseUml(dsl);
    expect(isParseSuccess(result)).toBe(true);
    if (isParseSuccess(result)) {
      const foo = result.model.nodes.find((n) => n.id === 'Foo');
      expect(foo?.members).toEqual([
        { kind: 'attribute', visibility: '+', name: 'pub', type: 'String' },
        { kind: 'attribute', visibility: '-', name: 'priv', type: 'String' },
      ]);
    }
  });
});

describe('renderToSvg: escapes XML-sensitive characters in labels', () => {
  it('never emits raw user-supplied markup into the rendered SVG', () => {
    const withSpecialChars: DiagramModel = {
      diagramTypeId: 'flowchart',
      nodes: [{ id: 'A', label: 'A & B <C>', shape: 'rectangle', position: { x: 0, y: 0 } }],
      edges: [],
      containers: [],
    };
    const svg = renderToSvg(withSpecialChars);
    expect(svg).toContain('A &amp; B &lt;C&gt;');
    expect(svg).not.toContain('A & B <C>');
  });
});

describe('parseFlowchart: structured error reporting (FR-005)', () => {
  it('never throws on malformed input', () => {
    expect(() => parseFlowchart('this is not mermaid at all {{{')).not.toThrow();
    expect(() => parseFlowchart('')).not.toThrow();
  });

  it('reports a structured error with line and content for an unrecognized line', () => {
    const result = parseFlowchart('flowchart TD\n  A[Valid Node]\n  ???not-valid-syntax???\n');
    expect(isParseSuccess(result)).toBe(false);
    if (!isParseSuccess(result)) {
      expect(result.errors.length).toBeGreaterThan(0);
      expect(result.errors[0]).toMatchObject({
        line: 3,
        content: expect.stringContaining('???not-valid-syntax???'),
      });
      expect(result.errors[0].message).toBeTruthy();
    }
  });
});
