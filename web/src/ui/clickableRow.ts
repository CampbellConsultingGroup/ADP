import type { KeyboardEvent } from "react";

/**
 * Props that make a non-button element (a list row, a card) behave like a button: focusable with
 * Tab and activated with Enter or Space, as well as by click (ADP-blp.40).
 *
 * Rows that open a detail view were plain `<div onClick>`s, so the main list-to-detail navigation
 * on several screens could not be used from the keyboard. Spread the result onto the element:
 *
 *   <div {...clickableRow(() => onSelect(item.id))} aria-current={selected}>
 *
 * Keys pressed inside a nested control (a button or input in the row) are left alone.
 */
export function clickableRow(onActivate: () => void) {
  return {
    role: "button" as const,
    tabIndex: 0,
    onClick: onActivate,
    onKeyDown: (event: KeyboardEvent<HTMLElement>) => {
      if (event.target !== event.currentTarget) return;
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        onActivate();
      }
    },
  };
}
