/** Links an initiative to strategic objectives, with the shared LinkEditor (ADP-blp.36). The
 * linked set comes straight off the initiative (objective_ids). */

import React from "react";
import {
  useObjectives,
  useLinkInitiativeObjective,
  useUnlinkInitiativeObjective,
  type StrategyInitiative,
} from "../api/strategy";
import LinkEditor from "./LinkEditor";

interface Props {
  initiative: StrategyInitiative;
  /** Opens the objective within the Strategy screen. Omitted: the statement is plain text. */
  onNavigateToObjective?: (objectiveId: string) => void;
}

export default function InitiativeObjectiveLinkEditor({ initiative, onNavigateToObjective }: Props): React.ReactElement {
  const all = useObjectives();
  return (
    <LinkEditor
      noun="objective"
      plural="objectives"
      prompt="Link an objective…"
      isLoading={all.isLoading}
      options={(all.data?.items ?? []).map((o) => ({ id: o.id, label: o.statement }))}
      linkedIds={initiative.objective_ids}
      link={useLinkInitiativeObjective(initiative.id)}
      unlink={useUnlinkInitiativeObjective(initiative.id)}
      onOpen={onNavigateToObjective}
      openTitle="Jump to this objective"
    />
  );
}
