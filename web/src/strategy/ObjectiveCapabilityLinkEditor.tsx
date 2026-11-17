/** Links a strategic objective to business capabilities. The editor itself is the shared
 * LinkEditor (ADP-blp.36); the linked set comes straight off the objective (capability_ids). */

import React from "react";
import { useCapabilities } from "../api/business";
import {
  useLinkObjectiveCapability,
  useUnlinkObjectiveCapability,
  type StrategicObjective,
} from "../api/strategy";
import LinkEditor from "./LinkEditor";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveCapabilityLinkEditor({ objective }: Props): React.ReactElement {
  const all = useCapabilities();
  return (
    <LinkEditor
      noun="capability"
      entityKind="business_capability"
      plural="capabilities"
      isLoading={all.isLoading}
      options={(all.data?.items ?? []).map((c) => ({ id: c.id, label: c.name }))}
      linkedIds={objective.capability_ids}
      link={useLinkObjectiveCapability(objective.id)}
      unlink={useUnlinkObjectiveCapability(objective.id)}
    />
  );
}
