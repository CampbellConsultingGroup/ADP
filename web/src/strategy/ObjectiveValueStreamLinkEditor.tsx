/** Links a strategic objective to value streams, with the shared LinkEditor (ADP-blp.36). */

import React from "react";
import { useValueStreams } from "../api/business";
import {
  useLinkObjectiveValueStream,
  useUnlinkObjectiveValueStream,
  type StrategicObjective,
} from "../api/strategy";
import LinkEditor from "../links/LinkEditor";

interface Props {
  objective: StrategicObjective;
}

export default function ObjectiveValueStreamLinkEditor({ objective }: Props): React.ReactElement {
  const all = useValueStreams();
  return (
    <LinkEditor
      action="write_business_arch"
      noun="value stream"
      plural="value streams"
      isLoading={all.isLoading}
      options={(all.data?.items ?? []).map((v) => ({ id: v.id, label: v.name }))}
      linkedIds={objective.value_stream_ids}
      link={useLinkObjectiveValueStream(objective.id)}
      unlink={useUnlinkObjectiveValueStream(objective.id)}
    />
  );
}
