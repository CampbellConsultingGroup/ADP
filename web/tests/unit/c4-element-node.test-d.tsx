/**
 * Compile-time type tests for C4ElementNode — ART-XII / QG-17.
 * Verified by `tsc --noEmit`. @ts-expect-error lines succeed ONLY when
 * TypeScript rejects the prop, enforcing the no-style-override contract.
 *
 * If C4ElementNode ever starts accepting a color/fill/stroke/style prop,
 * the corresponding @ts-expect-error becomes "unused" and tsc --noEmit fails.
 */
import { C4ElementNode } from "../../src/canvas/nodes/C4ElementNode";
import type { C4NodeData } from "../../src/types";

const validData: C4NodeData = {
  element: { id: "e1", name: "Test", kind: "container" },
  style: { fill: "#438DD5", stroke: "#3C7FC0", color: "#fff", shape: "box" },
  selected: false,
};

// Valid usage — must compile without error
const _valid = <C4ElementNode data={validData} selected={false} />;
void _valid;

// ART-XII enforcement — none of these extra props should compile:

// @ts-expect-error — color is not a valid prop
const _color = <C4ElementNode data={validData} selected={false} color="red" />;
void _color;

// @ts-expect-error — fill is not a valid prop
const _fill = <C4ElementNode data={validData} selected={false} fill="#ff0000" />;
void _fill;

// @ts-expect-error — stroke is not a valid prop
const _stroke = <C4ElementNode data={validData} selected={false} stroke="blue" />;
void _stroke;

// @ts-expect-error — backgroundColor is not a valid prop
const _bg = <C4ElementNode data={validData} selected={false} backgroundColor="#333" />;
void _bg;

// @ts-expect-error — customStyle is not a valid prop
const _cs = <C4ElementNode data={validData} selected={false} customStyle={{}} />;
void _cs;
