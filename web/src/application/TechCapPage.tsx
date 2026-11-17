import React from "react";
import TechCapTree from "./TechCapTree";
import { PageHeader } from "../ui/primitives";

/** Technical Architecture screen (top-level nav item). Captures technical
 *  capabilities and other technical characteristics -- deliberately mirrors
 *  the look and interaction feel of Business Architecture's Capabilities tab
 *  (CapabilityTree.tsx/CapabilityNode.tsx) but scoped to exactly what
 *  `TechnicalCapability` already supports today (no maturity_level, no
 *  domain assignment, no Heat Map/orphan-report/agent-review/chat -- those
 *  are Business Capability-specific enrichments from later work, out of
 *  scope here). */
export default function TechCapPage({ focusTechCapId = null }: { focusTechCapId?: string | null }): React.ReactElement {
  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div style={{ flex: 1, overflowY: "auto", padding: 20, maxWidth: 900, width: "100%", margin: "0 auto" }}>
        <PageHeader title="Technical Architecture" lede="Define the technical capabilities that describe the platform's technology foundation." />

        <TechCapTree focusId={focusTechCapId} />
      </div>
    </div>
  );
}
