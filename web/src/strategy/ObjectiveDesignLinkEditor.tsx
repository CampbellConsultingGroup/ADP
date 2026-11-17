/** Links a strategic objective to designs, with the shared LinkEditor (ADP-blp.36). The design
 * list comes from a plain, non-Suspense query (useDesignsForLinking) rather than
 * web/src/api/designs.ts's own hooks. */

import React from "react";
import {
  useDesignsForLinking,
  useLinkObjectiveDesign,
  useUnlinkObjectiveDesign,
  type StrategicObjective,
} from "../api/strategy";
import LinkEditor from "../links/LinkEditor";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveDesignLinkEditor({ objective }: Props): React.ReactElement {
  const all = useDesignsForLinking();
  return (
    <LinkEditor
      noun="design"
      plural="designs"
      isLoading={all.isLoading}
      options={(all.data?.designs ?? []).map((d) => ({ id: d.id, label: d.title }))}
      linkedIds={objective.design_ids}
      link={useLinkObjectiveDesign(objective.id)}
      unlink={useUnlinkObjectiveDesign(objective.id)}
    />
  );
}
