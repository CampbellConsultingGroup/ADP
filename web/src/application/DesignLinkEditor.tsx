import { useDesigns } from "../api/business";
import { useAppDesignLinks, useCreateAppDesignLink, useDeleteAppDesignLink } from "../api/application";
import LinkEditor from "../links/LinkEditor";

interface Props { appId: string; }

/** An application's design links. A wrapper over the shared LinkEditor (ADP-blp.36). */
export default function DesignLinkEditor({ appId }: Props) {
  const { data: links, isLoading } = useAppDesignLinks(appId);
  const { data: designs } = useDesigns();
  const createLink = useCreateAppDesignLink(appId);
  const deleteLink = useDeleteAppDesignLink(appId);

  const all = (designs?.designs ?? []).map((d) => ({ id: d.id, label: d.title }));
  const titleOf = new Map(all.map((d) => [d.id, d.label]));
  const linked = (links?.items ?? []).map((l) => ({ id: l.design_id, label: titleOf.get(l.design_id) ?? l.design_id }));

  return (
    <LinkEditor
      title="Linked Designs"
      action="write_application"
      noun="design"
      plural="designs"
      isLoading={isLoading}
      options={all}
      linkedIds={linked.map((d) => d.id)}
      linkedItems={linked}
      link={createLink}
      unlink={deleteLink}
    />
  );
}
