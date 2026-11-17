import React, { useRef } from "react";

/**
 * The one tab bar (ADP-blp.45). Six screens each had their own copy of an underline tab bar and
 * two more used filled pills, none with tab semantics: a screen reader heard a row of unrelated
 * buttons and the arrow keys did nothing. This one is a real tablist: the selected tab is
 * announced, Left/Right/Home/End move between tabs, and only the selected tab is in the Tab order.
 *
 * `variant="pill"` is for a secondary level inside a panel (the application detail's sections),
 * where the bar wraps onto several rows.
 */
export interface TabDef<T extends string> {
  id: T;
  label: React.ReactNode;
}

interface TabsProps<T extends string> {
  tabs: ReadonlyArray<TabDef<T>>;
  active: T;
  onChange: (id: T) => void;
  /** What the tabs switch between, for assistive technology (e.g. "Business architecture"). */
  label: string;
  variant?: "underline" | "pill";
  className?: string;
  style?: React.CSSProperties;
}

export function Tabs<T extends string>({
  tabs, active, onChange, label, variant = "underline", className = "", style,
}: TabsProps<T>): React.ReactElement {
  const ref = useRef<HTMLDivElement>(null);

  function onKeyDown(event: React.KeyboardEvent<HTMLButtonElement>) {
    const index = tabs.findIndex((t) => t.id === active);
    let next = index;
    if (event.key === "ArrowRight") next = (index + 1) % tabs.length;
    else if (event.key === "ArrowLeft") next = (index - 1 + tabs.length) % tabs.length;
    else if (event.key === "Home") next = 0;
    else if (event.key === "End") next = tabs.length - 1;
    else return;
    event.preventDefault();
    onChange(tabs[next].id);
    ref.current?.querySelectorAll<HTMLButtonElement>('[role="tab"]')[next]?.focus();
  }

  return (
    <div
      ref={ref}
      role="tablist"
      aria-label={label}
      className={`ui-tabs ui-tabs-${variant} ${className}`}
      style={style}
    >
      {tabs.map((tab) => {
        const selected = tab.id === active;
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            className={`ui-tab${selected ? " active" : ""}`}
            onClick={() => onChange(tab.id)}
            onKeyDown={onKeyDown}
          >
            {tab.label}
          </button>
        );
      })}
    </div>
  );
}

export default Tabs;
