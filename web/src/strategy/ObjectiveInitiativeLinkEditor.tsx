/** Links a strategic objective to initiatives, with the shared LinkEditor (ADP-blp.36). The
 * "linked" set comes from a dedicated reverse-lookup query (useObjectiveInitiatives) rather than
 * an inline field on the objective, since GET /objectives/{id} doesn't carry initiative_ids. */

import React from "react";
import {
  useInitiatives,
  useObjectiveInitiatives,
  useLinkObjectiveToInitiative,
  useUnlinkObjectiveFromInitiative,
} from "../api/strategy";
import LinkEditor from "./LinkEditor";

interface Props {
  objectiveId: string;
  /** Opens the initiative within the Strategy screen. Omitted: the name is plain text. */
  onNavigateToInitiative?: (initiativeId: string) => void;
}

export default function ObjectiveInitiativeLinkEditor({ objectiveId, onNavigateToInitiative }: Props): React.ReactElement {
  const all = useInitiatives();
  const linked = useObjectiveInitiatives(objectiveId);
  // The linked initiatives come from their own query, so list them first: a linked initiative
  // is shown even if the full list has not loaded it.
  const linkedItems = linked.data?.items ?? [];
  const linkedIdSet = new Set(linkedItems.map((i) => i.id));
  const options = [
    ...linkedItems.map((i) => ({ id: i.id, label: i.name })),
    ...(all.data?.items ?? [])
      .filter((i) => !linkedIdSet.has(i.id))
      .map((i) => ({ id: i.id, label: i.name })),
  ];
  return (
    <LinkEditor
      noun="initiative"
      plural="initiatives"
      prompt="Link an initiative…"
      isLoading={all.isLoading || linked.isLoading}
      options={options}
      linkedIds={linkedItems.map((i) => i.id)}
      link={useLinkObjectiveToInitiative(objectiveId)}
      unlink={useUnlinkObjectiveFromInitiative(objectiveId)}
      onOpen={onNavigateToInitiative}
      openTitle="Jump to this initiative"
    />
  );
}
