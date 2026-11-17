/** NavLinkButton — a plain-text-looking, clickable cross-reference to
 * another strategy entity (Theme/Objective/Initiative). Shared by
 * ObjectiveDetail's Theme field and the "Linked ___" panels that previously
 * rendered the other side's name as inert plain `<span>` text -- the direct
 * ask behind "we need a method of navigation on the strategy screens to
 * allow navigation between themes - objectives and initiatives." Renders as
 * a real <button> (not an <a>, since there is no URL/route backing these
 * views -- StrategyPage's tab/detail state is the only navigation model) so
 * it stays keyboard- and screen-reader-accessible. */

import React from "react";

interface NavLinkButtonProps {
  onClick: () => void;
  children: React.ReactNode;
  title?: string;
}

export default function NavLinkButton({ onClick, children, title }: NavLinkButtonProps): React.ReactElement {
  return (
    <button
      type="button"
      onClick={onClick}
      title={title}
      style={{
        background: "none",
        border: "none",
        padding: 0,
        margin: 0,
        font: "inherit",
        color: "var(--accent)",
        cursor: "pointer",
        textDecoration: "underline",
        textAlign: "left",
      }}
    >
      {children}
    </button>
  );
}
