import React from "react";
import TechCapTree from "./TechCapTree";

/** Technical Architecture screen (top-level nav item). Captures technical
 *  capabilities and other technical characteristics -- deliberately mirrors
 *  the look and interaction feel of Business Architecture's Capabilities tab
 *  (CapabilityTree.tsx/CapabilityNode.tsx) but scoped to exactly what
 *  `TechnicalCapability` already supports today (no maturity_level, no
 *  domain assignment, no Heat Map/orphan-report/agent-review/chat -- those
 *  are Business Capability-specific enrichments from later work, out of
 *  scope here). */
export default function TechCapPage(): React.ReactElement {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", fontFamily: "Arial, sans-serif" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 900, width: "100%", margin: "0 auto" }}>
        <div style={{ marginBottom: 20 }}>
          <h2 style={{ fontSize: 20, fontWeight: 700, color: "var(--ink)", margin: "0 0 4px" }}>Technical Architecture</h2>
          <p style={{ fontSize: 13, color: "var(--ink-3)", margin: 0 }}>
            Define the technical capabilities that describe the platform's technology foundation.
          </p>
        </div>

        <TechCapTree />
      </div>
    </div>
  );
}
