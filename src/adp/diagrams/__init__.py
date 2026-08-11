"""Diagram types beyond C4 (ADP-SPEC-046).

Standalone, top-level diagram artifacts (flowchart, sequence, ER, UML,
cloud-architecture) additive to ADP's existing C4 workspace -- no
relationship to `ArchitectureDescription`, the C4 React Flow canvas
(`web/src/canvas/`), or `adp.renderer`. See specs/046-diagram-type-support/
for the full spec, research, and data model.

Parsing, DSL validation, and SVG rendering happen entirely client-side, in a
vendored copy of a sibling project's diagramming library
(`web/src/diagrams/core/`, see research.md Decision 1/2) -- this backend
package is deliberately just CRUD storage of an opaque DSL-source string,
plus one PNG-export endpoint reusing the existing `cairosvg` dependency
(research.md Decision 3).
"""

from __future__ import annotations
