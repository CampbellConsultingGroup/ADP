/** A compliance status as coloured text (944-agent-traceability), reusing the Compliance screen's
 * labels and colours. */

import type React from "react";
import type { ComplianceStatus } from "../api/compliance";
import { STATUS_COLOR, STATUS_LABEL } from "../compliance/ControlMappingsEditor";

export function ComplianceStatusText({ status }: { status: ComplianceStatus }): React.ReactElement {
  return (
    <span style={{ fontSize: 12, fontWeight: 600, color: STATUS_COLOR[status] }}>{STATUS_LABEL[status]}</span>
  );
}
