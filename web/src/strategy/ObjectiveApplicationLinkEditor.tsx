/** Links a strategic objective to applications, with the shared LinkEditor (ADP-blp.36). Uses
 * useApplicationsForLinking (a plain, non-Suspense query) rather than
 * web/src/api/application.ts's useApplications, which is useSuspenseQuery-based and needs a
 * <Suspense> boundary this part of the tree doesn't have. */

import React from "react";
import {
  useApplicationsForLinking,
  useLinkObjectiveApplication,
  useUnlinkObjectiveApplication,
  type StrategicObjective,
} from "../api/strategy";
import LinkEditor from "./LinkEditor";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveApplicationLinkEditor({ objective }: Props): React.ReactElement {
  const all = useApplicationsForLinking();
  return (
    <LinkEditor
      noun="application"
      entityKind="application"
      plural="applications"
      prompt="Link an application…"
      isLoading={all.isLoading}
      options={(all.data?.items ?? []).map((a) => ({ id: a.id, label: a.name }))}
      linkedIds={objective.application_ids}
      link={useLinkObjectiveApplication(objective.id)}
      unlink={useUnlinkObjectiveApplication(objective.id)}
    />
  );
}
