/** DesignLinkEditor — add/remove design links for capabilities and value streams (ADP-SPEC-034).
 * A thin wrapper over the shared link editor (ADP-blp.36): choosing a design links it. */

import React from "react";
import {
  useDesigns,
  useLinkedCapabilityDesigns,
  useLinkDesignToCapability,
  useUnlinkDesignFromCapability,
  useLinkedValueStreamDesigns,
  useLinkDesignToValueStream,
  useUnlinkDesignFromValueStream,
} from "../api/business";
import LinkEditor from "../links/LinkEditor";

interface Props {
  entityType: "capability" | "value-stream";
  entityId: string;
}

export default function DesignLinkEditor({ entityType, entityId }: Props): React.ReactElement {
  const isCapability = entityType === "capability";

  const capLinkedQuery = useLinkedCapabilityDesigns(isCapability ? entityId : null);
  const vsLinkedQuery = useLinkedValueStreamDesigns(!isCapability ? entityId : null);
  const linkedQuery = isCapability ? capLinkedQuery : vsLinkedQuery;
  const allDesigns = useDesigns();

  const linkToCapability = useLinkDesignToCapability(entityId);
  const unlinkFromCapability = useUnlinkDesignFromCapability(entityId);
  const linkToVs = useLinkDesignToValueStream(entityId);
  const unlinkFromVs = useUnlinkDesignFromValueStream(entityId);

  // The linked designs come from their own request, so one outside the picker's page of
  // designs is still listed.
  const linked = (linkedQuery.data?.items ?? []).map((d) => ({
    id: d.design_id,
    label: d.title,
    detail: d.lifecycle_status,
  }));

  return (
    <LinkEditor
      action="write_business_arch"
      noun="design"
      plural="designs"
      isLoading={linkedQuery.isLoading}
      options={(allDesigns.data?.designs ?? []).map((d) => ({ id: d.id, label: d.title }))}
      linkedIds={linked.map((d) => d.id)}
      linkedItems={linked}
      link={isCapability ? linkToCapability : linkToVs}
      unlink={isCapability ? unlinkFromCapability : unlinkFromVs}
    />
  );
}
