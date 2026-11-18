/** The strategic objectives an application realizes (ADP-d8u.2), linked from the application's
 * side. A wrapper over the shared LinkEditor (ADP-blp.36). */

import {
  useApplicationObjectives,
  useObjectives,
  useLinkApplicationToObjective,
  useUnlinkApplicationFromObjective,
} from "../api/strategy";
import LinkEditor from "../links/LinkEditor";

interface Props {
  appId: string;
}

export default function ObjectiveLinksPanel({ appId }: Props) {
  const { data: linked, isLoading } = useApplicationObjectives(appId);
  const { data: allObjectives } = useObjectives();
  const link = useLinkApplicationToObjective(appId);
  const unlink = useUnlinkApplicationFromObjective(appId);

  const linkedItems = (linked?.items ?? []).map((o) => ({ id: o.id, label: o.statement }));

  return (
    <LinkEditor
      title="Objectives Realized"
      action="write_business_arch"
      noun="objective"
      plural="objectives"
      prompt="Link an objective…"
      isLoading={isLoading}
      options={(allObjectives?.items ?? []).map((o) => ({ id: o.id, label: o.statement }))}
      linkedIds={linkedItems.map((o) => o.id)}
      linkedItems={linkedItems}
      link={link}
      unlink={unlink}
    />
  );
}
